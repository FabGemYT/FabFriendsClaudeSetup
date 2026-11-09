# claude-cleanup.ps1 - close what Claude Code sessions leave running on this machine.
#
# WHY THIS EXISTS. Two different costs, both measured here.
#
# 1. LEFTOVERS (measured 2026-10-29 on Claude Code 2.1.312; open upstream as
#    anthropics/claude-code #91523, #92583 and #97752). When Claude stops a
#    background command, a command times out, or a session closes, Claude Code
#    kills the outer Git Bash shell with `taskkill /T`. That walk follows Windows
#    parent links, and Git Bash tools (sleep, tail, grep, find) have none: their
#    Windows parent exits the moment they start. So they keep running. A 10-second
#    test proved it: a stopped `node` died, a stopped `sleep` survived. On the day,
#    three "stopped" a live web game alarms were still running and a `tail` from 24 Oct had
#    used 26 minutes of CPU doing nothing. Native programs survive the same way when
#    something between them and claude.exe has already exited.
#
# 2. MULTIPLICATION (measured 2026-08-07): every open session runs its own helpers
#    (about 0.5 GB of local MCP servers, up to 1.4 GB of TypeScript server). Sessions
#    here stay open for days and sit idle most of the time (an online store about 121 of 168
#    hours in the week to 2026-10-30), holding all of it the whole time.
#
# 3. IDLE SESSIONS (measured 2026-10-30, Claude Code 2.1.312). When Claude Code's own
#    registry (~/.claude/sessions/<pid>.json: "status": "idle", "statusUpdatedAt") shows
#    a session idle for -IdleHours, this closes that session's TypeScript language
#    server and NOTHING else of it. Claude Code starts the server again by itself the
#    next time that session touches a code file (read in the binary: a stopped or
#    crashed server is restarted before use, and the crash counter resets on every
#    successful start). MCP helpers are never closed in an open session: an interactive
#    session does not restart a stdio MCP server that exits (docs, "Stdio servers that
#    exit"), so closing one would break that session's tools until /mcp Reconnect.
#
# SAFE BY CONSTRUCTION. A group of processes is closed only when ALL of these hold:
#   1. ORPHANED. Git Bash tools are judged by Git Bash's own process table, because
#      Windows shows them parentless even while a live shell waits on them (judging
#      them by Windows would kill a live timer). Everything else: its Windows parent
#      is gone, or that parent PID now belongs to a newer process.
#   2. CLAUDE'S. The top process is a Git Bash tool, node, python, esbuild, bun,
#      deno, cmd or a Git program, never anything else (not explorer, a terminal,
#      Chrome or an app), and the group traces back to Claude: Git Bash started it,
#      it is a known stdio helper, or it runs from a project folder, the npx cache,
#      the global npm folder or Claude's temp folder. Anything else is not listed.
#   3. UNUSED. Never closed: anything still under a live claude.exe; claude itself,
#      explorer, terminals, VS Code; the shared agent-browser daemon; scheduled jobs
#      under ~/.claude/scheduled; anything with a visible window; anything younger
#      than -MinAgeMinutes. Servers and scripts inside a project whose session is
#      still open are left to that session, because a live web game starts its test server
#      detached and it looks orphaned while in use. So is anything a program on this
#      machine or the LAN is connected to, and anything that cannot be traced to a
#      project at all.
#      Two kinds skip the project and connection rules, because once orphaned
#      nothing can use them: bare Git Bash tools (a timer or a search whose shell is
#      gone) and stdio helpers (MCP servers, the TypeScript language server), whose
#      only client was a claude.exe that is gone. A connection to the internet does
#      NOT protect a leftover: a script still spending on a paid API with no session
#      behind it is exactly what must stop (CLAUDE.md, spending rule 6).
# More than -MaxGroups candidates at once means something is off: report, close
# nothing. Any error before the closing step closes nothing.
#
#   powershell -File ~/.claude/bin/claude-cleanup.ps1            # report only (dry run)
#   powershell -File ~/.claude/bin/claude-cleanup.ps1 -Force     # close them
#
# hooks/sweep-leftovers.sh runs it with -Force -Quiet on SessionStart and Stop.
# Closes are logged to ~/.claude/state/cleanup.log, and each real sweep's summary
# goes to ~/.claude/state/cleanup-last-run.json (read by /health). The tests are
# hooks/tests/test-sweep-leftovers.py; run them after ANY edit to this file.

