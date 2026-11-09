"""the owner's real daily operations. Every one of these MUST pass the guard layer.

WHY THIS FILE EXISTS
--------------------
On 2026-08-07 an audit found that "destructive migration or RLS change" -- one of
the six named human gates -- had no enforcement anywhere. The fix blocked the
whole Supabase migration CATEGORY: `db push`, `migration up`, `migration repair`,
`functions deploy`. Hours later a live session could no longer do the Supabase
work it had done the day before, and `migration repair` (which edits history
metadata and touches NO schema and NO data) was blocked outright.

The rule as written said "destructive migration". The implementation said "all
migrations". The gap between those two sentences is this entire file.

In the SAME session, a new git guard WAS tested against routine work, caught
over-blocking `git checkout main` and `git stash pop`, and was narrowed before
commit. Same class of change, same hour, opposite outcome -- because that check
was something that happened to be done, not something that had to be.

THE CONTRACT
------------
Maximum autonomy means EXPANDING what Claude can do, never SHRINKING what the owner
controls. A guard that blocks daily work gets disabled, which is the worst
possible outcome. So: before shipping ANY new guard, deny rule, or permission
change, run this file. Anything that fails is either a bug in the new guard or a
deliberate, named decision -- never a shrug.

This file asserts ALLOW. The BLOCK side lives in test-command-guards.py and
test-guard-tamper.py; the two together are the whole picture.

Run:  py -3 test-routine-work.py
"""
import json
import os
import subprocess
import sys

HOOKS = os.path.expanduser("~/.claude/hooks")
GUARDS = ("block-main-push.sh", "block-pr-merge.sh", "block-prod-deploy.sh",
          "block-stacked-pr-base.sh", "block-guard-tamper.sh")
HOME = os.path.expanduser("~").replace("\\", "/")
CC = HOME + "/.claude"
PROJ = "~/projects/a live web game"

