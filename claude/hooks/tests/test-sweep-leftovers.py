"""The leftover sweep closes real leftovers and nothing that is still in use.

WHY THIS FILE EXISTS
--------------------
On Windows, when Claude stops a background command, a command times out, or a
session closes, the programs inside the shell keep running (measured 2026-10-29
on Claude Code 2.1.312; anthropics/claude-code #91523, #92583, #97752 are open).
bin/claude-cleanup.ps1 closes them from the SessionStart and Stop hooks. A
cleanup that closes the wrong thing is worse than none, so every case here is a
REAL process put in a known state: orphaned or not, inside an open or a closed
project, connected or not. The script is asked what it would do, then made to
close, and the survivors are checked by looking at the process table again.

Sessions here stay open for days, so the script also puts an IDLE session's
TypeScript language server to sleep (Claude Code restarts it on next use) and
must leave everything else of that session alone. Three fake sessions (a renamed
node.exe as claude.exe, each owning a language server and an MCP-like helper,
listed in a temp registry) check that only the 3-hour idle one loses its language
server, never its helper, and that busy and 1-hour-idle sessions keep theirs.

The closing runs are restricted to this run's own markers (-OnlyMarker), so the
suite never touches anything else on the machine. The markers are unmistakable
(`swtest` plus six random digits, and the same digits after `0.` for the timers),
and the final tidy-up only stops the four kinds of process the suite starts. Its
log goes to a temp folder, not ~/.claude/state. Everything it started is stopped
at the end, pass or fail.

Run:  py -3 test-sweep-leftovers.py      (about 20 seconds; run it from inside a session)
Env:  CLEANUP_UNDER_TEST=/path/to/claude-cleanup.ps1 to test a staged copy.
"""
import glob
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

CC = os.path.expanduser("~/.claude")
SCRIPT = os.environ.get("CLEANUP_UNDER_TEST") or os.path.join(CC, "bin", "claude-cleanup.ps1")
GIT_BASH = None
for root in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", ""),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
    if root and os.path.exists(os.path.join(root, "Git", "usr", "bin", "bash.exe")):
        GIT_BASH = os.path.join(root, "Git", "usr", "bin", "bash.exe")
        break
NODE = shutil.which("node")
RUN = str(random.randint(100000, 999999))
MARK_NATIVE = "swtest" + RUN                     # in every node case's command line
MARK_TIMER = "0." + RUN                          # sleep only takes numbers: `sleep 1000000 0.<RUN><case>`
MARK_IDLE = "swidle" + RUN                      # the idle-session cases (their own registry)
STARTED_KINDS = ("sleep.exe", "bash.exe", "node.exe", "sh.exe", "claude.exe")   # claude.exe = the fake one below
STATE = tempfile.mkdtemp(prefix="sweep-test-")
# Idle-session cases need a process NAMED claude.exe that owns a language server and a
# helper. A copy of node.exe under that name, in a temp folder, plays the session; its
# registry file lives in a temp sessions folder (CLAUDE_CLEANUP_SESSIONS_DIR). A real
# claude.exe is never touched: the marker is in no real command line, and the tidy-up
# below only stops pids this run started.
FAKE = tempfile.mkdtemp(prefix="sweep-fake-session-")
FAKE_SESSIONS = os.path.join(FAKE, "sessions")
FAKE_SCRIPT = ("const {spawn}=require('child_process');const node=process.argv[1],tag=process.argv[2];"
               "const o={stdio:'ignore',windowsHide:true};"
               "spawn(node,['-e','setInterval(()=>{},1000)','typescript-language-server','--stdio',tag],o);"
               "spawn(node,['-e','setInterval(()=>{},1000)','chrome-devtools-mcp',tag],o);"
               "setInterval(()=>{},1000)")
DETACHED = 0x00000008 | 0x00000200               # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
TIMER_CASES = (1, 2, 3, 4)


def tag(case):
    return (MARK_TIMER if case in TIMER_CASES else MARK_NATIVE) + str(case)


def open_project():
    """An open session's folder from Claude Code's registry, whose parent is a real project home."""
    profile = os.environ.get("USERPROFILE", "").rstrip("\\").lower()
    for f in sorted(glob.glob(os.path.join(CC, "sessions", "*.json"))):
        try:
            s = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        cwd, pid = (s.get("cwd") or "").rstrip("\\"), s.get("pid")
        parent = os.path.dirname(cwd)
        if not cwd or not pid or len(parent) <= 3 or parent.lower() == profile:
            continue
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH"], capture_output=True, text=True).stdout
        if "claude" in out.lower():
            return cwd
    return None


