---
name: commit-push-pr
description: Use this skill WHENEVER the user wants to ship a chunk of work — triggers include 'commit', 'push', 'open a PR', 'ship this', 'let's merge', 'send this up', 'submit', 'land this', 'finalize and push'. ALWAYS commit + push + open a PR in one shot, and point the user to the PR where Vercel posts the preview link. Do NOT merge the PR (user-only).
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git branch:*), Bash(git log:*), Bash(gh pr create:*), Bash(gh pr view:*), Bash(gh pr list:*), Bash(npm run:*), Bash(npm test:*), Bash(vercel env:*)
---

# Commit, Push, Open PR

## Pre-computed context

Current branch:
!`git branch --show-current`

Working tree status:
!`git status --short`

Diff of uncommitted changes:
!`git diff HEAD`

Recent commits on this branch:
!`git log --oneline -10`

Existing PR for this branch (if any):
!`gh pr list --head $(git branch --show-current) --state open --json url,number,title 2>/dev/null || echo "none"`

## Your task

Using the context above:

1. Verify there ARE uncommitted changes. If working tree is clean and 
   no unpushed commits exist, report that and stop — nothing to do.

1b. **Verify a green build BEFORE committing (app repos only).** If `package.json`
   defines them, run the build/typecheck/test scripts and STOP on failure; do not
   commit broken code:
   ```bash
   npm run typecheck 2>/dev/null; npm run build 2>/dev/null; npm test 2>/dev/null
   ```
   Run whichever exist (skip cleanly if a script is absent). On any failure, surface
   the error and STOP, do not commit or push. Skip entirely for non-app repos
   (docs/config, like this backup) that have no build.

1c. **Reconcile Vercel env (Vercel-linked app repos).** If `.vercel/` exists and this
   change added or relies on a new env var, reconcile per the deploy-to-vercel skill
   Step 1.5 (`vercel env pull`, push any missing key via stdin) BEFORE pushing (a push
   to a Vercel-linked repo is what triggers the preview build), so the build does not
   run with a missing secret. Skip if not Vercel-linked.

2. Write a clear conventional-commit message:
   - Prefix with feat: / fix: / refactor: / chore: / docs: / test: / 
     style: as appropriate
   - Subject line under 60 chars, imperative mood
   - Add a body if the change is non-trivial (what + why, not how)

3. Stage everything: `git add -A`

4. Commit with the message.

5. Push the current branch to origin. FIRST confirm you are not on the 
   production branch: `git branch --show-current` must not return `main` or 
   `master`. If it does, STOP and cut a feature branch; a bare `git push` 
   there lands directly on main. Then use `-u origin <branch>` if it's a new 
   branch (no upstream yet), otherwise just `git push`.

6. If a PR already exists for this branch (per pre-compute above): 
   confirm the push landed and report the existing PR URL. Do NOT 
   open a duplicate PR.
   
   If no PR exists: open one via `gh pr create --fill --base main` (uses 
   commit messages for title/body). ALWAYS pass `--base main`: every PR is 
   cut from main and targets main, because a stacked PR silently drops its 
   diff when the parent dies. If --fill produces something weak, regenerate 
   with explicit --title and --body.

7. End-of-task wrap (per Operating Protocol > "End-of-task wrap (always)" in
   ~/.claude/CLAUDE.md).
   Output exactly this format, replacing the bracketed placeholder. 
   Plain English, no jargon, no preamble:

   🚢 Just shipped: [one-sentence plain English summary of what this 
   PR does — no jargon]

   PR: [PR URL]

   ⏱ Vercel preview URL will appear as a comment on this PR within 
   ~60 seconds. Open the PR, wait for the Vercel bot comment, click 
   the preview link, and test the change.

   If happy → click "Merge" on the PR → production auto-deploys 
   (~30 seconds after merge).

   If something's wrong → tell me what to fix, I'll push more 
   commits, the preview URL auto-updates.

   Do NOT poll for the preview URL via `gh pr view --json comments` 
   — the Vercel bot timing is fragile and waiting in the agent loop 
   wastes the user's time. Point them at the PR; Vercel handles the 
   comment naturally.

8. Stop-on-divergence (per Law 4, STOP WHEN UNCERTAIN, and the Autonomous
   execution contract's "if a hook or deny rule blocks something, stop and ask"):
   - Push rejected (non-fast-forward, branch protection) → STOP, 
     surface, ask
   - gh not authenticated → STOP, tell user to run `gh auth login`
   - Merge conflicts → STOP, do not improvise resolution
   - Any other unexpected error → STOP and surface
