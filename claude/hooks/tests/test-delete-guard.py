"""Recursive deletes: block only what has no undo, allow all routine cleanup.

WHY THIS FILE EXISTS
--------------------
Four blanket deny rules -- Bash(rm -rf:*), (rm -fr:*), (rm -Rf:*), (rm -R:*) --
refused EVERY recursive delete regardless of target.

Measured 2026-08-16 across all 2,717 transcripts on this machine (2.8 GB): they
fired ~190 times, more than every other guard in this system combined, and
caught ZERO dangerous deletes. What they actually stopped was `rm -rf .next`,
scratch directories Claude had created itself minutes earlier, and regenerated
data files. They matched the SUBSTRING `rm -rf` rather than the OPERATION --
the same defect the Guard incident record documents three other times.

They are gone. This suite is what replaces them, and it asserts BOTH halves,
because a guard that only proves it blocks is how the friction got here:

  MUST BLOCK   the filesystem/drive root, and the unset-$VAR-then-slash shape
               (the Steam bug: an empty variable turns "$VAR/x" into /x).
  MUST ALLOW   every real cleanup command found in the owner's transcripts.

The tamper cases are included deliberately. Home and the guard layer are NOT
protected by the new check -- `_tamper_protected` covers them -- so if a future
edit to the delete guard shadowed that path, only these cases would notice.

Run:  py -3 test-delete-guard.py
"""
import json
import os
import subprocess
import sys

HOOK = os.path.expanduser("~/.claude/hooks/block-guard-tamper.sh")
CWD = "~/projects/a live web game"
R = "rm -rf "

failures = []


def run(cmd, cwd=CWD):
    # bash, not sh: Claude Code runs the hook through its #!/bin/bash shebang. On
    # Windows `sh` happens to be bash; on Ubuntu it is dash, which cannot run the
    # wrapper, so every case failed closed (measured in the Linux CI, 2026-11-10).
    p = subprocess.run(
        ["bash", HOOK],
        input=json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": cmd},
                          "cwd": cwd}),
        capture_output=True, text=True, timeout=120)
    return p.returncode == 2


def expect(blocked_wanted, label, cmd, cwd=CWD):
    got = run(cmd, cwd)
    ok = got == blocked_wanted
    word = "BLOCK" if blocked_wanted else "ALLOW"
    print("   %-5s %-46s %s" % ("ok" if ok else "FAIL", label,
                                "" if ok else ("got %s" % ("BLOCK" if got else "ALLOW"))))
    if not ok:
        failures.append(label)