def fake_session(tag, status, idle_hours):
    """A fake open session: claude.exe (renamed node) with a language server and an MCP-like helper."""
    exe = os.path.join(FAKE, "claude.exe")
    if not os.path.exists(exe):
        shutil.copy2(NODE, exe)
        os.makedirs(FAKE_SESSIONS, exist_ok=True)
    p = subprocess.Popen([exe, "-e", FAKE_SCRIPT, NODE, tag], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
    with open(os.path.join(FAKE_SESSIONS, "%d.json" % p.pid), "w", encoding="utf-8") as fh:
        json.dump({"pid": p.pid, "sessionId": str(uuid.uuid4()), "cwd": r"~/projects/__sweep_fake__",
                   "name": "fake " + tag, "status": status,
                   "statusUpdatedAt": int((time.time() - idle_hours * 3600) * 1000)}, fh)
    return p


def child_alive(tag, word):
    """Is the fake session's node child whose command line carries `word` still running?
    (The fake claude.exe's own command line holds the same words, so match node.exe only.)"""
    return any(name.lower() == "node.exe" and word in cmd for name, cmd in procs_with(tag).values())


def sweep(*args, sessions=None):
    env = dict(os.environ, CLAUDE_CLEANUP_STATE_DIR=STATE)
    if sessions:
        env["CLAUDE_CLEANUP_SESSIONS_DIR"] = sessions
    out = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                          "-File", SCRIPT, "-Json", "-Trigger", "test"] + list(args),
                         capture_output=True, text=True, env=env, timeout=120)
    text = out.stdout.strip()
    try:
        return json.loads(text[text.index("{"):]) if text else {}
    except ValueError:
        print("unparseable output:\n" + text[:2000] + "\n" + out.stderr[:1000])
        return {}


def procs_with(*markers):
    """{pid: (name, commandline)} for the suite's own kinds of process carrying a marker."""
    cond = " -or ".join("$_.CommandLine -like '*%s*'" % m for m in markers)
    kinds = ",".join("'%s'" % k for k in STARTED_KINDS)
    ps = ("Get-CimInstance Win32_Process | Where-Object { (%s) -and @(%s) -contains $_.Name.ToLower() } | "
          "ForEach-Object { '{0}|{1}|{2}' -f $_.ProcessId, $_.Name, $_.CommandLine }" % (cond, kinds))
    out = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
                         capture_output=True, text=True, timeout=60).stdout
    res = {}
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3 and parts[0].isdigit():
            res[int(parts[0])] = (parts[1], parts[2])
    return res


def alive(case):
    return bool(procs_with(tag(case)))


def orphan_native(argv):
    """Start argv from a middleman that exits at once, so its parent is gone."""
    code = ("import subprocess,sys,json;"
            "subprocess.Popen(json.loads(sys.argv[1]),creationflags=%d,stdin=subprocess.DEVNULL,"
            "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)" % DETACHED)
    subprocess.run([sys.executable, "-I", "-c", code, json.dumps(argv)], timeout=30)


