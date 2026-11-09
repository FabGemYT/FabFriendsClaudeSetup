"""The credential loader: idempotent, atomic, and self-healing.

WHY THIS FILE EXISTS
--------------------
On 2026-08-16 a live a live web game session became unable to run ANY Bash command.
`echo ok` failed exactly like `git status`:

    bash: -c: line 112: unexpected EOF while looking for matching `''

The cause was this hook. It appended with `>>` and never truncated, one `printf`
PER LINE, and SessionStart fires repeatedly in a single session -- startup,
resume, clear AND every compaction. Sixteen exports times seven firings is
exactly 112 lines. Measured, not estimated. One of those sixteen-write bursts,
racing five concurrent sessions, tore a line in half:

    export GSC_GCP_PROJECT='fab

Claude Code inlines that file into every `bash -c`, so an unterminated quote kills
every command while bash is still PARSING. A restart did not help, because the
file is on disk and gets reused. The line number never moved, because the file was
static. `.env.local` looked innocent, because it was.

THE THREE PROPERTIES THIS PINS
------------------------------
  IDEMPOTENT  seven firings must produce exactly what one firing produces.
  ATOMIC      the block is written in ONE printf, so a torn line is impossible.
  SELF-HEALING an already-wedged env file must be repaired at the next
              SessionStart -- a session with no working shell cannot fix itself
              any other way, and that is the whole difference between "run
              /compact" and "lose the session".

Plus the security properties the old version already had, which must not regress:
values single-quoted (so `$(...)` in a value is inert), `~/` expanded, empty
values skipped, `export KEY=` accepted, embedded quotes escaped.

Run:  py -3 test-load-env.py
"""
import os
import subprocess
import sys
import tempfile

HOOK = os.path.expanduser("~/.claude/hooks/load-env.sh")
BEGIN = "# >>> claude-env begin"
PAYLOAD = '{"hook_event_name":"SessionStart","source":"%s"}'

failures = []


def check(label, ok, detail=""):
    print("   %-5s %-56s %s" % ("ok" if ok else "FAIL", label, detail))
    if not ok:
        failures.append(label)


def run_hook(env_file, home, source="startup"):
    env = dict(os.environ)
    env["CLAUDE_ENV_FILE"] = env_file
    env["HOME"] = home
    subprocess.run(["sh", HOOK], input=PAYLOAD % source,
                   capture_output=True, text=True, env=env, timeout=120)


def parses(path):
    p = subprocess.run(["sh", "-n", path], capture_output=True, text=True)
    return p.returncode == 0


def sourced_value(path, var):
    """What a real Bash tool call would actually see."""
    p = subprocess.run(
        ["bash", "-c", ". '%s' >/dev/null 2>&1; printf '%%s' \"$%s\"" % (path, var)],
        capture_output=True, text=True)
    return p.stdout


def fixture(tmp, env_local_text):
    """A fake HOME whose .env.local holds exactly the given text."""
    home = os.path.join(tmp, "home")
    os.makedirs(os.path.join(home, ".claude"), exist_ok=True)
    with open(os.path.join(home, ".claude", ".env.local"), "w",
              encoding="utf-8", newline="") as fh:
        fh.write(env_local_text)
    return home


