# SETUP: instructions for Claude

You are Claude Code on a friend's computer. Its owner asked you to set up this shared Claude
setup. **The owner is not technical.** Do every step yourself; they should never read or type a
command.

## Rules while setting up

- **Ask the owner only for clicks that are truly theirs:** signing in, an "Allow" or
  "Authorize", creating an account, adding the Chrome extension, a Mac password, restarting
  Claude Code. When you need one, say exactly what to click, in one line.
- **Check every install command is still current before you run it** (`winget show <id>`,
  `brew info <name>`, or the tool's own docs). Tools change; if one did, use the current way
  and say what changed.
- **Windows commands come first, Mac second.** Until Git is installed, use PowerShell on Windows.
- **Keep a progress note** at `~/claude-setup/.setup-progress` (one line per finished step), so
  "continue setup" after a restart picks up exactly where you stopped.
- Every step can be run twice safely. If a step is already done, say so and move on.

## 0. Look around

Note the operating system, `claude --version`, and which of git, node, python, gh, pnpm and
Chrome already exist. Ask the owner which Claude plan they are on if they know (Pro or higher is
needed for Claude Code).

## 1. Install the tools

**Windows (PowerShell):**
```powershell
winget install -e --id Git.Git               # git, and Git Bash, which Claude Code uses as its shell
winget install -e --id OpenJS.NodeJS.LTS     # Node.js
winget install -e --id Python.Python.3.13    # Python 3: the safety guards NEED it
winget install -e --id GitHub.cli            # gh
winget install -e --id pnpm.pnpm             # pnpm
winget install -e --id Gyan.FFmpeg           # ffmpeg, for the video and audio skills
winget install -e --id Google.CloudSDK       # gcloud, for Search Console later
irm get.scoop.sh | iex                       # Scoop, needed for the Supabase CLI
scoop install supabase poppler               # Supabase CLI; poppler lets Claude read PDFs
```

**Mac (Terminal; needs [Homebrew](https://brew.sh), whose installer asks for the Mac password,
which is the owner's step):**
```bash
brew install node python git gh pnpm ffmpeg poppler supabase/tap/supabase
brew install --cask google-cloud-sdk
```

**Both:**
```bash
npm install -g vercel resend-cli @sentry/cli eas-cli firebase-tools agent-browser @playwright/cli typescript-language-server typescript
npx playwright install
```

Then ask the owner to **close and reopen Claude Code** (new tools need a fresh start) and to
say "continue setup".

## 2. Get this setup

```bash
git clone https://github.com/FabGemYT/FabFriendsClaudeSetup ~/claude-setup
```
It is public, so no login is needed. If `~/claude-setup` already exists, run
`git -C ~/claude-setup pull --ff-only` instead.

## 3. Install it

```bash
node ~/claude-setup/install.mjs
```
Read the last lines:
- **`INSTALLED`, `safety guards: ON`, and every guard check `N/N`:** good. Anything it replaced
  in an existing `~/.claude` was saved first in `~/.claude/backups/setup-<date>/`.
- **`PYTHON 3 IS MISSING`:** install Python (step 1), then run it again.
- **`A GUARD CHECK FAILED`:** stop and tell the owner in one line; do not continue.

Then ask the owner to **restart Claude Code** so the new rules, settings and guards load, and to
say "continue setup".

## 4. Check it is live

Run `bash ~/.claude/skills/health/scripts/health.sh` (about four minutes). Every FAIL line names
its fix. Right after setup, expect exactly these, which the next steps clear: a FAIL for the
missing `SUPABASE_ACCESS_TOKEN` (step 6), and WARNs that Search Console is not set up (step 8)
and that the leftover sweep has not run yet (it runs by itself from the next session). Anything
else is real: fix it before going on.

## 5. Get to know the owner

Ask in plain words, a few questions at a time (AskUserQuestion): their name, what they want to
build, their Claude plan, and the phone they use. Fill in `~/.claude/about-me.md`; it is theirs
and updates never touch it. Every session reads it.

## 6. Their accounts

Do each in the browser, and record each one in `~/.claude/about-me.md` ("Accounts") and every
credential in `~/.claude/rules/secrets-map.md` (names and places, never values).

- **GitHub.** No account yet: open github.com/signup; **creating the account is theirs**. Then
  run `gh auth login --web --git-protocol https`; **they enter the code shown and click
  Authorize**. Then `gh auth setup-git`.
- **Vercel.** vercel.com/signup, **"Continue with GitHub"**. Then `vercel login`. Create a token
  at vercel.com/account/tokens and file it as `VERCEL_TOKEN` in `~/.claude/.env.local`.
- **Supabase.** supabase.com/dashboard/sign-up, **"Continue with GitHub"**. Then
  `supabase login`. Create an access token at supabase.com/dashboard/account/tokens and file it
  as `SUPABASE_ACCESS_TOKEN` in `~/.claude/.env.local`.
- **Tell auto mode whose accounts these are,** so it treats them as the owner's own and not as
  strangers'. Write `~/.claude/my-settings.json` like this, with their real names, then run
  `node ~/claude-setup/install.mjs` again to merge it:
  ```json
  {
    "autoMode": { "environment": [
      "Organization: <name>, a solo founder building <what they build>. One person, no team.",
      "Source control: github.com/<username> and every repository under it. All of them are the owner's own. Pushing branches and opening pull requests there is routine; merging to main is the owner's button.",
      "Cloud provider(s): Vercel (team <team>), Supabase (organization <org>).",
      "Trusted internal domains: <their domains, or none yet>, and the Vercel preview URLs of the team above."
    ] },
    "permissions": { "allow": [] }
  }
  ```

## 7. Claude's own browser

- Install Chrome if it is missing (`winget install -e --id Google.Chrome`, or
  `brew install --cask google-chrome`).
- Make a separate Chrome profile named **Claude Agent**: **The owner clicks** the profile icon,
  Add, then signs in with their Google account.
- In that profile, add **Claude in Chrome** from the Chrome Web Store: **"Add to Chrome", then
  "Add extension"**, then they sign in to it with their Claude account.
- In that profile, sign in to Google, GitHub, Vercel and Supabase, choosing "Sign in with
  Google" or "with GitHub" wherever offered, and tick "Remember me". After this Claude rarely
  needs them to log in again.
- From now on, browser work runs with `claude --chrome` (or Chrome switched on in the desktop
  app). Claude never asks them to log in to something that profile is already signed in to.

## 8. Later, when it is needed (not now)

- **Search Console, when their first site is live.** Run `gcloud auth login` (**they click
  Allow**), then:
  ```bash
  gcloud projects create <short-name>-seo --name="SEO"
  gcloud services enable searchconsole.googleapis.com --project=<short-name>-seo
  gcloud iam service-accounts create gsc-reader --project=<short-name>-seo
  gcloud iam service-accounts keys create ~/.claude/secrets/gsc-service-account.json \
    --iam-account=gsc-reader@<short-name>-seo.iam.gserviceaccount.com --project=<short-name>-seo
  ```
  Put `GSC_SERVICE_ACCOUNT_PATH=<that file>` in `~/.claude/.env.local`, add the service-account
  email as a **Full** user on the property (Search Console, Settings, Users and permissions),
  and check with `py -3 ~/.claude/bin/gsc.py properties` (`python3` on a Mac). Free, no billing.
- **The Hormozi books.** If the owner has the three *$100M* PDFs, they go in a folder named
  `Alex Hormozi Books` inside Downloads. `rules/the-goal.md` reads them from there. Never copy
  them into a project or upload them anywhere.
- **Mobile apps.** An Apple Developer account ($99 a year) and a Google Play account ($25 once)
  are the owner's to create and pay for; Claude does the rest (TOOLS.md).

## 9. Finish

Tell the owner, in three short lines: what is set up, what to say next ("Make me a website for
..."), and that merging a pull request is the one button that puts things live, and it is theirs.

---

## Update (The owner says "update my setup")

1. `git -C ~/claude-setup pull --ff-only` (if the folder is missing, clone it as in step 2).
2. `node ~/claude-setup/install.mjs`, and read its summary.
3. Say in plain words what is new: `git -C ~/claude-setup log --oneline -10`.
4. If `CLAUDE.md`, `settings.json` or anything in `hooks/` changed, ask them to restart Claude Code.
5. If the pull fails because the repository is private right now, say: "The person who shares
   this setup has paused it for now. Nothing on your side changed. Try again later."

Their own files are never touched by an update: `about-me.md`, `rules/secrets-map.md`,
`.env.local`, `my-settings.json`, and everything in `secrets/`.

## If something goes wrong

- **Every command is blocked with "no working Python 3 interpreter":** install Python 3, then run
  the installer again.
- **Something broke after an update:** the previous version of every replaced file is in
  `~/.claude/backups/setup-<date>/`. Put the broken one back, and tell the owner to let the
  person who shares this setup know.
- **Never delete `~/.claude`:** it also holds their sign-in and their history.
