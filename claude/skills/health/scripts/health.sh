#!/bin/bash
# health.sh -- the silent-failure check for the ~/.claude system.
#
# Every check here exists because its failure mode actually happened and was
# invisible until someone went digging: a dead advisor key, a model alias that
# resolved to an older Opus, a 200k window that should have been 1M, a guard
# hole behind $HOME, missing poppler killing PDF reads machine-wide.
#
# CONTRACT: always exits 0 (this is a report, not a gate). One line per check:
#   OK   <what>   -- healthy
#   WARN <what>   -- works, but probably not what you want
#   FAIL <what>   -- broken, with the blast radius named
# Ends with a one-line summary. Runtime: about 4 minutes (measured 3m44s to
# 4m10s in Nov 2026); the live test suites are nearly all of it.

CC="$HOME/.claude"
# Native-Windows Python cannot open Git Bash's /c/... paths; cygpath -m yields
# C:/... which both worlds accept. First live run FAILed on exactly this.
CCPY="$(cygpath -m "$CC" 2>/dev/null || echo "$CC")"
OK=0; WARN=0; FAIL=0

# Mac and Linux have no Windows `py` launcher: let every `py -3 ...` below mean python3.
if ! command -v py >/dev/null 2>&1; then
  py() { [ "$1" = "-3" ] && shift; python3 "$@"; }
fi

ok()   { OK=$((OK+1));     echo "OK   $1"; }
warn() { WARN=$((WARN+1)); echo "WARN $1"; }
fail() { FAIL=$((FAIL+1)); echo "FAIL $1"; }

# The daily-driver model this system is tuned for. Update when the standard
# changes (see TOOLS.md "Model split" for why this exact value).
EXPECTED_MODEL='claude-opus-5-5[1m]'

# --- 1. python (the guards' interpreter) -------------------------------------
# No python = every guard fails CLOSED = every Bash command blocked.
if command -v py >/dev/null 2>&1 && py -3 -c "pass" 2>/dev/null; then
  PYEXE=$(py -3 -c 'import sys;print(sys.executable)' 2>/dev/null | tr -d '\r')
  ok "python: py -3 resolves ($(py -3 -c 'import sys;print(sys.version.split()[0])' 2>/dev/null)) at $PYEXE"
  case "$PYEXE" in
    *Downloads*) warn "python: the interpreter every hook uses lives under a Downloads folder. Deleting that folder blocks every Bash command in every session (TOOLS.md, Machine hygiene). Leave it, or move Python deliberately and re-run /health" ;;
  esac
elif command -v python3 >/dev/null 2>&1 && python3 -c "pass" 2>/dev/null; then
  ok "python: python3 resolves"
else
  fail "python: neither py -3 nor python3 works -- ALL guards fail closed, every Bash command will be blocked"
fi

# --- 2. settings.json parses + model is the intended one ---------------------
MODEL=$(py -3 -c "
import json,sys
try:
    s=json.load(open('$CCPY/settings.json',encoding='utf-8'))
except Exception as e:
    print('PARSE-ERROR:'+str(e)); sys.exit()
print(s.get('model','<missing>'))
print('ARRAY' if isinstance(s.get('fallbackModel'),list) else 'NOT-ARRAY')
" 2>/dev/null | tr -d '\r')
MODEL_LINE=$(echo "$MODEL" | sed -n 1p)
FALLBACK_LINE=$(echo "$MODEL" | sed -n 2p)
case "$MODEL_LINE" in
  PARSE-ERROR:*) fail "settings.json does not parse: ${MODEL_LINE#PARSE-ERROR:}" ;;
  "$EXPECTED_MODEL") ok "model: $MODEL_LINE (the intended daily driver)" ;;
  "<missing>") ok "model: none pinned, so sessions use the plan's default model (friends' setup)" ;;
  opus*|sonnet*|haiku*|fable|default|opusplan)
    warn "model: '$MODEL_LINE' is a bare ALIAS -- aliases have resolved to older models before (opus[1m] -> Opus 4.8). Use the explicit id $EXPECTED_MODEL" ;;
  claude-fable-5*)
    warn "model: $MODEL_LINE -- Fable as the saved default burns Max usage far faster than Opus. Fine for one session, wrong as the default. Expected: $EXPECTED_MODEL" ;;
  *)
    warn "model: $MODEL_LINE (expected $EXPECTED_MODEL -- intentional?)" ;;
esac
[ "$FALLBACK_LINE" = "ARRAY" ] && ok "fallbackModel: array form (documented format)" \
  || warn "fallbackModel: not an array -- the documented form is an array of up to 3 ids"