param(
  [switch]$Force,
  [switch]$Quiet,              # hooks: no output, log only
  [switch]$Json,               # tests and /health: machine-readable report
  [int]$MinAgeMinutes = 2,
  [int]$MaxGroups = 40,
  [double]$IdleHours = 2,      # an idle session's TypeScript server sleeps after this long
  [string]$OnlyMarker = '',    # tests: consider only groups whose command lines contain one of these (comma-separated)
  [string]$Trigger = 'manual'
)

# Not 'Stop': Windows PowerShell 5.1 turns a native tool's stderr into a terminating
# error under 'Stop' even when it is redirected. Cmdlets that matter say -ErrorAction
# Stop themselves, and the try block below catches everything else.
$ErrorActionPreference = 'Continue'
$StateDir = Join-Path $env:USERPROFILE '.claude\state'
if ($env:CLAUDE_CLEANUP_STATE_DIR) { $StateDir = $env:CLAUDE_CLEANUP_STATE_DIR }   # tests keep the real log clean
$LogFile = Join-Path $StateDir 'cleanup.log'
$LastRunFile = Join-Path $StateDir 'cleanup-last-run.json'

function Write-Log([string]$Line) {
  try {
    if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir -Force | Out-Null }
    if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt 512KB)) {
      $keep = @(Get-Content -Path $LogFile -Tail 2000)
      Set-Content -Path $LogFile -Value $keep -Encoding UTF8
    }
    Add-Content -Path $LogFile -Value ('{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Trigger, $Line) -Encoding UTF8
  } catch { }
}
function Say([string]$Line) { if (-not $Quiet -and -not $Json) { Write-Output $Line } }
function Save-LastRun($Summary) {
  if (-not $Force) { return }
  try {
    if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir -Force | Out-Null }
    Set-Content -Path $LastRunFile -Value ($Summary | ConvertTo-Json -Compress) -Encoding UTF8
  } catch { }
}

