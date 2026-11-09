"""Verify the branch-aware limb of guard_main_push.

A bare `git push` names no ref, so whether it lands on main depends on the
CHECKED-OUT BRANCH, not the command text. Build two throwaway repos -- one on
main, one on a feature branch -- and confirm the guard blocks only the first.
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.expanduser("~/.claude/hooks/block-main-push.sh")


def sh(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def mkrepo(root, branch):
    d = os.path.join(root, "repo_" + branch.replace("/", "_"))
    os.makedirs(d, exist_ok=True)
    sh(["git", "init", "-q"], d)
    sh(["git", "config", "user.email", "t@t.t"], d)
    sh(["git", "config", "user.name", "t"], d)
    open(os.path.join(d, "f.txt"), "w").write("x")
    sh(["git", "add", "-A"], d)
    sh(["git", "commit", "-qm", "init"], d)
    sh(["git", "branch", "-M", branch], d)
    cur = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], d).stdout.strip()
    return d, cur


def probe(cmd, cwd):
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": cmd},
        "cwd": cwd,
    })
    p = subprocess.run(["bash", HOOK], input=payload,
                       capture_output=True, text=True)
    return p.returncode, (p.stderr or "").strip().splitlines()[:1]


def main():
    root = tempfile.mkdtemp(prefix="guardbranch_")
    print("scratch:", root)
    results = []
    for branch in ("main", "feat/safe"):
        d, cur = mkrepo(root, branch)
        print("\n=== repo on branch %r (confirmed: %r) ===" % (branch, cur))
        for cmd in ("git push",
                    "git push origin",
                    "git push origin HEAD",
                    "git push -f origin main",
                    "git push origin feat/x"):
            rc, err = probe(cmd, d)
            verdict = "BLOCK" if rc == 2 else "allow"
            print("   %-5s rc=%d  %-26s %s"
                  % (verdict, rc, cmd, (err[0][:70] if err else "")))
            results.append((branch, cmd, verdict))

    print("\n" + "=" * 70)
    print("EXPECTED: bare/HEAD pushes BLOCK on main, allow on feat/safe.")
    print("EXPECTED: 'git push -f origin main' BLOCKs on BOTH (names main).")
    print("=" * 70)
    for branch, cmd, verdict in results:
        exp = None
        if cmd in ("git push", "git push origin", "git push origin HEAD"):
            exp = "BLOCK" if branch == "main" else "allow"
        elif cmd == "git push -f origin main":
            exp = "BLOCK"
        elif cmd == "git push origin feat/x":
            exp = "allow"
        flag = "" if verdict == exp else "   <== MISMATCH (expected %s)" % exp
        print("  [%-9s] %-26s %s%s" % (branch, cmd, verdict, flag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