def main():
    print("=" * 78)
    print("RECURSIVE DELETE GUARD")
    print("=" * 78)

    print("\n-- MUST BLOCK: no undo ------------------------------------------")
    # GNU rm refuses a bare `/` itself, but the glob form expands past that.
    expect(True,  "filesystem root",            R + "/")
    expect(True,  "filesystem root glob",       R + "/*")
    expect(True,  "drive root (windows)",       R + "C:/")
    expect(True,  "drive root glob",            R + "C:/*")
    expect(True,  "msys drive root",            R + "/c/")
    # The Steam bug. Shell state does not survive between tool calls, so an
    # unset variable collapses the target to the filesystem root.
    expect(True,  "unset $VAR then slash",      R + '"$NOPE_NOT_SET/cache"')
    expect(True,  "unset ${VAR} then slash",    R + '"${NOPE_NOT_SET}/cache"')
    expect(True,  "unset $VAR slash glob",      R + '"$NOPE_NOT_SET/*"')
    expect(True,  "-fr spelling",               "rm -fr \"$NOPE_NOT_SET/x\"")
    expect(True,  "-Rf spelling",               "rm -Rf \"$NOPE_NOT_SET/x\"")

    print("\n-- MUST BLOCK: still the tamper guard's job ----------------------")
    expect(True,  "home tilde",                 R + "~")
    expect(True,  "home $HOME",                 R + "$HOME")
    expect(True,  "the ~/.claude root",         R + "~/.claude")
    expect(True,  "the hooks dir",              R + "~/.claude/hooks")
    expect(True,  "guard glob",                 R + "~/.claude/hook*")
    expect(True,  "cd then relative",           "cd ~/.claude && " + R + "hooks")
    expect(True,  "settings.json",              "rm ~/.claude/settings.json")

    print("\n-- MUST ALLOW: real commands from the owner's transcripts ----------------")
    # Every one of these was blocked by the old blanket rules.
    expect(False, "next build cache",           R + ".next")
    expect(False, "scratch dirs",               R + ".review .playwright")
    expect(False, "generated files",            R + ".gen/canon-cache")
    expect(False, "node_modules",               R + "node_modules")
    expect(False, "dist",                       R + "dist")
    expect(False, "compound with cd",           "cd " + CWD + "\n" + R + ".review .playwright\npnpm typecheck")
    expect(False, "delete then rebuild",        R + ".next\npnpm build")
    expect(False, "assigned var, same command", 'S=' + CWD + '/tmp\n' + R + '"$S/frames"')
    expect(False, "$HOME resolves, safe path",  R + "$HOME/projects/scratch")
    expect(False, "absolute path in a project", R + CWD + "/.next")
    expect(False, "bare unset var, no slash",   R + '"$NOPE_NOT_SET"')
    expect(False, "non-recursive rm",           "rm -f ./tmpfile.txt")
    expect(False, "a file, not a dir",          "rm ./build.log")
    expect(False, "not a delete at all",        "ls -la /")

    print("\n-- MUST ALLOW: adjacent commands that merely mention a delete ----")
    # A commit message or PR body that QUOTES a delete is not a delete.
    #
    # This bit twice on 2026-08-16, in the same session: the guard blocked the
    # commit documenting the delete-rule fix, and then blocked the PR body for
    # it. The first diagnosis (globs resolving against a cd'd cwd) was WRONG.
    # The real cause: heredoc bodies were judged as code whenever ANY segment
    # anywhere in the command was an interpreter, so an unrelated
    # `sh health.sh` earlier in the same command turned the prose into
    # "commands". Now judged per heredoc, on its own declaring line.
    danger = R + "~/.claude/hooks"
    expect(False, "commit msg quoting a delete",
           "git commit -F - <<'EOF'\nfix: stop deleting the cache\n" + R + ".next\nEOF")
    expect(False, "echo describing a delete",   'echo "run ' + R + '.next to clean"')
    expect(False, "PR body after an sh call",
           "sh health.sh 2>&1 | tail -1\ngh pr create --body-file - <<'BODY'\nevidence: " + danger + "\nBODY")
    expect(False, "commit msg after an sh call",
           "sh health.sh\ngit commit -F - <<'MSG'\nfix: stop " + danger + "\nMSG")
    expect(False, "PR body quoting a root delete",
           "sh x.sh\ngh pr create --body-file - <<'BODY'\nwe now block " + R + "/*\nBODY")

    print("\n-- MUST BLOCK: a heredoc that genuinely executes ------------------")
    # The other half of the same change. Scoping the interpreter check to the
    # declaring line must NOT stop a body that really is fed to a shell.
    expect(True,  "bash <<EOF",         "bash <<'EOF'\n" + danger + "\nEOF")
    expect(True,  "bash -s <<EOF",      "bash -s <<'EOF'\n" + danger + "\nEOF")
    expect(True,  "cat <<EOF | bash",   "cat <<'EOF' | bash\n" + danger + "\nEOF")
    expect(True,  "sh <<EOF root",      "sh <<'EOF'\n" + R + "/*\nEOF")
    expect(True,  "interpreter after cd",
           "cd /tmp\nbash <<'EOF'\n" + danger + "\nEOF")

    print()
    print("=" * 78)
    total = 43
    print("SUMMARY: %d/%d correct" % (total - len(failures), total))
    if failures:
        for f in failures:
            print("   [FAIL] %s" % f)
        sys.exit(1)
    print("\nALL CLEAN")


main()