# --- 3. every wired hook exists and is executable ----------------------------
MISSING=0; TOTAL=0
# tr -d '\r': Windows Python prints \r\n; bash word-splits on \n only, so
# without the strip every path carries an invisible \r and -x fails on all.
for f in $(py -3 -c "
import json
s=json.load(open('$CCPY/settings.json',encoding='utf-8'))
print('\n'.join(h['command'] for v in s.get('hooks',{}).values()
                for e in v for h in e.get('hooks',[])))" 2>/dev/null | tr -d '\r'); do
  TOTAL=$((TOTAL+1))
  g="${f/\$HOME/$HOME}"
  [ -x "$g" ] || { MISSING=$((MISSING+1)); fail "hook missing/not executable: $f"; }
done
[ "$MISSING" -eq 0 ] && [ "$TOTAL" -gt 0 ] && ok "hooks: all $TOTAL wired hook files present and executable"
[ "$TOTAL" -eq 0 ] && fail "hooks: none found in settings.json -- the guard layer is not wired at all"

# --- 4. guard logic answers correctly (live test, not just file presence) ----
if [ -f "$CC/hooks/tests/test-guard-tamper.py" ]; then
  SUITE=$(py -3 "$CC/hooks/tests/test-guard-tamper.py" 2>/dev/null | grep -E '^SUMMARY')
  case "$SUITE" in
    *"cases correct"*) ok "guards: live suite green (${SUITE#SUMMARY: })" ;;
    "") fail "guards: test suite produced no summary -- run it by hand: py -3 ~/.claude/hooks/tests/test-guard-tamper.py" ;;
    *) fail "guards: suite NOT clean ($SUITE)" ;;
  esac
else
  warn "guards: tests/test-guard-tamper.py not found -- guard logic unverified"
fi

# --- 4a. the backup lock: the backup never goes public, never gains a reader --
# FabGemYT/FabClaudeWorkflow and the public friends' copy have close names, and
# the friends' copy is flipped public/private on request. This suite proves no
# route can expose the backup, and that work on the friends' repo still runs.
if [ -f "$CC/hooks/tests/test-backup-lock.py" ]; then
  BL=$(py -3 "$CC/hooks/tests/test-backup-lock.py" 2>/dev/null | grep -E '^SUMMARY')
  if [ -z "$BL" ]; then
    fail "backup lock: the suite produced no summary. Run: py -3 ~/.claude/hooks/tests/test-backup-lock.py"
  elif echo "$BL" | grep -qE '([0-9]+)/\1 '; then
    ok "backup lock: ${BL#SUMMARY: }"
  else
    fail "backup lock: $BL -- the private backup could be made public, shared or pushed elsewhere"
  fi
else
  warn "backup lock: tests/test-backup-lock.py not found -- the backup's privacy is unverified"
fi

# --- 4b. do the guards still let daily work through? -------------------------
# The other half of the guard question, and the one that actually bit the owner: on
# 2026-08-07 a new Supabase guard blocked `db push`, `migration up`,
# `migration repair` and `functions deploy`, and a live session lost the ability
# to do work it had done the day before. A guard that blocks daily work gets
# disabled, which is worse than having no guard.
if [ -f "$CC/hooks/tests/test-routine-work.py" ]; then
  RW=$(py -3 "$CC/hooks/tests/test-routine-work.py" 2>/dev/null | grep -E '^SUMMARY')
  case "$RW" in
    *"$(echo "$RW" | grep -oE '[0-9]+/[0-9]+' | awk -F/ '$1==$2{print $0}')"*)
      [ -n "$RW" ] && ok "routine work: ${RW#SUMMARY: }" ;;
  esac
  if [ -z "$RW" ]; then
    fail "routine work: the suite produced no summary. Run: py -3 ~/.claude/hooks/tests/test-routine-work.py"
  elif ! echo "$RW" | grep -qE '([0-9]+)/\1 '; then
    fail "routine work: a guard is BLOCKING daily work ($RW). Either the guard is too broad, or the block is a deliberate decision that belongs in CLAUDE.md FOUNDATION"
  fi
fi

# --- 3b. recursive deletes: the replacement for four blanket deny rules ------
# Those rules fired ~190 times across 2.8 GB of transcripts, more than every
# other guard combined, and caught nothing dangerous. This suite asserts BOTH
# halves of the replacement: the root and unset-variable shapes still stop, and
# every real cleanup command from the transcripts still runs.
if [ -f "$CC/hooks/tests/test-delete-guard.py" ]; then
  DG=$(py -3 "$CC/hooks/tests/test-delete-guard.py" 2>/dev/null | grep -E '^SUMMARY')
  if [ -z "$DG" ]; then
    fail "delete guard: the suite produced no summary. Run: py -3 ~/.claude/hooks/tests/test-delete-guard.py"
  elif echo "$DG" | grep -qE '([0-9]+)/\1 '; then
    ok "delete guard: ${DG#SUMMARY: }"
  else
    fail "delete guard: $DG -- either a catastrophic delete is no longer blocked, or routine cleanup is being blocked again"
  fi
else
  warn "delete guard: tests/test-delete-guard.py not found -- the recursive-delete rules are unverified"
