---
name: deploy-to-vercel
description: Deploys a project to Vercel as a preview build and returns the preview URL. Use when the user wants to deploy, ship a preview, or get a live link (triggers include "deploy my app", "deploy and give me the link", "push this live", "create a preview deployment"). Never deploys to production; production is blocked by a deny rule and a hook, and ships only when the user merges to main.
---

# Deploy to Vercel

Deploy any project to Vercel. **Always deploy as preview** (not production). Production ships only when the user merges to main (Vercel auto-deploys main), never via this skill.

The goal is to get the user into the best long-term setup: their project linked to Vercel with git-push deploys. Every method below tries to move the user closer to that state.

## Step 1: Gather Project State

Run all four checks before deciding which method to use:

```bash
# 1. Check for a git remote
git remote get-url origin 2>/dev/null

# 2. Check if locally linked to a Vercel project (either file means linked)
cat .vercel/project.json 2>/dev/null || cat .vercel/repo.json 2>/dev/null

# 3. Check if the Vercel CLI is installed and authenticated
vercel whoami 2>/dev/null

# 4. List available teams (if authenticated)
vercel teams list --format json 2>/dev/null
```

### Team selection

If the user belongs to multiple teams, present all available team slugs as a bulleted list and ask which one to deploy to. Once the user picks a team, proceed immediately to the next step — do not ask for additional confirmation.

Pass the team slug via `--scope` on all subsequent CLI commands (`vercel deploy`, `vercel link`, `vercel inspect`, etc.):

```bash
vercel deploy [path] -y --no-wait --scope <team-slug>
```

If the project is already linked (`.vercel/project.json` or `.vercel/repo.json` exists), the `orgId` in those files determines the team — no need to ask again. If there is only one team (or just a personal account), skip the prompt and use it directly.

**About the `.vercel/` directory:** A linked project has either:
- `.vercel/project.json` — created by `vercel link` (single project linking). Contains `projectId` and `orgId`.
- `.vercel/repo.json` — created by `vercel link --repo` (repo-based linking). Contains `orgId`, `remoteName`, and a `projects` array mapping directories to Vercel project IDs.

Either file means the project is linked. Check for both.

**Do NOT** use `vercel project inspect`, `vercel ls`, or `vercel link` to detect state in an unlinked directory — without a `.vercel/` config, they will interactively prompt (or with `--yes`, silently link as a side-effect). Only `vercel whoami` is safe to run anywhere.

## Step 1.5: Reconcile environment variables (before any deploy)

When the Vercel CLI is authenticated (`vercel whoami` works), reconcile env before
deploying. A git-push or CLI deploy only sees env vars stored on Vercel; `.env.local`
is gitignored and never travels with the push, so a key the user just added locally
will be MISSING from the build unless you push it up first.

1. Pull what Vercel currently has (development target, the only one readable back):
   ```bash
   vercel env pull .env.local --environment=development --yes
   ```
2. Compare against the keys the code references (`process.env.*`, `NEXT_PUBLIC_*`) and
   anything the user just added to `.env.local`.
