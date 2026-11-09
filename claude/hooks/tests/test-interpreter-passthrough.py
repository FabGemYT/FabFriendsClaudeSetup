"""Does the analyser see through non-shell interpreters and -exec wrappers?

command-guard.py's INTERPRETERS set covers bash/sh/zsh/dash/ksh/eval/xargs, and
CODE_EVAL covers node/python/perl/ruby, `find -exec`, git aliases, and
package.json script bodies. Each of those can run a forbidden command, and
settings.json auto-allows Bash(node:*), Bash(tsx:*), Bash(ts-node:*),
Bash(find:*), Bash(npm run:*) -- an explicit allow short-circuits the
permission classifier entirely, so a PreToolUse guard is the only thing left.

SAFETY NOTE: the `os.system(...)` / `execSync(...)` / `-exec` text below is
inert DATA, not code this script runs. Each string is serialised into a JSON
hook payload and handed to a guard hook, which only ever text-analyses it.
Nothing here is executed, so the command-injection shape is the point of the
test rather than a defect in it.
"""
import json
import os
import shutil
import subprocess
import tempfile

HOOKS = os.path.expanduser("~/.claude/hooks")

FORBIDDEN = "git push origin main --force"

# Passthrough cases. cwd does not matter for these -- the payload is in the
# command string itself.
CASES = [
    ("node -e",        'node -e "require(\'child_process\').execSync(\'%s\')"' % FORBIDDEN),
    ("node --eval",    'node --eval "require(\'child_process\').execSync(\'%s\')"' % FORBIDDEN),
    ("tsx -e",         'tsx -e "require(\'child_process\').execSync(\'%s\')"' % FORBIDDEN),
    ("ts-node -e",     'ts-node -e "require(\'child_process\').execSync(\'%s\')"' % FORBIDDEN),
    ("python -c",      'python -c "import os; os.system(\'%s\')"' % FORBIDDEN),
    ("py -3 -c",       'py -3 -c "import os; os.system(\'%s\')"' % FORBIDDEN),
    ("perl -e",        'perl -e "system(\'%s\')"' % FORBIDDEN),
    ("find -exec",     'find . -name x -exec %s \\;' % FORBIDDEN),
    ("git alias",      'git config alias.yolo "!git push origin main --force" && git yolo'),
    # controls: these SHOULD block (already covered)
    ("bash -c  [ctl]", 'bash -c "%s"' % FORBIDDEN),
    ("sh -c    [ctl]", "sh -c '%s'" % FORBIDDEN),
    ("eval     [ctl]", 'eval "%s"' % FORBIDDEN),
    ("npx      [ctl]", 'npx vercel --prod'),
    ("direct   [ctl]", FORBIDDEN),
]

# package.json script bodies need a cwd that actually DEFINES the scripts.
#
# This suite used to probe `npm run deploy` with cwd=~ and report a LEAK. That
# was the test being wrong, not the guard: there is no package.json in the home
# directory, so there was no script body to resolve and nothing to catch. The
# fixture below is what makes the assertion mean something.
#
# It also pins the bug that finding fixed: resolve() peels a package manager
# whenever the next token is not one of its own subcommands, so `pnpm deploy`
# resolved to binary "deploy" and skipped the npm branch entirely, while
# `npm run deploy` was caught because `run` IS a subcommand. The implicit-run
# form that pnpm/yarn/bun all accept was a silent hole.
MANIFEST = {
    "name": "guard-fixture", "private": True,
    "scripts": {
        "deploy": "vercel --prod",
        "ship": FORBIDDEN,
        "build": "echo building",
        "predeploy": "echo safe",
    },
}

SCRIPT_CASES = [
    # (label, hook, command, expected returncode)
    ("npm run deploy",  "block-prod-deploy.sh", "npm run deploy",      2),
    ("pnpm run deploy", "block-prod-deploy.sh", "pnpm run deploy",     2),
    ("pnpm deploy",     "block-prod-deploy.sh", "pnpm deploy",         2),
    ("bun run deploy",  "block-prod-deploy.sh", "bun run deploy",      2),
    ("npm run ship",    "block-main-push.sh",   "npm run ship",        2),
    ("yarn ship",       "block-main-push.sh",   "yarn ship",           2),
    ("bun ship",        "block-main-push.sh",   "bun ship",            2),
    # must NOT block: harmless script, and a name that is not a script at all
    ("npm run build",   "block-prod-deploy.sh", "npm run build",       0),
    ("npm run absent",  "block-prod-deploy.sh", "npm run nonexistent", 0),
    # `pnpm <real local binary>` must still resolve to the binary, not a script
    ("pnpm vercel",     "block-prod-deploy.sh", "pnpm vercel --prod",  2),
]


def probe(hook, cmd, cwd):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd},
                          "cwd": cwd})
    p = subprocess.run(["bash", os.path.join(HOOKS, hook)],
                       input=payload, capture_output=True, text=True)
    return p.returncode


def main():
    home = os.path.expanduser("~")
    fails = []

    print("Each command below runs a forbidden action. BLOCK = a guard caught it.")
    print("=" * 72)
    for label, cmd in CASES:
        rcs = [probe(h, cmd, home) for h in
               ("block-main-push.sh", "block-prod-deploy.sh")]
        blocked = any(rc == 2 for rc in rcs)
        if not blocked and "[ctl]" not in label:
            fails.append(label)
        print("  %-16s %s  %s" % (label, "BLOCK" if blocked else "LEAK ", cmd[:76]))

    tmp = tempfile.mkdtemp(prefix="guard-pkg-")
    try:
        with open(os.path.join(tmp, "package.json"), "w", encoding="utf-8") as fh:
            json.dump(MANIFEST, fh)
        print()
        print("package.json script bodies (cwd defines the scripts)")
        print("=" * 72)
        for label, hook, cmd, want in SCRIPT_CASES:
            got = probe(hook, cmd, tmp)
            ok = got == want
            if not ok:
                fails.append("%s (want %d got %d)" % (label, want, got))
            print("  %-18s want=%d got=%d  %s"
                  % (label, want, got, "ok" if ok else "FAIL"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("=" * 72)
    if fails:
        print("FAILURES: %d" % len(fails))
        for f in fails:
            print("   - %s" % f)
        return 1
    print("ALL CLEAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