fi
# The destructive-SQL check WARNS, it never blocks (rewritten 2026-08-08 after it
# produced 3 of the 4 guard blocks that ever hit a real product, all false
# positives). The suite asserts both halves: real data loss warns, and the entire
# replace-an-object family stays silent.
if [ -f "$CC/hooks/tests/test-destructive-sql.py" ]; then
  DS=$(py -3 "$CC/hooks/tests/test-destructive-sql.py" 2>/dev/null | grep -E '^SUMMARY')
  echo "$DS" | grep -qE '([0-9]+)/\1 ' \
    && ok "destructive-SQL warn: ${DS#SUMMARY: }" \
    || fail "destructive-SQL warn: NOT clean ($DS)"
fi
# A guard that starts BLOCKING here is the regression this whole rewrite exists to
# prevent, so assert it separately rather than trusting the count above.
if py -3 - <<'PY' 2>/dev/null
import json, os, subprocess, sys
hook = os.path.expanduser("~/.claude/hooks/block-prod-deploy.sh")
cmd = "psql -c '%s profiles'" % " ".join(["DROP", "TABLE"])
p = subprocess.run(["bash", hook], capture_output=True, text=True,
                   input=json.dumps({"tool_name": "Bash",
                                     "tool_input": {"command": cmd},
                                     "cwd": "/tmp"}))
sys.exit(1 if p.returncode == 2 else 0)
PY
then
  ok "destructive-SQL: warns without blocking (zero friction preserved)"
else
  fail "destructive-SQL: it is BLOCKING again -- that is the regression; it must only warn"
fi

# --- 4b2. the Vercel surface -------------------------------------------------
# A `--prod` substring test blocked five READ-ONLY commands, which is how a
# session concluded production was off-limits, never found `vercel redeploy`, and
# handed the owner a manual dashboard click (2026-08-12). Reading is not deploying.
if [ -f "$CC/hooks/tests/test-vercel-surface.py" ]; then
  VS=$(py -3 "$CC/hooks/tests/test-vercel-surface.py" 2>/dev/null | grep -E '^SUMMARY')
  echo "$VS" | grep -qE '([0-9]+)/\1 ' \
    && ok "vercel surface: ${VS#SUMMARY: }" \
    || fail "vercel surface: NOT clean ($VS)"
else
  warn "vercel surface: tests/test-vercel-surface.py not found -- read-only commands unverified"
fi

# --- 4c. MCP route coverage --------------------------------------------------
# The gap this catches is COVERAGE, not logic: every blocking hook was wired to
# the Bash matcher alone, so `mcp__claude_ai_Supabase__execute_sql` carrying a
# DROP TABLE passed all five while the identical SQL through Bash was blocked
# (measured 2026-08-07). A green destructive-SQL suite could not see that.
if [ -f "$CC/hooks/tests/test-mcp-guard.py" ]; then
  MG=$(py -3 "$CC/hooks/tests/test-mcp-guard.py" 2>/dev/null | grep -E '^SUMMARY')
  echo "$MG" | grep -qE '([0-9]+)/\1 coverage' \
    && ok "MCP route: ${MG#SUMMARY: }" \
    || fail "MCP route: NOT clean ($MG)"
else
  warn "MCP route: tests/test-mcp-guard.py not found -- MCP coverage unverified"
fi
# The matcher itself must be registered, or the suite passes while nothing runs.
py -3 -c "
import json,os,sys
d=json.load(open(os.path.expanduser('~/.claude/settings.json'),encoding='utf-8'))
pre=d.get('hooks',{}).get('PreToolUse',[])
sys.exit(0 if any('mcp__' in (g.get('matcher') or '') for g in pre) else 1)
" 2>/dev/null \
  && ok "MCP route: PreToolUse matcher 'mcp__.*' is registered" \
  || fail "MCP route: NO PreToolUse hook matches mcp__* -- every MCP call is unguarded"

# --- 4c2. Supabase's SQL confirmation form is answered, money forms are not ---
# Since Claude Code advertised MCP form support (protocol 2026-07-28, 2.1.292 to
# 2.1.295) Supabase's hosted server asks before destructive-looking SQL. The
# owner settled that case on 2026-08-07/08: it runs, with a one-line note in
# chat from block-mcp-danger.sh. The Elicitation hook answers that one form.
# Cost confirmations (create_project, create_branch) must still reach the dialog.
if [ -f "$CC/hooks/tests/test-elicitation-answer.py" ]; then
  EA=$(py -3 "$CC/hooks/tests/test-elicitation-answer.py" 2>/dev/null | grep -E '^SUMMARY')
  echo "$EA" | grep -qE '([0-9]+)/\1 ' \
    && ok "supabase form: ${EA#SUMMARY: } (SQL confirmation answered, cost forms left to the dialog)" \
    || fail "supabase form: suite NOT clean ($EA)"
else
  warn "supabase form: tests/test-elicitation-answer.py not found -- the form hook is unverified"