# Lower case, one kind of slash, and Git Bash's /d/x spelling turned into d:\x.
function Normalize([string]$Text) {
  if (-not $Text) { return '' }
  $t = $Text.ToLowerInvariant().Replace('/', '\')
  return [regex]::Replace($t, '(^|[\s"''=])\\([a-z])\\', '$1$2:\')
}
# Is the folder $Root named in $Text, as a whole folder and not a prefix of another?
function Test-Under([string]$Text, [string]$Root) {
  if (-not $Text -or -not $Root) { return $false }
  return [regex]::IsMatch($Text, [regex]::Escape($Root.TrimEnd('\')) + '(\\|"|''|\s|$)')
}

$summary = [ordered]@{ time = (Get-Date -Format 's'); trigger = $Trigger; live_sessions = 0; candidates = 0; closed = 0; slept = 0; braked = $false; error = '' }

try {
  # --- the process table ----------------------------------------------------
  $all = @(Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId, Name, ExecutablePath, CommandLine, CreationDate, WorkingSetSize -ErrorAction Stop)
  if ($all.Count -lt 10) { throw "only $($all.Count) processes visible" }
  $byPid = @{}
  foreach ($p in $all) { $byPid[[int]$p.ProcessId] = $p }

  # The real parent, or $null when it is gone or its PID now belongs to a newer process.
  function Get-RealParent($p) {
    $pp = $byPid[[int]$p.ParentProcessId]
    if ($null -eq $pp -or [int]$pp.ProcessId -eq [int]$p.ProcessId) { return $null }
    if ($pp.CreationDate -gt $p.CreationDate) { return $null }
    return $pp
  }
  $kids = @{}
  foreach ($p in $all) {
    $pp = Get-RealParent $p
    if ($pp) {
      $k = [int]$pp.ProcessId
      if (-not $kids.ContainsKey($k)) { $kids[$k] = New-Object System.Collections.Generic.List[int] }
      $kids[$k].Add([int]$p.ProcessId)
    }
  }

  # --- open sessions, from Claude Code's own registry ------------------------
  # ~/.claude/sessions/<pid>.json names each running session's pid, folder and id.
  # A file whose pid is gone, or now belongs to another process, does not count.
  $liveCwds = New-Object System.Collections.Generic.List[string]
  $liveIds = New-Object System.Collections.Generic.HashSet[string]
  $liveSessions = New-Object System.Collections.Generic.List[object]
  $registryOk = $true
  $SessionsDir = Join-Path $env:USERPROFILE '.claude\sessions'
  if ($env:CLAUDE_CLEANUP_SESSIONS_DIR) { $SessionsDir = $env:CLAUDE_CLEANUP_SESSIONS_DIR }   # tests only
  try {
    foreach ($f in @(Get-ChildItem -Path $SessionsDir -Filter '*.json' -File -ErrorAction Stop)) {
      try { $s = Get-Content -Raw -Path $f.FullName -ErrorAction Stop | ConvertFrom-Json } catch { continue }
      if (-not $s.pid) { continue }
      $sp = $byPid[[int]$s.pid]
      if ($null -eq $sp -or ([string]$sp.Name) -notlike 'claude*') { continue }
      if ($s.procStart -and $sp.CreationDate) {
        try { if ([math]::Abs($sp.CreationDate.ToFileTimeUtc() - [Int64]$s.procStart) -gt 20000000) { continue } } catch { }
      }
      if ($s.cwd) { $liveCwds.Add((Normalize ([string]$s.cwd)).TrimEnd('\')) }
      if ($s.sessionId) { [void]$liveIds.Add(([string]$s.sessionId).ToLowerInvariant()) }
      $idleFor = 0
      if ($s.status -eq 'idle' -and $s.statusUpdatedAt) {
        try { $idleFor = ((Get-Date).ToUniversalTime() - [DateTimeOffset]::FromUnixTimeMilliseconds([Int64]$s.statusUpdatedAt).UtcDateTime).TotalHours } catch { $idleFor = 0 }
      }
      $liveSessions.Add([pscustomobject]@{ Pid = [int]$s.pid; Name = [string]$s.name; Cwd = [string]$s.cwd; Status = [string]$s.status; IdleHours = $idleFor })
    }
  } catch { $registryOk = $false }
  $summary.live_sessions = $liveIds.Count

  # Project homes: the folders the open sessions' projects live in (~/projects
  # here). A path inside one of them, outside every open project, belongs to a
  # project nobody has open. Never a drive root, never the user profile itself.
  $profileNorm = (Normalize $env:USERPROFILE).TrimEnd('\')
  $homes = New-Object System.Collections.Generic.List[string]
  foreach ($c in $liveCwds) {
    $parent = Split-Path -Path $c -Parent
    if ($parent -and $parent.Length -gt 3 -and $parent -ne $profileNorm -and -not $homes.Contains($parent)) { $homes.Add($parent) }
  }

  # --- Git Bash's own process table -------------------------------------------
  $gitRoot = $null
  foreach ($g in @("$env:ProgramFiles\Git", "${env:ProgramFiles(x86)}\Git", "$env:LOCALAPPDATA\Programs\Git")) {
    if ($g -and (Test-Path (Join-Path $g 'usr\bin\ps.exe'))) { $gitRoot = $g; break }
  }
  $gitNorm = $null; $msysNorm = $null
  if ($gitRoot) { $gitNorm = (Normalize $gitRoot).TrimEnd('\') + '\'; $msysNorm = $gitNorm + 'usr\bin\' }
  $msys = @{}; $msysByWin = @{}; $msysKids = @{}
  if ($gitRoot) {
    foreach ($line in @(& (Join-Path $gitRoot 'usr\bin\ps.exe') -l 2>$null)) {
      $m = [regex]::Match([string]$line, '^\s*[A-Z]?\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+\S+\s+\d+\s+(\d\d:\d\d:\d\d|[A-Z][a-z]{2}\s+\d+)\s+(.+?)\s*$')
      if (-not $m.Success) { continue }
      $o = [pscustomobject]@{ Pid = [int]$m.Groups[1].Value; PPid = [int]$m.Groups[2].Value; WinPid = [int]$m.Groups[4].Value }
      $msys[$o.Pid] = $o
      $msysByWin[$o.WinPid] = $o.Pid
    }
    foreach ($o in $msys.Values) {
      if (-not $msysKids.ContainsKey($o.PPid)) { $msysKids[$o.PPid] = New-Object System.Collections.Generic.List[int] }
      $msysKids[$o.PPid].Add($o.Pid)
    }
  }
  function Test-MsysExe($p) { return [bool]($msysNorm -and $p.ExecutablePath -and (Normalize $p.ExecutablePath).StartsWith($msysNorm)) }
  function Test-GitNative($p) {
    if (-not $gitNorm -or -not $p.ExecutablePath) { return $false }
    $e = Normalize $p.ExecutablePath
    return ($e.StartsWith($gitNorm) -and -not $e.StartsWith($msysNorm))
  }
  $ShellNames = @('bash.exe', 'sh.exe', 'dash.exe', 'zsh.exe')
  # A Git Bash process is orphaned when its Git Bash parent is gone. At the top of
  # a Git Bash tree (parent 1) the parent is a Windows program: judge that link by Windows.
  function Test-MsysOrphan($o) {
    if ($o.PPid -ne 1) { return -not $msys.ContainsKey($o.PPid) }
    $w = $byPid[$o.WinPid]
    if ($null -eq $w) { return $false }
    return ($null -eq (Get-RealParent $w))
  }
  function Get-MsysCwd([int]$CygPid) {
    try {
      $posix = @(& (Join-Path $gitRoot 'usr\bin\readlink.exe') "/proc/$CygPid/cwd" 2>$null)[0]
      if (-not $posix) { return '' }
      $win = @(& (Join-Path $gitRoot 'usr\bin\cygpath.exe') -w $posix 2>$null)[0]
      return (Normalize ([string]$win)).TrimEnd('\')
    } catch { return '' }
  }

  # --- what a group is ----------------------------------------------------------
  $NativeRootNames = @('node.exe', 'python.exe', 'pythonw.exe', 'py.exe', 'esbuild.exe', 'bun.exe', 'deno.exe', 'cmd.exe')
  $NeverNames = @('claude.exe', 'explorer.exe', 'windowsterminal.exe', 'openconsole.exe', 'code.exe')
  $ClaudeMarks = @('\npm-cache\_npx\', '\appdata\roaming\npm\', '\temp\claude\')
  function Test-Helper([string]$n) {
    if ($n.Contains('typescript-language-server') -or $n.Contains('\typescript\lib\tsserver.js') -or $n.Contains('\typescript\lib\typingsinstaller.js')) { return $true }
    if ($n.Contains('chrome-devtools-mcp')) { return $true }
    if ($n.Contains('shadcn') -and [regex]::IsMatch($n, '(\s|")mcp("|\s|$)')) { return $true }
    if (($n.Contains('\npm-cache\_npx\') -or $n.Contains('\appdata\roaming\npm\node_modules\')) -and $n.Contains('mcp')) { return $true }
    return $false
  }
  $sidRegex = [regex]'\\temp\\claude\\[^\\]+\\([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(\\|"|''|\s|$)'
  # 'live' = inside an open session's project or temp folder, 'closed' = inside a
  # project folder nobody has open (or a known Git Bash folder outside every open
  # project), '' = cannot tell.
  function Get-Place([string]$n, [bool]$KnownFolder) {
    $m = $sidRegex.Match($n)
    if ($m.Success) { if ($liveIds.Contains($m.Groups[1].Value)) { return 'live' } else { return 'closed' } }
    foreach ($c in $liveCwds) { if (Test-Under $n $c) { return 'live' } }
    if ($KnownFolder) { return 'closed' }
    foreach ($h in $homes) { if (Test-Under $n $h) { return 'closed' } }
    return ''
  }
  function Get-Group([int]$RootWinPid) {
    $seen = New-Object System.Collections.Generic.HashSet[int]
    $queue = New-Object System.Collections.Generic.Queue[int]
    $queue.Enqueue($RootWinPid)
    while ($queue.Count -gt 0) {
      $w = $queue.Dequeue()
      if (-not $seen.Add($w)) { continue }
      if ($kids.ContainsKey($w)) { foreach ($c in $kids[$w]) { $queue.Enqueue($c) } }
      if ($msysByWin.ContainsKey($w) -and $msysKids.ContainsKey($msysByWin[$w])) {
        foreach ($cc in $msysKids[$msysByWin[$w]]) { $queue.Enqueue($msys[$cc].WinPid) }
      }
    }
    return @($seen | Where-Object { $byPid.ContainsKey($_) })
  }

  # --- orphan roots -------------------------------------------------------------
  $roots = New-Object System.Collections.Generic.List[int]
  foreach ($o in $msys.Values) {
    if ($byPid.ContainsKey($o.WinPid) -and (Test-MsysOrphan $o)) { $roots.Add($o.WinPid) }
  }
  foreach ($p in $all) {
    $id = [int]$p.ProcessId
    if ($id -le 4 -or $msysByWin.ContainsKey($id) -or (Test-MsysExe $p)) { continue }
    if ($NativeRootNames -notcontains ([string]$p.Name).ToLowerInvariant() -and -not (Test-GitNative $p)) { continue }
    if ($null -eq (Get-RealParent $p)) { $roots.Add($id) }
  }
  # Oldest first, and a root already inside an older group belongs to that group.
  $claimed = New-Object System.Collections.Generic.HashSet[int]
  $groups = New-Object System.Collections.Generic.List[object]
  foreach ($r in @($roots | Sort-Object { $byPid[$_].CreationDate })) {
    if ($claimed.Contains($r)) { continue }
    $members = Get-Group $r
    foreach ($m in $members) { [void]$claimed.Add($m) }
    $groups.Add([pscustomobject]@{ Root = $r; Members = $members })
  }

  # --- a verdict for each group -------------------------------------------------
  $windowPids = $null; $connPids = $null; $netOk = $true
  $now = Get-Date
  $markers = @($OnlyMarker.ToLowerInvariant().Split(',') | Where-Object { $_ })
  $marker = $markers.Count -gt 0
  $verdicts = New-Object System.Collections.Generic.List[object]
  foreach ($g in $groups) {
    $rootP = $byPid[$g.Root]
    $norms = @{}
    foreach ($m in $g.Members) { $norms[$m] = Normalize ([string]$byPid[$m].CommandLine + ' ' + [string]$byPid[$m].ExecutablePath) }
    $joined = ($norms.Values -join "`n")
    if ($marker -and -not ($markers | Where-Object { $joined.Contains($_) })) { continue }

    $hasMsys = $false; $allTools = $true
    foreach ($m in $g.Members) {
      $mp = $byPid[$m]
      $isMsys = $msysByWin.ContainsKey($m) -or (Test-MsysExe $mp)
      if ($isMsys) { $hasMsys = $true }
      $isTool = ($isMsys -and ($ShellNames -notcontains ([string]$mp.Name).ToLowerInvariant())) -or (Test-GitNative $mp)
      if (-not $isTool) { $allTools = $false }
    }
    $class = 'project'
    if (Test-Helper $norms[$g.Root]) { $class = 'helper' }
    elseif (($msysByWin.ContainsKey($g.Root) -or (Test-GitNative $rootP)) -and $allTools) { $class = 'bare-tool' }

    # Rule 2: only Claude's leftovers are this script's business.
    $ours = ($class -ne 'project') -or $hasMsys
    if (-not $ours) { foreach ($mk in $ClaudeMarks) { if ($joined.Contains($mk)) { $ours = $true; break } } }
    if (-not $ours) { foreach ($n in $norms.Values) { if (Get-Place $n $false) { $ours = $true; break } } }
    if (-not $ours -and -not $marker) { continue }

    $decision = 'close'; $reason = ''
    $ageMin = [math]::Round(($now - $rootP.CreationDate).TotalMinutes, 0)
    $names = @($g.Members | ForEach-Object { ([string]$byPid[$_].Name).ToLowerInvariant() })
    if (-not $ours) { $decision = 'keep'; $reason = 'not traceable to Claude' }
    elseif (@($names | Where-Object { $NeverNames -contains $_ -or $_ -like 'agent-browser*' }).Count -gt 0) { $decision = 'keep'; $reason = 'contains a process this never closes' }
    elseif ($joined.Contains('\.claude\scheduled\')) { $decision = 'keep'; $reason = 'a scheduled job' }
    elseif ($ageMin -lt $MinAgeMinutes) { $decision = 'keep'; $reason = "younger than $MinAgeMinutes min" }
    else {
      if ($null -eq $windowPids) {
        $windowPids = New-Object System.Collections.Generic.HashSet[int]
        foreach ($wp in @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero })) { [void]$windowPids.Add([int]$wp.Id) }
      }
      if (@($g.Members | Where-Object { $windowPids.Contains([int]$_) }).Count -gt 0) { $decision = 'keep'; $reason = 'has a visible window' }
    }
    if ($decision -eq 'close' -and $class -eq 'project') {
      if (-not $registryOk) { $decision = 'keep'; $reason = 'the open-session list is unreadable' }
      else {
        $places = New-Object System.Collections.Generic.List[string]
        foreach ($m in $g.Members) {
          if ($msysByWin.ContainsKey($m)) {
            $cwd = Get-MsysCwd $msysByWin[$m]
            if ($cwd) { $places.Add((Get-Place $cwd $true)) } else { $places.Add('unknown') }
          }
          $places.Add((Get-Place $norms[$m] $false))
        }
        if ($places.Contains('live')) { $decision = 'keep'; $reason = "its project's session is still open" }
        elseif ($places.Contains('unknown')) { $decision = 'keep'; $reason = 'its folder could not be read' }
        elseif (-not $places.Contains('closed')) { $decision = 'keep'; $reason = 'cannot tell which project it belongs to' }
        else {
          if ($null -eq $connPids) {
            $connPids = New-Object System.Collections.Generic.HashSet[int]
            if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
              foreach ($c in @(Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue)) {
                $ra = [string]$c.RemoteAddress
                if ($ra -eq '127.0.0.1' -or $ra -eq '::1' -or $ra -like '::ffff:127.*' -or $ra -like '10.*' -or $ra -like '192.168.*' -or
                    $ra -match '^172\.(1[6-9]|2\d|3[01])\.' -or $ra -like 'fe80:*' -or $ra -match '^f[cd][0-9a-f]{2}:') { [void]$connPids.Add([int]$c.OwningProcess) }
              }
            } else { $netOk = $false }
          }
          if (-not $netOk) { $decision = 'keep'; $reason = 'connections could not be read' }
          elseif (@($g.Members | Where-Object { $connPids.Contains([int]$_) }).Count -gt 0) { $decision = 'keep'; $reason = 'something on this machine is connected to it' }
        }
      }
    }
    if ($decision -eq 'close') {
      if ($class -eq 'bare-tool') { $reason = 'its Git Bash shell is gone, so nothing will ever read it' }
      elseif ($class -eq 'helper') { $reason = 'a helper whose Claude session is gone' }
      else { $reason = 'left over in a project with no open session' }
    }
    $mb = [math]::Round((($g.Members | ForEach-Object { [double]$byPid[$_].WorkingSetSize }) | Measure-Object -Sum).Sum / 1MB, 0)
    $rootCmd = [string]$rootP.CommandLine
    $verdicts.Add([pscustomobject]@{
      root = $g.Root; name = [string]$rootP.Name; class = $class; decision = $decision; reason = $reason
      age_min = $ageMin; mb = $mb; pids = @($g.Members); names = @($names)
      created = @($g.Members | ForEach-Object { $byPid[$_].CreationDate.ToFileTimeUtc() })
      cmd = $rootCmd.Substring(0, [math]::Min(110, $rootCmd.Length))
      cmds = @($g.Members | ForEach-Object { [string]$byPid[$_].CommandLine })
    })
  }

  # --- idle sessions: the TypeScript server sleeps until it is needed again -----
  # Only the language server that is a direct child of an idle session's claude.exe,
  # with its own subtree (the tsserver processes). Never busy sessions, never a
  # session idle for less than -IdleHours, never anything else the session runs.
  $sleepers = New-Object System.Collections.Generic.List[object]
  foreach ($s in $liveSessions) {
    if ($s.Status -ne 'idle' -or $s.IdleHours -lt $IdleHours -or -not $kids.ContainsKey($s.Pid)) { continue }
    foreach ($k in $kids[$s.Pid]) {
      if (-not (Normalize ([string]$byPid[$k].CommandLine)).Contains('typescript-language-server')) { continue }
      $members = Get-Group $k
      $joinedK = (@($members | ForEach-Object { Normalize ([string]$byPid[$_].CommandLine) }) -join "`n")
      if ($marker -and -not ($markers | Where-Object { $joinedK.Contains($_) })) { continue }
      $sleepers.Add([pscustomobject]@{
        root = $k; session = $s.Name; cwd = $s.Cwd; idle_h = [math]::Round($s.IdleHours, 1)
        mb = [math]::Round((($members | ForEach-Object { [double]$byPid[$_].WorkingSetSize }) | Measure-Object -Sum).Sum / 1MB, 0)
        pids = @($members); created = @($members | ForEach-Object { $byPid[$_].CreationDate.ToFileTimeUtc() })
        cmds = @($members | ForEach-Object { [string]$byPid[$_].CommandLine })
      })
    }
  }
} catch {
  $summary.error = $_.Exception.Message
  Write-Log "error, closed nothing: $($_.Exception.Message)"
  Save-LastRun $summary
  if ($Json) { [pscustomobject]@{ error = $summary.error; groups = @(); sleepers = @(); closed = @() } | ConvertTo-Json -Depth 5 -Compress }
  else { Say "Claude cleanup could not read this machine's processes, so it closed nothing: $($summary.error)" }
  exit 0
}

$toClose = @($verdicts | Where-Object { $_.decision -eq 'close' })
$summary.candidates = $toClose.Count

# --- report -------------------------------------------------------------------
if (-not $Quiet -and -not $Json) {
  $nodeAll = @($all | Where-Object { $_.Name -eq 'node.exe' })
  $os = Get-CimInstance Win32_OperatingSystem
  Say ''
  Say 'Claude cleanup'
  Say ('  open sessions      : {0}' -f $liveIds.Count)
  Say ('  node processes     : {0} totalling {1} MB' -f $nodeAll.Count, [math]::Round((($nodeAll | Measure-Object WorkingSetSize -Sum).Sum) / 1MB, 0))
  Say ('  memory in use      : {0}%' -f [math]::Round((1 - ($os.FreePhysicalMemory / $os.TotalVisibleMemorySize)) * 100, 0))
  Say ('  uptime             : {0} days' -f [math]::Round(((Get-Date) - $os.LastBootUpTime).TotalDays, 1))
  Say ''
  if ($toClose.Count -eq 0) { Say '  No leftovers. Nothing to close.' }
  else {
    Say ('  {0} leftover group(s), {1} MB:' -f $toClose.Count, (($toClose | Measure-Object mb -Sum).Sum))
    foreach ($v in $toClose) { Say ('    pid {0,-6} {1,-12} {2,5} MB  age {3,5} min  {4}  :: {5}' -f $v.root, $v.name, $v.mb, $v.age_min, $v.reason, $v.cmd) }
  }
  $kept = @($verdicts | Where-Object { $_.decision -eq 'keep' })
  if ($kept.Count -gt 0) {
    Say ''
    Say "  Claude's, but left alone:"
    foreach ($v in $kept) { Say ('    pid {0,-6} {1,-12} {2,5} MB  {3}  :: {4}' -f $v.root, $v.name, $v.mb, $v.reason, $v.cmd) }
  }
  if ($sleepers.Count -gt 0) {
    Say ''
    Say ("  Idle {0}+ hours, TypeScript server to put to sleep (it restarts when needed):" -f $IdleHours)
    foreach ($v in $sleepers) { Say ('    pid {0,-6} {1,5} MB  {2} ({3}), idle {4}h' -f $v.root, $v.mb, $v.session, $v.cwd, $v.idle_h) }
  }
  Say ''
}

if ($toClose.Count -gt $MaxGroups) {
  $summary.braked = $true
  Write-Log ("brake: {0} leftover groups at once is more than {1}; closed nothing" -f $toClose.Count, $MaxGroups)
  Save-LastRun $summary
  Say ("  SAFETY BRAKE: {0} at once is more than {1}. Nothing was closed; read the list above." -f $toClose.Count, $MaxGroups)
  if ($Json) { [pscustomobject]@{ live_sessions = $liveIds.Count; braked = $true; groups = $verdicts.ToArray(); sleepers = $sleepers.ToArray(); closed = @() } | ConvertTo-Json -Depth 5 -Compress }
  exit 0
}
if (-not $Force) {
  if ($toClose.Count -gt 0 -or $sleepers.Count -gt 0) { Say '  DRY RUN. Nothing was closed. Re-run with -Force to close them.' }
  if ($Json) { [pscustomobject]@{ live_sessions = $liveIds.Count; braked = $false; groups = $verdicts.ToArray(); sleepers = $sleepers.ToArray(); closed = @() } | ConvertTo-Json -Depth 5 -Compress }
  exit 0
}

# --- close ----------------------------------------------------------------------
# Re-check every pid is still the same process (start time) right before closing it.
function Test-Same([int]$ProcId, [Int64]$CreatedFt) {
  try { $gp = Get-Process -Id $ProcId -ErrorAction Stop } catch { return $false }
  try { return ([math]::Abs($gp.StartTime.ToFileTimeUtc() - $CreatedFt) -lt 20000000) } catch { return $false }
}
# Closes one group: its root with its Windows subtree, then any member still left
# (Git Bash children are not in that subtree). Returns the pids that are now gone.
function Close-Group($v) {
  $gonePids = New-Object System.Collections.Generic.List[int]
  if (-not (Test-Same $v.root $v.created[0])) { return ,$gonePids }
  & "$env:SystemRoot\System32\taskkill.exe" /PID $v.root /T /F 2>&1 | Out-Null
  for ($i = 0; $i -lt $v.pids.Count; $i++) {
    if (Test-Same $v.pids[$i] $v.created[$i]) { try { Stop-Process -Id $v.pids[$i] -Force -ErrorAction Stop } catch { } }
  }
  Start-Sleep -Milliseconds 300
  for ($i = 0; $i -lt $v.pids.Count; $i++) {
    if (-not (Test-Same $v.pids[$i] $v.created[$i])) { $gonePids.Add($v.pids[$i]) }
  }
  return ,$gonePids
}
$closedPids = New-Object System.Collections.Generic.List[int]
foreach ($v in $toClose) {
  $gone = Close-Group $v
  foreach ($p in $gone) { $closedPids.Add($p) }
  Write-Log ("closed {0}/{1} pid {2} {3} {4} MB age {5} min [{6}] {7} :: {8}" -f $gone.Count, $v.pids.Count, $v.root, $v.name, $v.mb, $v.age_min, $v.class, $v.reason, $v.cmd)
  Say ("  closed pid {0} {1} ({2} of {3} processes)" -f $v.root, $v.name, $gone.Count, $v.pids.Count)
}
$sleptPids = New-Object System.Collections.Generic.List[int]
foreach ($v in $sleepers) {
  $gone = Close-Group $v
  foreach ($p in $gone) { $sleptPids.Add($p) }
  if ($gone.Count -gt 0) { $summary.slept++ }
  Write-Log ("slept the TypeScript server of {0} ({1}), idle {2}h: {3}/{4} processes, {5} MB, pid {6}" -f $v.session, $v.cwd, $v.idle_h, $gone.Count, $v.pids.Count, $v.mb, $v.root)
  Say ("  put to sleep: TypeScript server of {0}, {1} MB ({2} of {3} processes)" -f $v.session, $v.mb, $gone.Count, $v.pids.Count)
}
$summary.closed = $closedPids.Count
Save-LastRun $summary
# .ToArray(), not @(): Windows PowerShell 5.1 throws "Argument types do not match"
# for @(<generic list>) inside an object literal.
if ($Json) { [pscustomobject]@{ live_sessions = $liveIds.Count; braked = $false; groups = $verdicts.ToArray(); sleepers = $sleepers.ToArray(); closed = $closedPids.ToArray(); slept = $sleptPids.ToArray() } | ConvertTo-Json -Depth 5 -Compress }
exit 0