def git_bash(script, wait):
    p = subprocess.Popen([GIT_BASH, "-c", script], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if wait:
        p.wait(timeout=20)
    return p


def verdict_for(report, case):
    for g in report.get("groups") or []:
        if any(tag(case) in (c or "") for c in g.get("cmds") or []):
            return g
    return None


def main():
    if not os.path.exists(SCRIPT):
        print("SUMMARY: cleanup script not found at %s" % SCRIPT)
        return 1
    if not GIT_BASH or not NODE:
        print("SUMMARY: needs Git Bash and node on this machine (bash=%s node=%s)" % (GIT_BASH, NODE))
        return 1
    live = open_project()
    if not live:
        print("SUMMARY: no open Claude session found in ~/.claude/sessions; run this from inside a session")
        return 1
    closed_dir = os.path.join(os.path.dirname(live), "__sweep_test_closed__")
    live_posix = "/" + live[0].lower() + live[2:].replace("\\", "/")
    idle = "setInterval(()=>{},1000)"
    server = ("const n=require('net');const s=n.createServer(c=>c.on('data',()=>{}))"
              ".listen(0,'127.0.0.1',()=>{n.connect(s.address().port,'127.0.0.1').on('error',()=>{})});"
              "setInterval(()=>{},1000)")
    markers = MARK_NATIVE + "," + MARK_TIMER

    cases = [
        # (case, what it is, expected decision, expected reason fragment, expected class)
        (1, "a timer whose shell is gone (the a live web game alarms)", "close", "shell is gone", "bare-tool"),
        (2, "a timer whose shell is still waiting on it", None, None, None),
        (3, "a detached loop inside an open project", "keep", "still open", "project"),
        (4, "a detached loop outside every open project", "close", "no open session", "project"),
        (5, "a leftover server in a project nobody has open", "close", "no open session", "project"),
        (6, "a leftover server inside an open project", "keep", "still open", "project"),
        (7, "an orphaned TypeScript server (a helper), even inside an open project", "close", "helper", "helper"),
        (8, "a leftover server something is connected to", "keep", "connected", "project"),
        (9, "an orphan that is not Claude's", "keep", "not traceable", "project"),
    ]
    started = []
    failures = []
    try:
        git_bash("sleep 1000000 %s & exit 0" % tag(1), wait=True)
        started.append(git_bash("sleep 1000000 %s; true" % tag(2), wait=False))
        git_bash("(cd '%s' && while true; do sleep 1000000 %s; done) & exit 0" % (live_posix, tag(3)), wait=True)
        git_bash("(cd /tmp && while true; do sleep 1000000 %s; done) & exit 0" % tag(4), wait=True)
        orphan_native([NODE, "-e", idle, os.path.join(closed_dir, tag(5))])
        orphan_native([NODE, "-e", idle, os.path.join(live, "__sweep_test_open__", tag(6))])
        orphan_native([NODE, "-e", idle, os.path.join(live, "node_modules", "typescript", "lib", "tsserver.js"), tag(7)])
        orphan_native([NODE, "-e", server, os.path.join(closed_dir, tag(8))])
        orphan_native([NODE, "-e", idle, os.path.join("C:\\", "SomewhereElse", tag(9))])
        time.sleep(2)

        report = sweep("-MinAgeMinutes", "0", "-OnlyMarker", markers)
        if report.get("error"):
            failures.append("script error: %s" % report.get("error"))
        for case, what, decision, reason, cls in cases:
            v = verdict_for(report, case)
            if decision is None:
                ok = v is None or v.get("decision") == "keep"
                got = "not listed" if v is None else "%s (%s)" % (v.get("decision"), v.get("reason"))
            else:
                ok = v is not None and v.get("decision") == decision and reason in (v.get("reason") or "") and v.get("class") == cls
                got = "missing" if v is None else "%s [%s] (%s)" % (v.get("decision"), v.get("class"), v.get("reason"))
            print("%-5s case %d: %s -> %s" % ("ok" if ok else "FAIL", case, what, got))
            if not ok:
                failures.append("case %d" % case)

        young = verdict_for(sweep("-MinAgeMinutes", "60", "-OnlyMarker", markers), 5)
        ok = young is not None and young.get("decision") == "keep" and "younger" in (young.get("reason") or "")
        print("%-5s too new: a leftover younger than the grace period is kept -> %s" % ("ok" if ok else "FAIL", young and young.get("reason")))
        if not ok:
            failures.append("grace period")

        braked = sweep("-Force", "-MinAgeMinutes", "0", "-MaxGroups", "1", "-OnlyMarker", markers)
        ok = braked.get("braked") is True and not braked.get("closed") and alive(1) and alive(5)
        print("%-5s brake: more candidates than -MaxGroups closes nothing -> braked=%s closed=%s" % ("ok" if ok else "FAIL", braked.get("braked"), braked.get("closed")))
        if not ok:
            failures.append("brake")

        sweep("-Force", "-MinAgeMinutes", "0", "-OnlyMarker", markers)
        time.sleep(1)
        for case, what, decision, _, _ in cases:
            should_live = decision != "close"
            is_alive = alive(case)
            ok = is_alive == should_live
            print("%-5s after closing: case %d should be %s -> %s" % ("ok" if ok else "FAIL", case, "kept" if should_live else "closed",
                                                                    "alive" if is_alive else "gone"))
            if not ok:
                failures.append("after closing, case %d" % case)
        log_path, last_path = os.path.join(STATE, "cleanup.log"), os.path.join(STATE, "cleanup-last-run.json")
        log = open(log_path, encoding="utf-8-sig").read() if os.path.exists(log_path) else ""
        last = json.load(open(last_path, encoding="utf-8-sig")) if os.path.exists(last_path) else {}
        ok = log.count("] closed ") >= 4 and "brake:" in log and last.get("closed", 0) >= 4 and not last.get("error")
        print("%-5s log: the brake and every close are written down -> %d close lines, last run closed %s" % ("ok" if ok else "FAIL", log.count("] closed "), last.get("closed")))
        if not ok:
            failures.append("log")

        # The real machine, report only: nothing it would close is ever a never-close process.
        real = sweep()
        never = {"claude.exe", "explorer.exe", "windowsterminal.exe", "openconsole.exe", "code.exe", "chrome.exe", "msedge.exe"}
        would_close = [g for g in real.get("groups") or [] if g.get("decision") == "close"]
        bad = [g for g in would_close if never & set(n.lower() for n in g.get("names") or [])]
        ok = "groups" in real and not real.get("error") and not bad
        print("%-5s real machine (report only): %d leftover group(s) it would close, none containing a never-close process" % ("ok" if ok else "FAIL", len(would_close)))
        for g in would_close:
            print("        would close: pid %s %s [%s] %s" % (g.get("root"), g.get("name"), g.get("class"), (g.get("cmd") or "")[:80]))
        if not ok:
            failures.append("real machine")

        # Idle sessions: only the language server of a session idle past the limit sleeps.
        fakes = {"i1": fake_session(MARK_IDLE + "i1", "idle", 3),
                 "i2": fake_session(MARK_IDLE + "i2", "busy", 3),
                 "i3": fake_session(MARK_IDLE + "i3", "idle", 1)}
        started.extend(fakes.values())
        time.sleep(2)
        plan = sweep("-OnlyMarker", MARK_IDLE, sessions=FAKE_SESSIONS).get("sleepers") or []
        picked = [c for s in plan for c in s.get("cmds") or []]
        ok = (len(plan) == 1 and any(MARK_IDLE + "i1" in c and "typescript-language-server" in c for c in picked)
              and not any("chrome-devtools-mcp" in c for c in picked))
        print("%-5s idle sessions: only the 3-hour idle session's language server is picked (not the busy one, not the 1-hour one, never a helper) -> %d picked" % ("ok" if ok else "FAIL", len(plan)))
        if not ok:
            failures.append("idle pick")
        sweep("-Force", "-OnlyMarker", MARK_IDLE, sessions=FAKE_SESSIONS)
        time.sleep(1)
        for what, ok in (
            ("idle 3 h: its language server is asleep", not child_alive(MARK_IDLE + "i1", "typescript-language-server")),
            ("idle 3 h: its MCP helper and the session itself are untouched",
             child_alive(MARK_IDLE + "i1", "chrome-devtools-mcp") and fakes["i1"].poll() is None),
            ("busy and 1-hour-idle sessions: language servers untouched",
             child_alive(MARK_IDLE + "i2", "typescript-language-server") and child_alive(MARK_IDLE + "i3", "typescript-language-server")),
        ):
            print("%-5s %s" % ("ok" if ok else "FAIL", what))
            if not ok:
                failures.append(what)
        log = open(log_path, encoding="utf-8-sig").read() if os.path.exists(log_path) else ""
        last = json.load(open(last_path, encoding="utf-8-sig")) if os.path.exists(last_path) else {}
        ok = "slept the TypeScript server of fake " + MARK_IDLE + "i1" in log and last.get("slept") == 1
        print("%-5s log: the sleep is written down -> slept=%s" % ("ok" if ok else "FAIL", last.get("slept")))
        if not ok:
            failures.append("idle log")
    finally:
        for p in started:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            try:
                p.kill()
            except Exception:
                pass
        # Loops first: a loop whose sleep dies first just starts another sleep.
        for _ in range(3):
            found = procs_with(MARK_NATIVE, MARK_TIMER, MARK_IDLE)
            if not found:
                break
            for pid, (name, _) in sorted(found.items(), key=lambda kv: kv[1][0].lower() != "bash.exe"):
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
            time.sleep(0.5)
        shutil.rmtree(STATE, ignore_errors=True)
        shutil.rmtree(FAKE, ignore_errors=True)
        leftover = procs_with(MARK_NATIVE, MARK_TIMER, MARK_IDLE)
        if leftover:
            print("WARN  test processes still running after cleanup: %s" % leftover)
            failures.append("test cleanup")

    total = len(cases) + 10
    print("SUMMARY: %d/%d cases correct" % (total - len(failures), total))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