fi
py -3 -c "
import json,os,sys
d=json.load(open(os.path.expanduser('~/.claude/settings.json'),encoding='utf-8'))
el=d.get('hooks',{}).get('Elicitation',[])
sys.exit(0 if any('upabase' in (e.get('matcher') or '') and any('answer-supabase-sql-confirm' in h.get('command','') for h in e.get('hooks',[])) for e in el) else 1)
" 2>/dev/null \
  && ok "supabase form: Elicitation hook is wired for the Supabase server" \
  || warn "supabase form: NO Elicitation hook for Supabase in settings.json -- every destructive-looking statement will stop for an Accept tap"

# --- 4c3. background work survives low memory --------------------------------
# Claude Code stops an idle session's background commands when Windows reports
# critical memory pressure. The docs say Windows has no such signal; the code
# (2.1.312) acts on it as is, and between 9 Sep and 29 Oct 2026 it stopped this
# machine's builds, test runs, a dependency reinstall and timers 32 times, while
# the stopped timers kept running anyway. The env switch turns it off. Claude
# reads it each time a background command starts, so a save applies at once.
REAP=$(py -3 -c "
import json
s=json.load(open(r'$CCPY/settings.json',encoding='utf-8'))
print((s.get('env') or {}).get('CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP',''))" 2>/dev/null | tr -d '\r')
[ "$REAP" = "1" ] \
  && ok "low memory: background commands are never stopped by the memory reaper (CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1)" \
  || warn "low memory: CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP is not 1 in settings.json env -- Claude can stop background builds and timers again when memory runs low"

# --- 4c4. the leftover sweep: wired, working, and actually running -----------
# On Windows the programs inside a stopped or timed-out command keep running
# (TOOLS.md, Machine hygiene). hooks/sweep-leftovers.sh runs bin/claude-cleanup.ps1
# on SessionStart and Stop. It can stop working three silent ways: unwired, the
# script unable to read this machine, or never firing. The dry run below closes
# nothing; its full test suite is hooks/tests/test-sweep-leftovers.py.
SW=$(py -3 -c "
import json
s=json.load(open(r'$CCPY/settings.json',encoding='utf-8'))
h=s.get('hooks') or {}
w=lambda ev: any('sweep-leftovers.sh' in x.get('command','') and x.get('async') for e in h.get(ev,[]) for x in e.get('hooks',[]))
print('%s|%s' % (w('SessionStart'), w('Stop')))" 2>/dev/null | tr -d '\r')
if ! command -v powershell.exe >/dev/null 2>&1; then
  ok "leftover sweep: a Windows-only job; nothing to sweep on this machine"
elif [ "$SW" != "True|True" ]; then
  warn "leftover sweep: not wired as a background hook on both SessionStart and Stop ($SW) -- leftover processes pile up until someone ends them in Task Manager"
elif [ ! -f "$CC/bin/claude-cleanup.ps1" ]; then
  fail "leftover sweep: wired, but bin/claude-cleanup.ps1 is missing -- every sweep silently does nothing"
else
  DRY=$(powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$(cygpath -w "$CC/bin/claude-cleanup.ps1")" -Json 2>/dev/null \
    | py -3 -c "
import json,sys
t=sys.stdin.read(); t=t[t.find('{'):] if '{' in t else ''
try: d=json.loads(t)
except Exception: print('ERR|unreadable output'); raise SystemExit
if d.get('error'): print('ERR|'+d['error']); raise SystemExit
g=d.get('groups') or []
print('OK|%d|%d|%d' % (d.get('live_sessions',0), len([x for x in g if x.get('decision')=='close']), len([x for x in g if x.get('decision')=='keep'])))" 2>/dev/null | tr -d '\r')
  LAST=$(py -3 -c "
import json,datetime
try: d=json.load(open(r'$CCPY/state/cleanup-last-run.json',encoding='utf-8-sig'))
except Exception: print('never'); raise SystemExit
age=(datetime.datetime.now()-datetime.datetime.fromisoformat(d['time'])).total_seconds()/3600
print('%.1f|%s|%s|%s|%s' % (age, d.get('trigger'), d.get('closed'), d.get('error') or '', d.get('slept', 0)))" 2>/dev/null | tr -d '\r')
  IFS='|' read -r DS DLIVE DCLOSE DKEEP <<EOF_SWEEP
$DRY
EOF_SWEEP
  IFS='|' read -r LAGE LTRIG LCLOSED LERR LSLEPT <<EOF_LAST
$LAST
EOF_LAST
  if [ "$DS" != "OK" ]; then
    fail "leftover sweep: claude-cleanup.ps1 cannot read this machine (${DLIVE:-no output}) -- it closes nothing, so leftovers pile up again"
  elif [ "$LAST" = "never" ]; then
    warn "leftover sweep: wired and working ($DLIVE open sessions seen), but it has never run -- it starts with the next session start or reply"
  elif [ -n "$LERR" ]; then
    warn "leftover sweep: the last sweep (${LAGE}h ago, $LTRIG) hit an error and closed nothing: $LERR"
  elif awk "BEGIN{exit !($LAGE > 48)}"; then
    warn "leftover sweep: wired and working, but the last sweep was ${LAGE}h ago -- the hooks may not be firing"
  else
    ok "leftover sweep: last ran ${LAGE}h ago ($LTRIG, closed $LCLOSED, put ${LSLEPT:-0} idle TypeScript server(s) to sleep); right now $DCLOSE leftover(s) waiting, $DKEEP of Claude's kept as in use, $DLIVE open sessions"
  fi
fi

# --- 4d. Search Console: credential live, and every site actually granted -----
# Two separate failure modes. The key can be present and valid while a NEW site
# has never been shared with the service account, which is silent: queries for
# that domain just fail. The tool compares Vercel's live domains against what the
# service account can actually read, so a sixth site reports itself.
if [ -f "$CC/bin/gsc.py" ] && [ -n "$GSC_SERVICE_ACCOUNT_PATH" ]; then
  GSC_OUT=$(py -3 "$CC/bin/gsc.py" properties 2>&1)
  if echo "$GSC_OUT" | grep -q "NOT YET SHARED"; then
    MISS=$(echo "$GSC_OUT" | sed -n '/NOT YET SHARED/,/^$/p' | grep -cE '^   [a-z0-9-]+\.')
    warn "search console: $MISS site(s) not shared with the service account -- run: py -3 ~/.claude/bin/gsc.py properties"
  elif echo "$GSC_OUT" | grep -q "sc-domain:"; then
    ok "search console: $(echo "$GSC_OUT" | grep -c 'sc-domain:') properties readable, all live sites covered"
  else
    fail "search console: credential set but no properties readable ($(echo "$GSC_OUT" | head -1))"
  fi
elif [ -f "$CC/bin/gsc.py" ]; then
  warn "search console: bin/gsc.py present but GSC_SERVICE_ACCOUNT_PATH not in the session env"
fi

# --- 4e. the credential loader, and the live env file ------------------------
# On 2026-08-16 this hook wedged a whole session: it appended without truncating,
# SessionStart fires on startup/resume/clear/compact, 16 exports x 7 firings =
# 112 lines, and one torn write left an unterminated quote. Claude Code inlines
# that file into every `bash -c`, so EVERY command died at parse time, including
# `echo ok`. Two checks, because they fail differently.
if [ -f "$CC/hooks/tests/test-load-env.py" ]; then
  LE=$(py -3 "$CC/hooks/tests/test-load-env.py" 2>/dev/null | grep -E '^SUMMARY')
  echo "$LE" | grep -qE '([0-9]+)/\1 ' \
    && ok "credential loader: ${LE#SUMMARY: }" \
    || fail "credential loader: NOT clean ($LE) -- idempotency or self-heal is broken"
else
  warn "credential loader: tests/test-load-env.py not found -- the 112-line wedge is unguarded"
fi
# The live file this session is actually using. A bloated or unparseable one is
# the symptom that reaches the user as "every Bash command suddenly fails".
if [ -n "$CLAUDE_ENV_FILE" ] && [ -f "$CLAUDE_ENV_FILE" ]; then
  ENV_LINES=$(wc -l < "$CLAUDE_ENV_FILE" 2>/dev/null | tr -d ' ')
  ENV_DUPES=$(grep -c '^# >>> claude-env begin' "$CLAUDE_ENV_FILE" 2>/dev/null | tr -d ' ')
  if ! sh -n "$CLAUDE_ENV_FILE" 2>/dev/null; then
    fail "session env file does NOT parse -- every Bash call in this session will die. Fix: /compact (fires SessionStart, which self-heals it)"
  elif [ "${ENV_DUPES:-0}" -gt 1 ] 2>/dev/null; then
    fail "session env file has $ENV_DUPES credential blocks -- the loader is appending again, which is the 112-line wedge returning"
  else
    ok "session env file: $ENV_LINES lines, 1 credential block, parses"
  fi
fi

# --- 5. PDF reading (poppler) ------------------------------------------------
command -v pdftoppm >/dev/null 2>&1 \
  && ok "pdf: poppler present ($(pdftoppm -v 2>&1 | head -1 | grep -oE '[0-9.]+' | head -1))" \
  || fail "pdf: pdftoppm missing -- NO session on this machine can read PDFs. Fix: scoop install poppler"

# --- 6. session context window ----------------------------------------------
# Only meaningful when run inside a session: the harness exports the
# auto-compact threshold while a 1M window is live.
if [ "$MODEL_LINE" = "<missing>" ]; then
  ok "session window: whatever the plan's default model gives (no 1M model pinned)"
elif [ -n "$CLAUDE_CODE_AUTO_COMPACT_WINDOW" ]; then
  ok "session window: 1M context live in this session (auto-compact at $CLAUDE_CODE_AUTO_COMPACT_WINDOW)"
else
  warn "session window: no 1M marker in this session's env -- if the statusline lacks '(1M context)', this session is on a 200k window"
fi

# --- 7. backup repo state ----------------------------------------------------
if git -C "$CC" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  BR=$(git -C "$CC" branch --show-current)
  DIRTY=$(git -C "$CC" status --porcelain | wc -l | tr -d ' ')
  if [ "$BR" = "main" ] && [ "$DIRTY" -gt 0 ]; then
    warn "repo: sitting on main with $DIRTY uncommitted file(s) -- work belongs on a fresh task branch"
  else
    ok "repo: branch '$BR', $DIRTY uncommitted file(s)"
  fi
elif [ -f "$CC/.friends-setup" ]; then
  ok "setup: installed from the friends' setup (updates: say \"update my setup\")"
else
  fail "repo: ~/.claude is not a git repo -- the backup layer is gone"
fi

# --- 8. GitHub auth ----------------------------------------------------------
timeout 6 gh auth status >/dev/null 2>&1 \
  && ok "github: gh authenticated" \
  || warn "github: gh auth check failed or timed out -- PRs and pushes may fail"

# --- 9. no-em-dash rule ------------------------------------------------------
DASHES=$(grep -o $'—' "$CC/CLAUDE.md" "$CC/TOOLS.md" 2>/dev/null | wc -l | tr -d ' ')
[ "$DASHES" -eq 0 ] && ok "style: 0 em-dashes in CLAUDE.md/TOOLS.md" \
  || warn "style: $DASHES em-dash(es) in CLAUDE.md/TOOLS.md -- the house rule says none"

# --- 10. secrets loader ------------------------------------------------------
[ -f "$CC/.env.local" ] && ok "secrets: .env.local present for the SessionStart loader" \
  || warn "secrets: ~/.claude/.env.local missing -- wired credentials will not auto-load"

# --- 11. secrets map matches reality -----------------------------------------
# The map is what stops sessions re-asking for credentials the user already gave.
# A map that has drifted from disk is worse than none: it sends sessions to the
# wrong place, they find nothing, and they ask the user again. That exact drift
# (RevenueCat key documented in .env.local, actually in secrets/) is why this
# check exists. Existence only -- no value is ever read.
MAP="$CC/rules/secrets-map.md"
if [ ! -f "$MAP" ]; then
  warn "secrets map: rules/secrets-map.md missing -- sessions have no index and will re-ask for known credentials"
else
  DRIFT=0
  # Every file the map claims lives in ~/.claude/secrets/ must actually be there.
  for want in $(grep -oE '`[A-Za-z0-9_.-]+\.(p8|json|txt)`' "$MAP" | tr -d '`' | sort -u); do
    [ -f "$CC/secrets/$want" ] || { DRIFT=$((DRIFT+1)); fail "secrets map: claims ~/.claude/secrets/$want but it is not there"; }
  done
  # Every account-level name the map lists must be loadable from .env.local.
  for want in APPLE_KEY_ID APPLE_ISSUER_ID APPLE_TEAM_ID APPLE_P8_PATH GOOGLE_SERVICE_ACCOUNT_PATH; do
    grep -qF "$want" "$MAP" || continue   # only names this machine's map actually lists
    grep -qE "^$want=." "$CC/.env.local" 2>/dev/null || { DRIFT=$((DRIFT+1)); fail "secrets map: $want listed as wired but missing/empty in ~/.claude/.env.local"; }
  done
  # Untracked files sitting in secrets/ that the map never mentions.
  for have in $(ls "$CC/secrets/" 2>/dev/null); do
    grep -qF "$have" "$MAP" || { DRIFT=$((DRIFT+1)); warn "secrets map: ~/.claude/secrets/$have exists but is not in the map -- add it or a session will not know it is there"; }
  done
  [ "$DRIFT" -eq 0 ] && ok "secrets map: every documented credential matches disk"
fi

# --- 11b. effort config: the silent-discard and ultracode-block traps --------
# Both bit this system. `effortLevel: "max"` is silently DISCARDED (the schema
# enum ends at xhigh), and CLAUDE_CODE_EFFORT_LEVEL set to anything other than
# xhigh disables ultracode entirely while looking like it worked.
#
# Since 2.1.280 the top-level effortLevel in USER settings no longer applies to
# Opus 5.5 or anything newer: those start at their own default (medium for Opus
# 5.5) unless modelSettings.<canonical model>.effortLevel names a level. The
# canonical name (claude-opus-5-5) also covers the [1m] variant. Measured
# 2026-10-10: three weeks of Opus 5.5 sessions had run at medium while this
# check reported xhigh as fine.
EFFORT=$(py -3 -c "
import json,sys,re
try: s=json.load(open(r'$CCPY/settings.json',encoding='utf-8'))
except Exception: print('ERR|ERR|ERR|ERR'); raise SystemExit
m=re.sub(r'\[1m\]$','',s.get('model',''))
ms=(s.get('modelSettings') or {}).get(m) or {}
print('%s|%s|%s|%s' % (s.get('effortLevel','<unset>'), (s.get('env') or {}).get('CLAUDE_CODE_EFFORT_LEVEL',''), m, ms.get('effortLevel','<unset>')))
" 2>/dev/null | tr -d '\r')
IFS='|' read -r EL EENV EMODEL EPM <<EOF_EFFORT
$EFFORT
EOF_EFFORT
case "$EL" in
  low|medium|high|xhigh) ok "effort: effortLevel '$EL' is schema-legal and persists (applies to Opus 5, Fable 5.1 and older)" ;;
  ERR) ;;
  *) fail "effort: effortLevel '$EL' is outside the schema enum (low|medium|high|xhigh) and is SILENTLY DISCARDED -- the setting does nothing" ;;
esac
case "$EMODEL" in
  claude-opus-5-5*|claude-sonnet-5-5*|claude-haiku-5-5*)
    case "$EPM" in
      low|medium|high|xhigh) ok "effort: modelSettings.$EMODEL.effortLevel '$EPM' is what $EMODEL actually starts at" ;;
      *) warn "effort: $EMODEL IGNORES the top-level effortLevel and has no modelSettings entry, so every session starts at its own default (medium). Add modelSettings.$EMODEL.effortLevel or run /effort <level> and press Enter once" ;;
    esac ;;