3. For each key the build needs that is missing on Vercel, push it via stdin
   (prod/preview are sensitive by default; never `--value`, which can save an empty
   string, bug #16160):
   ```bash
   printf '%s' "$VALUE" > /tmp/v && vercel env add KEY production < /tmp/v && rm /tmp/v
   ```
   Add to `preview` too if previews need it. The CLI cannot target `preview` non-interactively
   on this machine; use the REST API (`POST /v10/projects/{id}/env?teamId=...&upsert=true` with
   `$VERCEL_TOKEN`, see rules/secrets-map.md).
4. Verify without leaking: `vercel env ls` shows names only (sensitive values never
   print). That is your redacted confirmation.

Only the FIRST value of a third-party key is human-supplied; after that you propagate
it. Full provider-by-provider detail is in TOOLS.md "Secrets and env". Skip this step
for static sites that have no env vars.

## Step 2: Choose a Deploy Method

### Linked (`.vercel/` exists) + has git remote → Git Push

This is the ideal state. The project is linked and has git integration.

1. **Push freely; the PR is the review.** The merge is the owner's gate (CLAUDE.md FOUNDATION);
   a push to a feature branch only builds a preview.

2. **Check the branch FIRST, then commit and push:**
   ```bash
   git branch --show-current
   ```
   If that returns `main` or `master`, STOP. Do not push. On the production
   branch a plain `git push` ships PRODUCTION, which this skill must never do.
   Cut a feature branch first, then push that and open a PR:
   ```bash
   git checkout -b feat/<task>
   ```

   Once you are on a non-production branch:
   ```bash
   git add .
   git commit -m "deploy: <description of changes>"
   git push -u origin "$(git branch --show-current)"
   ```
   Vercel automatically builds from the push. Non-production branches get preview
   deployments, which is the only thing this skill produces. The production branch
   gets a production deployment, which is why step 2 refuses to run there;
   production ships only when the user merges the PR to main.

3. **Retrieve the preview URL.** If the CLI is authenticated:
   ```bash
   sleep 5
   vercel ls --format json
   ```
   The JSON output has a `deployments` array. Find the latest entry — its `url` field is the preview URL.

   If the CLI is not authenticated, tell the user to check the Vercel dashboard or the commit status checks on their git provider for the preview URL.

---

### Linked (`.vercel/` exists) + no git remote → `vercel deploy`

The project is linked but there's no git repo. Deploy directly with the CLI.

```bash
vercel deploy [path] -y --no-wait
```

Use `--no-wait` so the CLI returns immediately with the deployment URL instead of blocking until the build finishes (builds can take a while). Then check on the deployment status with:

```bash
vercel inspect <deployment-url>
```

---

### Not linked + CLI is authenticated → Link first, then deploy

The CLI is working but the project isn't linked yet. This is the opportunity to get the user into the best state.

1. **Ask the user which team to deploy to.** Present the team slugs from Step 1 as a bulleted list. If there's only one team (or just a personal account), skip this step.

2. **Once a team is selected, proceed directly to linking.** Tell the user what will happen but do not ask for separate confirmation:
   ```
   Linking this project to <team name> on Vercel. This will create a Vercel
   project to deploy to and enable automatic deployments on future git pushes.
   ```

3. **If a git remote exists**, use repo-based linking with the selected team scope:
   ```bash
   vercel link --repo --scope <team-slug>
   ```
   This reads the git remote URL and matches it to existing Vercel projects that deploy from that repo. It creates `.vercel/repo.json`. This is much more reliable than `vercel link` (without `--repo`), which tries to match by directory name and often fails when the local folder and Vercel project are named differently.

   **If there is no git remote**, fall back to standard linking:
   ```bash
   vercel link --scope <team-slug>
   ```
   This prompts the user to select or create a project. It creates `.vercel/project.json`.

4. **Then deploy using the best available method:**
   - If a git remote exists → commit and push (see git push method above)
   - If no git remote → `vercel deploy [path] -y --no-wait --scope <team-slug>`, then `vercel inspect <url>` to check status

---

### Not linked + CLI not authenticated → Install, auth, link, deploy

The Vercel CLI isn't set up at all.

1. **Install the CLI (if not already installed):**
   ```bash
   npm install -g vercel
   ```

2. **Authenticate:**
   ```bash
   vercel login
   ```
   The user completes auth in their browser. If running in a non-interactive environment where login is not possible, skip to the **no-auth fallback** below.

3. **Ask which team to deploy to** — present team slugs from `vercel teams list --format json` as a bulleted list. If only one team / personal account, skip. Once selected, proceed immediately.

4. **Link the project** with the selected team scope (use `--repo` if a git remote exists, plain `vercel link` otherwise):
   ```bash
   vercel link --repo --scope <team-slug>   # if git remote exists
   vercel link --scope <team-slug>          # if no git remote
   ```

5. **Deploy** using the best available method (git push if remote exists, otherwise `vercel deploy -y --no-wait --scope <team-slug>`, then `vercel inspect <url>` to check status).

---

---

## Agent-Specific Notes

### Claude Code / terminal-based agents

You have full shell access. Do NOT use the `/mnt/skills/` path. Follow the decision flow above using the CLI directly.

For the no-auth fallback, run the deploy script from the skill's installed location:
```bash
bash ~/.claude/skills/deploy-to-vercel/resources/deploy.sh [path]
```
The path may vary depending on where the user installed the skill.

---

## Output

Always show the user the deployment URL.

- **Git push:** Use `vercel ls --format json` to find the preview URL. If the CLI isn't authenticated, tell the user to check the Vercel dashboard or commit status checks.
- **CLI deploy:** Show the URL returned by `vercel deploy --no-wait`. Use `vercel inspect <url>` to check build status and report it to the user.
- **No-auth fallback:** Show both the preview URL and the claim URL:
  ```
  Deployment successful!

  Preview URL: https://my-app-abc123.vercel.app
  Claim URL:   https://vercel.com/claim-deployment?code=...

  View your site at the Preview URL.
  To transfer this deployment to your Vercel account, visit the Claim URL.
  ```

Verify before handing over the link: fetch the preview URL (behind Vercel protection, send the
project's bypass secret from rules/secrets-map.md as the `x-vercel-protection-bypass` header) and
check the page actually renders.

---

## Troubleshooting

### CLI Auth Failure

If `vercel login` or `vercel deploy` fails with authentication errors, fall back to the no-auth deploy script: `bash ~/.claude/skills/deploy-to-vercel/resources/deploy.sh [path]`.