# (label, command, cwd). Everything here is something the owner's sessions do for real.
ROUTINE = [
    # --- Supabase: FULL AUTONOMY (The owner's decision 2026-08-07). Only genuinely
    # destructive SQL stops, and it stops in conversation, not by blocking here.
    ("supabase-db-push", "supabase db push --linked", PROJ),
    ("supabase-migration-up", "supabase migration up", PROJ),
    ("supabase-migration-repair",
     "supabase migration repair --status applied 20260602000001", PROJ),
    ("supabase-migration-list", "supabase migration list", PROJ),
    ("supabase-migration-new", "supabase migration new add_column", PROJ),
    ("supabase-functions-deploy", "supabase functions deploy api", PROJ),
    ("supabase-functions-list", "supabase functions list", PROJ),
    ("supabase-link", "supabase link --project-ref edsirhcunhlyjbljedpw", PROJ),
    ("supabase-projects-list", "supabase projects list", PROJ),
    ("supabase-secrets-list", "supabase secrets list", PROJ),
    ("supabase-secrets-set", "supabase secrets set FOO=bar --project-ref abc", PROJ),
    ("supabase-db-diff", "supabase db diff", PROJ),
    ("supabase-gen-types", "supabase gen types typescript --linked", PROJ),
    # Additive SQL is ordinary work. Only the destructive verbs are gated.
    ("sql-create-table",
     "psql -c 'create table if not exists foo (id uuid primary key)'", PROJ),
    ("sql-alter-add-column", "psql -c 'alter table profiles add column bar text'", PROJ),
    ("sql-update-rows", "psql -c 'update profiles set nsfw_enabled = true'", PROJ),
    ("sql-select", "psql -c 'select count(*) from profiles'", PROJ),

    # --- Vercel: previews and inspection are Claude's; only production is gated.
    ("vercel-deploy-preview", "vercel deploy", PROJ),
    ("vercel-build", "vercel build --prod", PROJ),
    ("vercel-env-ls", "vercel env ls production", PROJ),
    ("vercel-env-pull", "vercel env pull .env.local --environment=development --yes", PROJ),
    ("vercel-logs", "vercel logs dpl_abc", PROJ),
    ("vercel-rest-env-upsert",
     'curl -X POST "https://api.vercel.com/v10/projects/x/env?upsert=true"', PROJ),
    # Checking what is live after a merge (blocked by the substring check, 2026-10-16).
    ("vercel-rest-list-production-deployments",
     'curl -s -H "Authorization: Bearer $VERCEL_TOKEN" "https://api.vercel.com/v6/deployments?projectId=x&target=production&limit=3"', PROJ),

    # --- Git and GitHub: everything except pushing to main and merging.
    ("git-status", "git status", PROJ),
    ("git-checkout-main", "git checkout main", PROJ),
    ("git-new-branch", "git checkout -b feat/thing", PROJ),
    ("git-push-branch", "git push -u origin feat/thing", PROJ),
    ("git-stash", "git stash push settings.json", PROJ),
    ("git-commit", 'git commit -m "feat: thing"', PROJ),
    ("gh-pr-create", 'gh pr create --base main --title "x" --body "y"', PROJ),
    ("gh-pr-view", "gh pr view 42", PROJ),
    ("gh-workflow-run", "gh workflow run android-release.yml", PROJ),
    # The workflow repo is maintained through ordinary git every session.
    ("git-checkout-main-in-claude", "git checkout main", CC),
    ("git-stash-pop-in-claude", "git stash pop", CC),
    ("git-discard-local-in-claude", "git checkout -- README.md", CC),

    # --- Operational work the owner explicitly wants Claude to own (2026-08-07).
    # "all of it, claude should handle... so boring stuff is all done by claude".
    # Store submission: submitting enters REVIEW, which takes days and can be
    # halted; the irreversible moment is Apple/Google approving, which no command
    # here causes.
    ("eas-submit-ios", "eas submit --platform ios --latest", PROJ),
    ("eas-submit-android", "eas submit --platform android --latest", PROJ),
    ("eas-build-autosubmit", "eas build -p android --auto-submit", PROJ),
    ("npx-eas-submit", "npx eas-cli submit --platform ios", PROJ),
    # Uploading a build is Claude's. Pressing "Submit for Review" / promoting to
    # the production track is the owner's, and those two are gated in test-mcp-guard.py's
    # sibling checks -- verified against the vendor docs, not assumed: `eas submit`
    # lands in TestFlight / the internal track and does NOT submit for review.
    ("fastlane-supply-internal", "fastlane supply --track internal", PROJ),
    ("fastlane-supply-beta", "fastlane supply --track beta", PROJ),
    ("fastlane-deliver-upload", "fastlane deliver --skip_screenshots", PROJ),
    ("fastlane-pilot-testflight", "fastlane pilot upload", PROJ),
    # Real email. Cannot be unsent, and that is accepted: the owner loved this being
    # automated and it is the core of the content and launch workflow.
    ("resend-send", "resend emails send --to a@b.com --subject hi", PROJ),
    ("resend-batch", "resend emails batch --file batch.json", PROJ),
    ("resend-broadcast", "resend broadcasts send --id abc", PROJ),
    ("resend-domains", "resend domains list", PROJ),
    # DNS and domains.
    ("vercel-domains-rm", "vercel domains rm old.example.com --yes", PROJ),
    ("vercel-certs-rm", "vercel certs rm cert_abc", PROJ),
    ("vercel-env-rm", "vercel env rm OLD_KEY production --yes", PROJ),
    # Recovery and config-only rebuilds. rollback restores a KNOWN-GOOD build
    # (the reversible direction); redeploy rebuilds the SAME code so a
    # NEXT_PUBLIC_* change takes effect. Neither ships new code.
    # THE FULL ENV-CHANGE LOOP, end to end. This is the sequence that failed on
    # 2026-08-12: a session set a var on production, then could not verify or
    # redeploy because `vercel ls --prod` (a READ) was blocked, and handed the owner a
    # dashboard click. Vercel bakes env vars in at BUILD time, so the redeploy is
    # not optional -- it is how the change takes effect.
    ("vercel-env-add-prod", "vercel env add ALLOW_TEST_SKU production", PROJ),
    ("vercel-ls-prod-READ", "vercel ls --prod", PROJ),
    ("vercel-inspect-READ", "vercel inspect https://x.vercel.app --prod", PROJ),
    ("vercel-logs-READ", "vercel logs https://x.vercel.app --prod", PROJ),
    ("vercel-redeploy-to-apply-env",
     "vercel redeploy https://x.vercel.app --target=production", PROJ),
    ("vercel-rollback", "vercel rollback dpl_abc", PROJ),
    ("vercel-rest-rollback",
     'curl -X POST https://api.vercel.com/v1/projects/prj_x/rollback/dpl_y', PROJ),
    ("vercel-redeploy", "vercel redeploy https://x.vercel.app --target=production", PROJ),
    # Money CONFIG (The owner's product's billing setup), as distinct from spending the owner's
    # own money on a card, which stays confirmed per purchase.
    ("revenuecat-api", 'curl -X POST https://api.revenuecat.com/v2/projects/x/offerings', PROJ),
    ("razorpay-api", 'curl -X POST https://api.razorpay.com/v1/plans', PROJ),

    # --- Build, test, deps, scaffolding.
    ("npm-run-build", "npm run build", PROJ),
    ("pnpm-test", "pnpm test", PROJ),
    ("npx-shadcn", "npx shadcn@latest add button", PROJ),
    ("npx-create-next", "npx create-next-app@latest myapp", "~/projects"),
    ("eas-build-preview", "eas build --profile preview -p android", PROJ),
    ("cap-sync", "npx cap sync android", PROJ),

    # --- Housekeeping in project directories.
    ("rm-node-modules", "rm -rf node_modules", PROJ),
    ("rm-dist", "rm -rf dist .next", PROJ),
    ("find-project", "find . -name '*.ts' -type f", PROJ),
    ("cd-then-build", "cd ~/projects/a live mobile app && npm run build", "~/projects"),
]


def run(cmd, cwd):
    """Return the first guard that blocks, or None."""
    payload = json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": cmd},
                          "cwd": cwd})
    for g in GUARDS:
        p = subprocess.run(["bash", os.path.join(HOOKS, g)],
                           input=payload, capture_output=True, text=True)
        if p.returncode == 2:
            return g, (p.stderr or "").strip().splitlines()[0][:100]
    return None


def main():
    print("=" * 78)
    print("ROUTINE WORK -- every case MUST be allowed")
    print("=" * 78)
    fails = []
    for label, cmd, cwd in ROUTINE:
        hit = run(cmd, cwd)
        if hit:
            fails.append((label, cmd, hit[0], hit[1]))
            print("   BLOCKED  %-30s %s" % (label, cmd[:40]))
        else:
            print("   ok       %-30s %s" % (label, cmd[:40]))

    print("\n" + "=" * 78)
    print("SUMMARY: %d/%d routine operations allowed" % (len(ROUTINE) - len(fails), len(ROUTINE)))
    if fails:
        print("\nA guard is blocking daily work. Either the guard is too broad, or the")
        print("block is a deliberate decision that belongs in CLAUDE.md's FOUNDATION.")
        for label, cmd, guard, reason in fails:
            print("  [%s] %s" % (label, cmd))
            print("      blocked by %s: %s" % (guard, reason))
        sys.exit(1)
    print("\nALL CLEAN")


main()