esac
if [ -n "$EENV" ]; then
  if [ "$EENV" = "xhigh" ]; then
    warn "effort: CLAUDE_CODE_EFFORT_LEVEL=xhigh pins every session; harmless but redundant with effortLevel"
  else
    fail "effort: CLAUDE_CODE_EFFORT_LEVEL='$EENV' pins every session AND disables ultracode entirely. Policy is per-session /effort; remove this key from the settings env block"
  fi
else
  ok "effort: no env override, so /effort max and /effort ultracode both work per session"
fi

# --- 11c. does hooks.json still mirror the live wiring? ----------------------
# hooks.json is the plugin-distribution copy; if it drifts, anyone installing
# this as a plugin gets a different guard set than the author runs.
if [ -f "$CC/hooks/hooks.json" ]; then
  LIVE=$(py -3 -c "
import json
s=json.load(open(r'$CCPY/settings.json',encoding='utf-8'))
print(len([h for v in (s.get('hooks') or {}).values() for e in v for h in e.get('hooks',[])]))" 2>/dev/null | tr -d '\r')
  DIST=$(py -3 -c "
import json
d=json.load(open(r'$CCPY/hooks/hooks.json',encoding='utf-8'))
h=d.get('hooks',d)
print(len([x for v in h.values() for e in v for x in e.get('hooks',[])]))" 2>/dev/null | tr -d '\r')
  if [ "$LIVE" = "$DIST" ]; then
    ok "hooks.json: distribution copy matches the live wiring ($LIVE hooks)"
  else
    warn "hooks.json: distribution copy has $DIST hooks but settings.json wires $LIVE -- a plugin install would get a different guard set"
  fi
fi

# --- 12. autonomy surface: can Claude actually reach these itself? -----------
# Every miss here is a task that gets handed BACK to the user as homework,
# which is the failure mode this system exists to prevent.
if grep -qE '^SUPABASE_ACCESS_TOKEN=.+' "$CC/.env.local" 2>/dev/null; then
  ok "supabase: access token set (CLI authenticated + Management API reachable)"
else
  fail "supabase: SUPABASE_ACCESS_TOKEN empty -- the CLI is NOT logged in and the Management API is unreachable, so auth/SMTP/backup config becomes user homework. Create at supabase.com/dashboard/account/tokens"
fi
for c in gcloud firebase gh vercel; do
  command -v "$c" >/dev/null 2>&1 \
    && ok "cli: $c present" \
    || fail "cli: $c missing -- work that needs it gets handed back to the user"
done
# The browser is the universal fallback for dashboard-only tasks (Cloud Console
# OAuth clients have no API at all). Not connectable from a script, so this is a
# reminder of the launcher rather than a live probe.
[ -x "$CC/bin/claude-chrome" ] \
  && ok "browser: claude-chrome launcher present (start sessions with it for dashboard work)" \
  || warn "browser: bin/claude-chrome missing -- console-only tasks have no path and become homework"

# --- 13. is the backup actually a 1:1 restore? ------------------------------
# This repo exists for exactly one purpose: `git clone` it and get this whole
# system back. Every failure below is SILENT -- the push succeeds, the repo
# looks populated on GitHub, and the gap only appears at restore time, which is
# the one moment it cannot be fixed.
#
# Found the hard way on 2026-08-16: skills/store-screenshots was committed as a
# GITLINK (mode 160000) because it had a nested .git. GitHub renders it as a
# normal-looking folder; a clone gets it EMPTY. 20 files, 0 restored, no error
# at any point.
if [ -d "$CC/.git" ]; then
  # 13a. gitlinks: the silent-empty-folder case.
  GL=$(cd "$CC" && git ls-files -s 2>/dev/null | awk '$1=="160000"{print $4}')
  if [ -n "$GL" ]; then
    for g in $GL; do
      fail "backup: '$g' is a gitlink (mode 160000) -- it clones EMPTY, so a restore silently loses it. Fix: git rm --cached '$g'; move its nested .git aside; git add '$g'"
    done
  else
    ok "backup: no gitlinks -- every tracked path restores with real content"
  fi

  # 13b. nested .git dirs are what CREATE a gitlink on the next `git add`.
  # Catching them here means the next one is caught before it is committed.
  NESTED=$(cd "$CC" && find . -mindepth 2 -name .git -prune -print 2>/dev/null)
  if [ -n "$NESTED" ]; then
    for n in $NESTED; do
      warn "backup: nested repo at '${n%/.git}' -- committing it would create a gitlink that clones empty. Vendor the files or record it in skills/SOURCES.md and gitignore it"
    done
  else
    ok "backup: no nested repos that could become gitlinks"
  fi

  # 13c. a file that exists here but is neither tracked nor ignored is simply
  # not in the backup. Warn, not fail: mid-edit files are legitimate.
  UNTRACKED=$(cd "$CC" && git status --porcelain --untracked-files=all 2>/dev/null | grep -c '^??')
  [ "${UNTRACKED:-0}" -eq 0 ] \
    && ok "backup: nothing untracked-and-unignored (no file is missing from the backup)" \
    || warn "backup: $UNTRACKED file(s) neither tracked nor ignored -- they exist here but would NOT come back from a clone"

  # 13d. committed but never pushed is a backup that only exists on this laptop.
  UP=$(cd "$CC" && git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null)
  if [ -n "$UP" ]; then
    AHEAD=$(cd "$CC" && git rev-list --count "$UP..HEAD" 2>/dev/null)
    [ "${AHEAD:-0}" -eq 0 ] \
      && ok "backup: pushed -- GitHub has everything this machine has" \
      || warn "backup: $AHEAD commit(s) not pushed to $UP -- that work exists only on this laptop"

    # 13e. merged on GitHub but not live here. Sessions add lessons through PRs the
    # owner merges on GitHub; on 2026-10-30 PR #73 had sat merged-but-not-live for two
    # days because nothing pulled it. hooks/sync-harness.sh now syncs at session start;
    # this catches what it had to leave alone (its reason is in state/harness-sync.log).
    (cd "$CC" && GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=never timeout 20 git fetch -q origin 2>/dev/null)
    BEHIND=$(cd "$CC" && git rev-list --count "HEAD..$UP" 2>/dev/null)
    if [ "${BEHIND:-0}" -gt 0 ] 2>/dev/null; then
      WAITING=$(cd "$CC" && git log --no-merges --format=%s "HEAD..$UP" 2>/dev/null | head -3 | paste -sd ';' -)
      WHY=$(grep -a 'left alone' "$CC/state/harness-sync.log" 2>/dev/null | tail -1 | cut -c21-)
      warn "backup: this laptop is $BEHIND commit(s) behind GitHub -- merged harness changes are not live yet ($WAITING)${WHY:+. The session-start sync said: $WHY}"
    else
      ok "backup: up to date with GitHub -- every merged harness change is live here"
    fi
  fi
fi

# --- 13f. the friends' copy: did the last automatic update reach them? -------
# After every merge, .github/workflows/share-to-friends.yml rebuilds the public
# friends' copy (FabGemYT/FabFriendsClaudeSetup), scans it and tests it, and
# publishes only when all of that passes. A failed run is safe (nothing personal
# goes out) but friends silently miss the merge, so it is surfaced here.
if [ -d "$CC/.git" ] && git -C "$CC" remote get-url origin 2>/dev/null | grep -qi 'FabGemYT/FabClaudeWorkflow'; then
  RUN=$(timeout 20 gh run list -R FabGemYT/FabClaudeWorkflow --workflow share-to-friends.yml --branch main --limit 1     --json status,conclusion,createdAt --jq '.[0] | "\(.status)|\(.conclusion)|\(.createdAt)"' 2>/dev/null)
  case "$RUN" in
    "") warn "friends' copy: no share-to-friends run on main yet (the first one runs after the merge that adds it)" ;;
    "completed|success|"*) ok "friends' copy: the last update after a merge published cleanly (${RUN##*|})" ;;
    completed*) fail "friends' copy: the last update did NOT publish (${RUN#completed|}) -- friends did not get the latest merge, and nothing personal went out. Details: gh run list -R FabGemYT/FabClaudeWorkflow --workflow share-to-friends.yml" ;;
    *) ok "friends' copy: an update is running right now" ;;
  esac
fi

echo ""
echo "SUMMARY: $OK ok, $WARN warn, $FAIL fail"
[ "$FAIL" -gt 0 ] && echo "Something above is genuinely broken. Each FAIL line names its blast radius."
[ "$FAIL" -eq 0 ] && [ "$WARN" -eq 0 ] && echo "All clean. Nothing is silently broken."
exit 0
