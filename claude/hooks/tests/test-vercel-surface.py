"""Every Vercel subcommand, judged the way the owner's gate actually works.

WHY THIS FILE EXISTS
--------------------
On 2026-08-12 a a course site session set an env var on production, could not
verify it, concluded "I can't touch production", and handed the owner a manual
dashboard redeploy. The owner asked: "why is claude not handling all this itself man!!"

The honest answer was that the guard told it not to. The prod-deploy check tested
for `--prod` ANYWHERE in a vercel command, so FIVE READ-ONLY commands were blocked
with the message "Production deploys are blocked":

    vercel ls --prod            (lists deployments)
    vercel list --prod
    vercel inspect <url> --prod (shows one deployment)
    vercel logs <url> --prod    (reads logs)
    vercel deployments list --prod

`vercel redeploy` was free the whole time, and is exactly the right tool: Vercel
bakes env vars in at build time, so a changed variable needs a rebuild of the same
commit. The session never found it, because the guard had already told it the
whole area was closed.

Same defect class as the destructive-SQL gate: matching a SUBSTRING instead of
understanding the OPERATION.

THE RULE THIS FILE PINS
-----------------------
Only three things stop, and all three make a deployment LIVE without a merge or
spend the owner's money:
    deploy to production (`vercel --prod`, `deploy --prod`, `--target production`)
    promote / alias
    buy
Everything else -- every read, every rebuild, every env change -- is Claude's job.

Run:  py -3 test-vercel-surface.py
"""
import json
import os
import subprocess
import sys

HOOK = os.path.expanduser("~/.claude/hooks/block-prod-deploy.sh")
CWD = "~/projects/a course site"

BLOCK, ALLOW = True, False

CASES = [
    # ---- READ-ONLY. The regression that caused the whole incident. ----------
    (ALLOW, "vercel ls --prod"),
    (ALLOW, "vercel list --prod"),
    (ALLOW, "vercel ls"),
    (ALLOW, "vercel inspect https://x.vercel.app --prod"),
    (ALLOW, "vercel logs https://x.vercel.app --prod"),
    (ALLOW, "vercel deployments list --prod"),
    (ALLOW, "vercel activity"),
    (ALLOW, "vercel metrics requests"),
    (ALLOW, "vercel usage"),
    (ALLOW, "vercel whoami"),
    (ALLOW, "vercel projects ls"),
    (ALLOW, "vercel teams ls"),
    (ALLOW, "vercel bisect"),
    (ALLOW, "vercel pull"),
    (ALLOW, "vercel link"),

    # ---- ENV: managing env vars is explicitly Claude's job ------------------
    (ALLOW, "vercel env ls production"),
    (ALLOW, "vercel env add ALLOW_TEST_SKU production"),
    (ALLOW, "vercel env rm ALLOW_TEST_SKU production --yes"),
    (ALLOW, "vercel env pull .env.local --environment=production --yes"),

    # ---- REBUILD the same commit. The tool the session never found. ---------
    (ALLOW, "vercel redeploy https://x.vercel.app --target=production"),
    (ALLOW, "vercel redeploy dpl_abc"),
    (ALLOW, "vercel redeploy dpl_abc --target production"),
    (ALLOW, "vercel rollback dpl_abc"),
    (ALLOW, "vercel rollback"),
    (ALLOW, "vercel build --prod"),
    (ALLOW, "vercel dev"),

    # ---- other config writes that never make new code live -----------------
    (ALLOW, "vercel domains ls"),
    (ALLOW, "vercel certs ls"),
    (ALLOW, "vercel dns ls example.com"),
    (ALLOW, "vercel cron ls"),
    (ALLOW, "vercel firewall ls"),
    (ALLOW, "vercel cache purge"),

    # ---- SHIPS NEW CODE TO PRODUCTION WITHOUT A MERGE: the owner's gate -------------
    (BLOCK, "vercel --prod"),
    (BLOCK, "vercel deploy --prod"),
    (BLOCK, "vercel deploy --prebuilt --prod"),
    (BLOCK, "vercel --prebuilt --prod"),
    (BLOCK, "vercel deploy --target production"),
    (BLOCK, "vercel deploy --target=production"),
    (BLOCK, "vercel deploy -f --prod"),
    (BLOCK, "npx vercel --prod"),
    (BLOCK, "npx vercel@latest --prod"),
    (BLOCK, "pnpm vercel --prod"),
    (BLOCK, "env VERCEL_ORG_ID=x vercel --prod"),

    # ---- makes an existing deployment live without a merge ------------------
    (BLOCK, "vercel promote dpl_abc"),
    (BLOCK, "vercel alias set dpl_abc example.com"),

    # ---- spends the owner's money (was completely ungated on the CLI route) ---------
    (BLOCK, "vercel buy domain example.com"),
]


def blocked(cmd):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd},
                          "cwd": CWD, "permission_mode": "bypassPermissions"})
    p = subprocess.run(["bash", HOOK], input=payload,
                       capture_output=True, text=True)
    return p.returncode == 2


def main():
    print("=" * 80)
    print("VERCEL SURFACE -- reading and rebuilding are never deploying")
    print("=" * 80)
    fails = []
    for should, cmd in CASES:
        got = blocked(cmd)
        ok = got == should
        if not ok:
            fails.append((cmd, should, got))
        print("   %-5s %-6s %s" % ("ok" if ok else "FAIL",
                                   "BLOCK" if got else "allow", cmd))

    print()
    print("=" * 80)
    allows = sum(1 for s, _ in CASES if not s)
    blocks = len(CASES) - allows
    print("SUMMARY: %d/%d correct (%d must run, %d must stop)"
          % (len(CASES) - len(fails), len(CASES), allows, blocks))
    if fails:
        for cmd, should, got in fails:
            why = "BLOCKED but must run" if got else "RAN but must stop"
            print("   %-50s %s" % (cmd, why))
        sys.exit(1)
    print("\nALL CLEAN")


main()