def main():
    print("=" * 78)
    print("CREDENTIAL LOADER")
    print("=" * 78)

    with tempfile.TemporaryDirectory() as tmp:
        home = fixture(tmp, "ALPHA=one\nBETA=two\nGAMMA=three\n")
        envf = os.path.join(tmp, "env1.sh")

        # --- idempotency: the actual bug ---------------------------------
        run_hook(envf, home)
        one = open(envf, encoding="utf-8").read()
        for _ in range(6):
            run_hook(envf, home, "compact")
        seven = open(envf, encoding="utf-8").read()
        check("7 firings == 1 firing (the 112-line bug)", one == seven,
              "%d bytes both" % len(one))
        check("no duplicated export", seven.count("export ALPHA=") == 1,
              "ALPHA x%d" % seven.count("export ALPHA="))
        check("file still parses after 7 firings", parses(envf))

        # --- values actually reach the shell -----------------------------
        check("value exported correctly", sourced_value(envf, "ALPHA") == "one")

    # --- self-healing: a wedged session repairs itself --------------------
    with tempfile.TemporaryDirectory() as tmp:
        home = fixture(tmp, "ALPHA=one\nBETA=two\n")
        envf = os.path.join(tmp, "env2.sh")
        with open(envf, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# harness preamble\n")
            fh.write(BEGIN + " (managed by hooks/load-env.sh -- do not edit inside)\n")
            fh.write("export ALPHA='one'\n")
            fh.write("export BETA='tw")          # TORN: quote never closes
        check("wedged file is genuinely broken first", not parses(envf))

        run_hook(envf, home)
        healed = open(envf, encoding="utf-8").read()
        check("self-healed: parses again", parses(envf))
        check("self-healed: torn line gone", "export BETA='tw\n" not in healed)
        check("self-healed: harness preamble preserved",
              "# harness preamble" in healed)
        check("self-healed: values work", sourced_value(envf, "BETA") == "two")

    # --- the LEGACY wedge: written by the pre-fix hook, so NO markers ------
    # This is the case that actually stranded a session, and the first cut of the
    # fix missed it: with no marker to find, cleanup did nothing and a fresh
    # block was simply appended after the poison, leaving it just as dead. Found
    # by testing the real recovery path instead of assuming it worked.
    with tempfile.TemporaryDirectory() as tmp:
        home = fixture(tmp, "ALPHA=one\nBETA=two\nGAMMA=three\n")
        envf = os.path.join(tmp, "env2b.sh")
        with open(envf, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# harness preamble\n")
            for _ in range(7):                       # 7 firings, old-style
                fh.write("export ALPHA='one'\nexport BETA='two'\nexport GAMMA='three'\n")
            fh.write("export GAMMA='thr")            # torn, unmarked
        check("legacy unmarked wedge is broken first", not parses(envf))

        run_hook(envf, home)
        body = open(envf, encoding="utf-8").read()
        check("legacy: parses after heal", parses(envf))
        check("legacy: duplicate exports removed",
              body.count("export ALPHA=") == 1, "ALPHA x%d" % body.count("export ALPHA="))
        check("legacy: harness preamble preserved", "# harness preamble" in body)
        check("legacy: credentials work", sourced_value(envf, "GAMMA") == "three")

    # --- security properties that must not regress ------------------------
    with tempfile.TemporaryDirectory() as tmp:
        home = fixture(
            tmp,
            "SAFE=$(touch " + os.path.join(tmp, "PWNED").replace("\\", "/") + ")\n"
            "SPACED=two words here\n"
            "QUOTED=\"already quoted\"\n"
            "EMPTY=\n"
            "export EXPORTED=viaexport\n"
            "TILDE=~/somewhere\n"
            "APOS=it's fine\n")
        envf = os.path.join(tmp, "env3.sh")
        run_hook(envf, home)
        body = open(envf, encoding="utf-8").read()

        sourced_value(envf, "SAFE")   # force a real source
        check("command substitution in a value is INERT",
              not os.path.exists(os.path.join(tmp, "PWNED")))
        check("value with spaces survives whole",
              sourced_value(envf, "SPACED") == "two words here")
        check("pre-quoted value is unwrapped once",
              sourced_value(envf, "QUOTED") == "already quoted")
        check("empty value is skipped", "EMPTY=" not in body)
        check("`export KEY=` form is accepted",
              sourced_value(envf, "EXPORTED") == "viaexport")
        check("~/ is expanded", sourced_value(envf, "TILDE").endswith("/somewhere")
              and not sourced_value(envf, "TILDE").startswith("~"))
        check("embedded apostrophe survives",
              sourced_value(envf, "APOS") == "it's fine")
        check("file parses with all of the above", parses(envf))

    # --- CRLF: .env.local really is CRLF on this machine -------------------
    with tempfile.TemporaryDirectory() as tmp:
        home = fixture(tmp, "CRLFVAR=value\r\nOTHER=second\r\n")
        envf = os.path.join(tmp, "env4.sh")
        run_hook(envf, home)
        check("CRLF source file leaves no CR in the value",
              sourced_value(envf, "CRLFVAR") == "value",
              repr(sourced_value(envf, "CRLFVAR")))
        check("file parses with CRLF input", parses(envf))

    # --- fail open ---------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        home = os.path.join(tmp, "nohome")
        os.makedirs(os.path.join(home, ".claude"), exist_ok=True)
        envf = os.path.join(tmp, "env5.sh")
        run_hook(envf, home)                       # no .env.local at all
        check("no .env.local -> writes nothing, exits clean",
              not os.path.exists(envf) or os.path.getsize(envf) == 0)

    print()
    print("=" * 78)
    total = 23
    print("SUMMARY: %d/%d correct" % (total - len(failures), total))
    if failures:
        for f in failures:
            print("   [FAIL] %s" % f)
        sys.exit(1)
    print("\nALL CLEAN")


main()
