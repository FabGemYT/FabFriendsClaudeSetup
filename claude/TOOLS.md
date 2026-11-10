# Tools Playbook

The standing reference for which tools to install, when, and how, per project type.
The kickoff skill reads this at project start, identifies the type from the PRD and
the deploy-target answer, and runs the matching section. No em-dashes. No secret
values.

Verification dates, stated honestly rather than blanket-refreshed: the bulk of this
file was verified against current reality on 2026-06-11, the Capacitor/Capawesome and
Secrets and env sections on 2026-06-19, and RevenueCat on 2026-06-24. On 2026-07-30 a
full-repo audit re-verified only the local, checkable claims (installed CLI versions,
the MCP server list and their allow-list prefixes, hook wiring and counts, subagent
models). The third-party install commands, pricing, and console click-paths were NOT
re-verified that day. Treat anything older than a few weeks as last-known-good and
re-verify before running, per Law 5.

---

## Governing principles (read first)

1. **CLIs are cheap. Install them globally, once.** A CLI on PATH costs nothing per
   session. The standing global toolbelt: `node`, `npm`, `pnpm`, `git`, `gh`,
   `vercel`, `supabase` (scoop/brew), `eas-cli`, `sentry-cli`, `resend-cli`,
   `agent-browser`. Add a new CLI globally the moment a project type needs it.

2. **Prefer project-scoped MCPs; the old 5-to-7 ceiling no longer applies.** With
   `ENABLE_TOOL_SEARCH=auto:5` set, a deferred tool costs only its NAME in the session
   prompt; the full schema loads on demand when ToolSearch fetches it. That is what
   retired the ceiling, and 11 servers are active today. It is a large discount, not a
   free pass: every connected server still contributes names, still runs as a live
   process or remote endpoint, and still has to be authenticated and trusted. So prefer
   a CLI when one covers the job, and still scope a server to the project that needs it.
   Rules:
   - Prefer a CLI over an MCP when both exist for the same job (e.g. deploy via the
     `vercel` CLI rather than leaning on the Vercel MCP for routine work).
   - Scope MCPs to the project that needs them (`claude mcp add <name> -s project ...`)
     instead of leaving everything on at user scope.
   - No numeric ceiling anymore (Tool Search made the old 5-to-7 rule obsolete; see above).
     Still don't add one a project type has no use for; each connection is a live server to
     maintain even if its schemas are deferred.

3. **Frameworks and engines install per project, never globally pinned.** Next.js,
   Expo, Phaser, Godot: each project carries its own version so projects never fight
   over a global. Use the official scaffolder with `@latest` so the version is always
   current and never drifts in this file.

4. **Per-PRD init rule.** Do not set up tooling by habit. kickoff reads this playbook,
   maps the PRD to one project type below, and runs only that section's setup. A web
   game does not get a Supabase MCP; a Roblox game does not get Vercel.

---

## Web app: Next.js + Supabase + Vercel

The default stack. Web-first unless the PRD explicitly needs native app stores.

**Scaffold (per project):**
```bash
npx create-next-app@latest        # TypeScript + Tailwind + App Router
npx shadcn@latest init            # shadcn/ui base; customize tokens, never ship stock
```
Register the premium registries in `components.json`, then pull heroes and motion
from them (per `rules/design.md`, "Component stack"):
```json
"registries": {
  "@aceternity": "https://ui.aceternity.com/registry/{name}.json",
  "@magicui": "https://magicui.design/r/{name}.json"
}
```
```bash
npx shadcn@latest add @aceternity/<x>     # or @magicui/<y>
```

**Backend (Supabase):** schema, migrations, RLS policies, and type generation go
through the Supabase MCP. Local stack when needed: `supabase init`, `supabase start`,
`supabase db push`. Skills: `supabase`, `supabase-postgres-best-practices`.

**Deploy (Vercel):** previews via the `vercel` CLI (or the Vercel MCP
`deploy_to_vercel`); surface the preview URL. Production ships automatically when the
user merges to main. Never run `vercel --prod` (deny-listed by design). Skill:
`deploy-to-vercel`.

**MCPs to project-scope (2):** Supabase, Vercel. Supabase and Vercel are claude.ai
account connectors; they ride your login. Keep them on for this project, off for project
types that do not touch a backend or a deploy. shadcn components come through the shadcn
CLI (`npx shadcn@latest search|view|docs|add`); its MCP server was retired 2026-10-30
(Machine hygiene).

**Design pipeline (no UI ships without it):** generate, then agent-browser desktop
(1440px) screenshot, then the design-reviewer subagent critiques against premium
standards, then iterate 2 to 3 rounds. Mobile and tablet via `playwright-cli` in real
device profiles (iPhone, Pixel, iPad). Hand the preview URL to the user for the
real-phone check, the mobile source of truth. Skills: `frontend-design-official`,
`ui-ux-pro-max`, `impeccable`, `web-design-guidelines`. Animation/video: `hyperframes`
(the router; it owns the animation domain via `hyperframes-animation` since the standalone
`gsap` skill was retired upstream). Framework patterns: `vercel-react-best-practices`.

**Analytics (PostHog), when live:** wire PostHog once the app has real traffic, not at
scaffold time. The PostHog MCP needs an OAuth sign-in (human step, see the
credential-gated section).

**Errors (Sentry):**
```bash
npx @sentry/wizard@latest -i nextjs
```
Use the Sentry MCP for issue triage, or the `sentry-cli` for releases and sourcemaps.

---

## Mobile app: Expo + EAS + Supabase backend

Only when the PRD explicitly wants a native iOS/Android/App-Store app.

**Current Expo workflow (verified):** the global `expo-cli` is deprecated. Use the
local CLI bundled in each project via `npx expo`, and the separate global `eas-cli`
for cloud builds and store submission.
```bash
npx create-expo-app@latest        # scaffold (carries its own local Expo CLI)
npx expo start                     # dev server; press w for web, scan QR for device
npx expo start --web               # web target for the agent-browser screenshot loop
```
Never `npm i -g expo-cli`.

**EAS (global CLI, installed: eas-cli/20.1.0):**
```bash
eas login
eas build:configure
eas build -p ios            # or -p android; cloud build, returns an install URL
eas update                  # OTA updates
eas submit -p ios           # store submission: deny-listed, human-gated final step
```
Building previews is free; `eas submit` and `eas build --auto-submit` are deny-listed
because store publishing is a deliberate human action.

**Screenshot loop:** Expo Go QR (scan with a real phone, the mobile source of truth)
plus Expo web (`npx expo start --web`) for the agent-browser desktop capture. Skill:
`react-native-best-practices`.

**Backend:** Supabase, same as the web section (project-scope the Supabase MCP).

**MCPs to project-scope:** Supabase (and Vercel only if shipping a companion web or
marketing site). The app-store MCP is added only when publishing, and it is
credential-gated (see below).

---

## Mobile app (Capacitor): Capawesome Cloud

For a Capacitor / Ionic / Cordova app (for example a webview app that loads a remote
URL), not Expo or React Native. Expo/RN apps use the EAS section above; Capawesome
does not target them. Capawesome Cloud is the agent-drivable replacement for Ionic
Appflow (Appflow access ends 2026-12-31).

**CLI (Node 20+, no global install needed):**
```bash
npx @capawesome/cli@latest --help
npx @capawesome/cli apps:list --json        # --json on many (not all) commands, for agent parsing
```
**Authenticate once (persists across sessions, like `vercel login`):**
```bash
npx @capawesome/cli login        # interactive; then `whoami` to confirm. The agent stays logged in.
```
After this one login the agent builds, signs, and submits for every app with no token
handling and no passwords (Capawesome holds the signing identity, entered once in the
Console). For CI only, use `login --token $CAPAWESOME_TOKEN` (token from the Console, never
committed). REST API base: `https://api.cloud.capawesome.io/v1`.

**Official Agent Skill (optional, needs user approval to install third-party code):**
```bash
npx skills add capawesome-team/skills              # whole collection
# or just the cloud skill via the plugin marketplace:
claude plugin marketplace add capawesome-team/skills
claude plugin install capawesome-cloud@capawesome-skills
```
There is NO Capawesome MCP yet (Capawesome says "launching soon"); drive it via the
CLI, the REST API, or the Skill, not an MCP.

**No-Mac cloud builds (signed iOS and Android, Apple Silicon, 1 to 3 min):**
```bash
npx @capawesome/cli apps:builds:create --platform ios   # or android
```
Upload signing identities once in the Console; Capawesome signs every build.

**OTA Live Updates (web layer, skips store review):**
```bash
npx @capawesome/cli apps:liveupdates:create --git-ref main --channel production
npx @capawesome/cli apps:liveupdates:rollout --channel production --percentage 50   # gradual rollout control
```
`apps:liveupdates:upload` is for uploading a pre-built local bundle (it does not build
from a git ref). For a webview app that already loads a live remote URL, OTA Live
Updates are largely redundant; the valuable parts here are the no-Mac cloud builds and
store submission.

**Store submission (one chain, multiple destinations):**
```bash
npx @capawesome/cli apps:builds:create --destination TestFlight   # or App Store, Google Play, Firebase App Distribution
```
`--destination` references a destination configured once (App Store Connect or Play
credentials), set up in the Console or via `apps:destinations:create`.

**Pricing and credential gate:** NO free tier (14-day trial; Live Updates from $9/mo,
full platform from $19/mo). Plus an Apple Developer account ($99/yr) and a Google Play
account ($25). One-time human steps: pick a plan, create the developer accounts,
generate the Capawesome API token in the Console. The agent then stores the token as a
secret (never printed, never committed) and runs the lifecycle.

**MCP:** none (use CLI/API/Skill). Re-check for a Capawesome MCP before assuming MCP control.

---

## In-app purchases and subscriptions (RevenueCat)

For any app selling subscriptions or IAP. The Capacitor apps use it through
`@revenuecat/purchases-capacitor`. RevenueCat is agent-drivable (verified 2026-06-24).

**Surfaces:**
- REST API v2 (`https://api.revenuecat.com/v2`): the config and metrics layer, apps, products,
  entitlements, offerings, packages, paywalls, and revenue / MRR / churn / charts. Bearer with a v2
  secret key (`sk_...`). This is the agent's main surface.
- REST API v1 (`https://api.revenuecat.com/v1`): subscriber-level ops that still live only here,
  promotional grant/revoke, refunds, deferrals, subscriber lookup.
- Official hosted MCP at `https://mcp.revenuecat.ai/mcp` (a natural-language wrapper over v2).
- Official AI Toolkit (Claude Code plugin) bundling RevenueCat integration skills.
- NO official CLI (only unofficial community ones, skip them; use the API or MCP).
- Webhooks stay as the event-push channel (already in use), unchanged.

**Wire it (project-scope the MCP, per the governing principle):**
```bash
# The v2 secret key is the core autonomy enabler. Account-level, so it lives in
# ~/.claude/.env.local and is auto-loaded into every session by hooks/load-env.sh.
# Mint it once (human): RevenueCat dashboard, Project settings, API keys, V2.
#   REVENUECAT_API_KEY_V2_WRITE=sk_***     (plus a read-only key for reporting jobs)

# Integration skills (cheap, instruction-only):
claude plugins marketplace add RevenueCat/ai-toolkit
claude plugins install RevenueCat                 # cross-platform integration skills
claude plugins install revenuecat-play-billing    # Google Play subscription lifecycle skills

# The MCP (~26 tools) is PROJECT-SCOPED, add it only inside a RevenueCat app repo, never globally:
claude mcp add --transport http revenuecat -s project https://mcp.revenuecat.ai/mcp
# headless/token use: append  --header "Authorization: Bearer $REVENUECAT_API_KEY_V2_WRITE"
```

**The lifecycle (critical: RevenueCat MIRRORS store products, it does not create them):**
1. The agent creates the real IAP product via the App Store Connect API plus the Google Play API
   (the wired Apple + Google creds, see "Secrets and env" and "Store listing automation").
2. Store review and the paid-apps / banking / tax agreements clear (human-only).
3. The agent imports that product id into RevenueCat (MCP or v2) and attaches it to an entitlement.
4. The agent builds the entitlement, offering, package, and paywall, then reads v2 metrics to report revenue.

**Agent can drive:** RevenueCat apps, mirroring a store product id, the entitlement/offering/package/
paywall hierarchy, promotional grant/revoke, subscriber lookups, and revenue/metrics reporting.

**Human-only:** mint the v2 secret key (dashboard), the one-time dashboard handshake that connects your
App Store Connect key and Google service-account into RevenueCat, pricing decisions, and store/IAP review.

---

## Store listing automation (App Store Connect + Google Play)

Fill the store listings from a plain-English prompt instead of by hand. About 85 to 90
percent of both listings is API-automatable; a few forms stay human-only (below).
PREREQUISITE: the binary is already built and submitted (Capawesome), so a build exists in
App Store Connect and an AAB/track exists in Play. This step fills LISTING metadata; it
does not build or sign.

**Standard tool: fastlane** (free, idempotent, folder-based; installed per app repo):
```bash
gem install fastlane            # in the app repo (or brew install fastlane on macOS)
fastlane deliver                # Apple: pushes metadata/ + screenshots/
fastlane supply                 # Google: pushes metadata/android/ + images/
```
The `app-publish` MCP (github.com/mikusnuz/app-publish-mcp, ~91 tools) is an OPTIONAL
conversational layer over the SAME two APIs and credentials; it adds no coverage.

**Listings live as files in the app's git repo (source of truth), not optional.** Google's
API cannot read screenshots back, so the local folder must be authoritative and every run
re-uploads. The agent writes the prompt into the folder conventions both tools read:
- Apple: `fastlane/metadata/<locale>/` (name, subtitle, description, keywords,
  promotional_text, support_url, marketing_url, release_notes) + `screenshots/<locale>/`.
- Google: `fastlane/metadata/android/<locale>/` (title, short_description, full_description,
  video, changelogs/<versionCode>) + `images/` (icon 512x512, featureGraphic 1024x500,
  phoneScreenshots/, sevenInchScreenshots/, tenInchScreenshots/).

**Two raw-API bolt-ons fastlane does not cover** (same credentials):
- Apple pricing/availability: POST `appPriceSchedules` and `appAvailabilities` (v2 schedule
  model; deliver's old price_tier is deprecated). Set once per app, not per release.
- Google Data Safety (NOT UI-only, common myth): POST
  `androidpublisher/v3/applications/<pkg>/dataSafety` with the declaration as a CSV in
  Google's template (`{safetyLabels: <csv>}`). Sits outside the edits transaction.

**Default to STAGING, never auto-submit** (matches the human-controls-go-live rule):
- Apple: run deliver WITHOUT `submit_for_review:true` so changes wait for you to submit.
- Google: commit with `changesNotSentForReview=true` so edits stage for review in Console.
The agent fills and stages everything, then surfaces a preview plus the human-only checklist.

**Stays human-only (the few forms no clean API sets):**
- Apple App Privacy nutrition label (first time per app; the .p8 key cannot set it, only a
  2FA-fragile Apple-ID session can, so do it once by hand). The privacy POLICY URL is
  separate and IS API-fillable; do not confuse them.
- Google content-rating (IARC) questionnaire and the "App content" / target-audience
  declarations (Console-only, no API resource exists).
- Google category and store-listing tags (set once in Console).
- The legal ANSWERS to privacy/rating questions, demo-account creds for review, and the
  final submit/release click.
The agent may best-effort drive the Console-only forms via agent-browser, but that is
screen-scraping a login-gated form, not an API, so a human confirms.

**Not a listing field (build artifacts):** the Apple 1024 marketing icon (from the build's
asset catalog) and the Google launcher icon (baked into the AAB). Changing them means a new
Capawesome build, not a listing edit. The Google 512 STORE icon IS API-fillable.

**Credentials (two, account-level, reused for every app):** the Apple App Store Connect API
key (.p8 + Key ID + Issuer ID, role App Manager) and a Google Cloud service-account JSON
(Android Publisher API enabled, invited into Play Console). See "Secrets and env".

---

## Web game: Phaser

Browser game, no backend by default.

**Scaffold (per project):** use the official CLI; choose Web Bundler, then Vite.
```bash
npm create @phaserjs/game@latest
```
Phaser 4 is the current major line (rebuilt WebGL renderer). Add to an existing
project instead with `npm install phaser`.

**Deploy:** Vercel, as a static Vite build. Previews via `vercel`; production on merge
to main. No `vercel --prod`.

**MCP:** none. A Phaser game gets no MCP unless it grows a backend (leaderboards,
auth, saves), in which case add Supabase and project-scope its MCP like the web app.

---

## Native game: Godot

Documented only. **Do not install the engine now.** Install Godot only when an actual
Godot project starts.

**Install when a Godot project begins:**
```bash
# Windows
winget install -e --id GodotEngine.GodotEngine
# or: scoop bucket add extras && scoop install godot

# macOS
brew install --cask godot

# Linux
flatpak install flathub org.godotengine.Godot
```
Decide GDScript (default build) versus the .NET/C# build up front; they are different
downloads. Version-check after install: `godot --version`.

**Deploy:** engine-native export. An HTML5 export can sit on Vercel as a static build;
desktop and mobile exports are platform-native.

**MCP:** none.

---

## Roblox: Studio + Rojo + Studio MCP

The one project type where an MCP is essential. Roblox Studio is a closed application,
so the Studio MCP is the only programmatic bridge an AI assistant has into the place.

**Roblox Studio:** install from create.roblox.com and sign in (human download and
login).

**Rojo (filesystem to Studio sync):** manage it with the Rokit toolchain manager so
the version is pinned per project.
```bash
# Install Rokit once (Rust/cargo route; or use the official installer binary)
cargo install rokit --locked && rokit self-install

# Per project
rokit add rojo-rbx/rojo        # pins Rojo in rokit.toml
rokit install
rojo init                       # create the project structure
rojo serve                      # live sync to Studio
rojo build                      # build a place/model file
rojo plugin install             # install the companion Studio plugin
```
Direct alternative without Rokit: `cargo install rojo --locked`, or download the
binary from Rojo's GitHub Releases.

**Roblox Studio MCP (essential):** use the official standalone server.
- Repo: `github.com/Roblox/studio-rust-mcp-server`.
- Easiest path (no Rust): download the latest release binary (`rbx-studio-mcp.exe` on
  Windows, the macOS zip on Mac), run the installer, restart Studio and the AI client.
  It auto-configures the MCP client and installs the Studio plugin.
- From source: `cargo run` from the repo root (Rust required for the source build
  only, not for the release binary).
- Roblox has shifted ongoing investment toward a built-in Studio MCP server; check
  Studio's Assistant settings for the in-app toggle and prefer it once it is available
  on your Studio build.

**Credentials:** none beyond a Roblox account and Studio login (human step).

---

## Secrets and env (cross-cutting)

The one rule: .env.local (gitignored) is the local source of truth. The user seeds
each secret VALUE once (the irreducible human gate); the agent then propagates it to
the remote stores and re-hydrates .env.local on demand.

**The inventory of what exists and where it lives is `rules/secrets-map.md`.** Read it
before asking the user for anything. **Handling rules are in CLAUDE.md "Secrets":** the
chat is a trusted channel, the user gets their own credentials on request in any form
they ask for, and no session ever advises rotation or hands the user a task Claude can do.

**File first, then reference (the rule that makes propagation actually work).**
`block-secret-leak.sh` scans Bash commands and hard-blocks a literal live key, so the
obvious one-liner (`vercel env add KEY prod` with the value typed in) fails mid-task.
Always write the value to its scanner-exempt home first (`.env.local`, `~/.claude/secrets/`),
then read it into a shell variable and pass `$VAR`:
```bash
# correct: value never appears literally in the command
VALUE=$(grep -E '^KEY=' .env.local | cut -d= -f2-)
printf '%s' "$VALUE" > /tmp/v && vercel env add KEY production < /tmp/v && rm /tmp/v
```

**Who provides each secret (decision table, not a guess):**

| Secret | Source | Agent-fetchable or human-must-paste |
| --- | --- | --- |
| Supabase anon / publishable key | Supabase MCP/CLI/dashboard | Agent-fetchable once the project exists (MCP `get_publishable_keys`) |
| Supabase service_role key | Supabase dashboard / API | Agent-fetchable via API once the project exists; high-sensitivity |
| Existing Vercel project env | `vercel env pull` | Agent-fetchable (development target only; see below) |
| OpenAI / Anthropic API key | provider dashboard + billing | Human-must-paste |
| Resend API key | resend.com/api-keys | Human-must-paste |
| Sentry DSN | Sentry dashboard or Sentry MCP | Human-must-paste, or agent via MCP |
| Stripe keys | Stripe dashboard | Human-must-paste |
| OAuth client secrets | the provider's console | Human-must-paste |
| Apple ASC .p8, Google Play JSON | Apple / Google dashboards | Human-must-paste (download once) |
| Capawesome token | Capawesome Console | Human-must-paste |
| RevenueCat v2 secret key | RevenueCat dashboard, API keys | Human-must-paste. Lives at `~/.claude/secrets/revenuecat-v2.json` (NOT .env.local, which this table claimed until 2026-08-01; sessions followed that and asked for a key the user had already given) |

**Vercel env, exact non-interactive commands:**
```bash
# Sync DOWN into the gitignored local file (development target reads back):
vercel env pull .env.local --environment=development --yes

# Write a value UP without hanging or saving empty. prod/preview are SENSITIVE by
# default, so feed the value over stdin and NEVER use --value (open bug #16160 saves
# an empty string with --value + sensitive):
printf '%s' "$VALUE" > /tmp/v && vercel env add KEY production < /tmp/v && rm /tmp/v

# Verify without leaking (names only; sensitive values never print) = redacted confirmation:
vercel env ls production
```
Caveats: prod/preview values are sensitive and CANNOT be pulled back in plaintext, so
Vercel is a write-only store for them (only development-target vars sync down). And
`vercel env add preview` can hang on a git-branch prompt (#15763); run it with
`</dev/null` or a timeout as a guard.

**Supabase Management API (the whole dashboard, scriptable).** A session once told the user that
adding a Google client ID to Supabase Auth was impossible because the MCP has no auth tool. The
MCP indeed does not, but the Management API does, and this is exactly the "no homework" failure.
Needs `SUPABASE_ACCESS_TOKEN` (an `sbp_` PAT) which `load-env.sh` exports into every session; it
also authenticates the `supabase` CLI, which is otherwise not logged in at all.
```bash
# auth providers, incl. native-Google "Authorized Client IDs" (web id FIRST, comma-joined)
curl -X PATCH "https://api.supabase.com/v1/projects/$REF/config/auth" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '{"external_google_enabled":true,"external_google_client_id":"WEB.apps.googleusercontent.com",
       "external_google_additional_client_ids":"IOS_ID,ANDROID_ID","external_google_skip_nonce_check":true}'
```
The same `/config/auth` object holds every `smtp_*`, `rate_limit_*`, `mfa_*` and `hook_*` field;
other paths cover SSO providers, custom hostnames, network restrictions, backups (incl. PITR),
secrets, function deploys, pause/restore/upgrade. Declarative alternative: `[auth.external.google]`
in `supabase/config.toml` plus `supabase config push --project-ref X --yes` (note: there is no
`config pull`, so dashboard edits drift silently, and `additional_client_ids` is not a documented
config.toml key, so set that one via the API).

**Vercel env vars: use the REST API, not `vercel env add`.** Two upstream bugs are still open
(2026-08-01): #16160 (`--value` with `--sensitive` exits 0 and saves an EMPTY string) and #15763
(`preview` hangs on a git-branch prompt even with `--yes --force`).
```bash
curl -X POST "https://api.vercel.com/v10/projects/$PROJ/env?upsert=true" \
  -H "Authorization: Bearer $VERCEL_TOKEN" -H "Content-Type: application/json" \
  -d '{"key":"KEY","value":"'"$VALUE"'","type":"encrypted","target":["production"]}'
```
`NEXT_PUBLIC_*` is inlined at build time, so any env change needs a NEW BUILD to take effect;
promote and rollback re-alias existing builds and will never pick it up. That rebuild is a
production change, so it is the user's button: prepare everything, then hand them the one-click
Redeploy link. (The prod-deploy guard covers the REST API too since 2026-08-01, so a curl to
`api.vercel.com/.../promote/` or a `target:"production"` deployment is blocked exactly like the CLI.)

**Supabase Edge Function secrets:**
```bash
supabase secrets set RESEND_API_KEY=re_*** --project-ref <ref>      # one or many, non-interactive
supabase secrets set --env-file ./supabase/.env --project-ref <ref> # many from the local source of truth
supabase secrets list --project-ref <ref>                           # names + digest, never plaintext
```

**Universal credentials, the "set up once, use everywhere" model.** Most stack tools
persist their own login, so the agent needs nothing stored after a one-time interactive
login: run `vercel login`, `supabase login`, and `capawesome login` ONCE and every later
command stays authenticated, across sessions. Those cover web deploy and mobile
build/sign/submit with zero key handling and no passwords. The only account-level secrets
NOT behind a persisted login are the two store-listing API credentials, reused for every
app: the Apple App Store Connect API key (`.p8` + Key ID + Issuer ID) and the Google Play
service-account JSON. Keep the key files in a gitignored `~/.claude/secrets/` folder (the
allowlist `.gitignore` excludes it, so it can never be committed) and their paths/IDs in
`~/.claude/.env.local`, which the agent reads when filling listings:
```
APPLE_KEY_ID=***
APPLE_ISSUER_ID=***
APPLE_P8_PATH=~/.claude/secrets/AuthKey_XXXX.p8
GOOGLE_SERVICE_ACCOUNT_PATH=~/.claude/secrets/play-service-account.json
```
The `.p8` is download-once and a lost Android upload key is painful, so keep your own
encrypted backup of these files somewhere safe (not a shared drive with a reused password).
No third-party secret manager is needed for a solo setup; persisted logins plus this one
gitignored file cover it. A SessionStart hook (hooks/load-env.sh) auto-loads this
.env.local into the environment at every session start, so the agent never reads the file
or hunts the disk for these account-level creds; they are present as env vars in every project.

---

## Credential-gated MCPs (documented ready, NOT activated)

These are wired-and-waiting. Do not activate any of them until the named credential
exists. Never inline a key or commit one; pass file paths and IDs through env only.

### app-publish (App Store Connect + Google Play), for mobile publishing

Unified server covering both the Apple App Store Connect surface (the "asc" side) and
Google Play Console in one MCP. Repo: `github.com/mikusnuz/app-publish-mcp`. There is
no npx form; build it, then register it project-scoped. Verify the repo and review its
source before building (per `rules/design.md`, "Security (registry components are third-party code)"); this runs code
you did not write, locally, with store credentials in scope.
```bash
git clone https://github.com/mikusnuz/app-publish-mcp
cd app-publish-mcp && npm install && npm run build

# Register project-scoped (claude mcp add is ask-gated, so it will prompt):
claude mcp add app-publish -s project \
  -e APPLE_KEY_ID=*** \
  -e APPLE_ISSUER_ID=*** \
  -e APPLE_P8_PATH=/path/AuthKey_XXXX.p8 \
  -e GOOGLE_SERVICE_ACCOUNT_PATH=/path/service-account.json \
  -- node /path/to/app-publish-mcp/dist/index.js
```
**Credentials the user must supply:**
- Apple: an App Store Connect API key. Gives `APPLE_KEY_ID`, `APPLE_ISSUER_ID`, and the
  downloaded `AuthKey_XXXX.p8` file (`APPLE_P8_PATH`). From App Store Connect, under
  Users and Access, Integrations / Keys. Requires an Apple Developer account.
- Google: a Google Play service account JSON (`GOOGLE_SERVICE_ACCOUNT_PATH`). Enable
  the Google Play Android Developer API, create the service account, then grant it
  access in the Play Console.

### PostHog (analytics)

Already added at user scope; goes live only after an OAuth browser sign-in. Run `/mcp`
inside Claude Code and complete the PostHog sign-in (human step).

### Sentry (error triage)

OAuth browser sign-in via `/mcp`, same pattern as PostHog, if not already connected.

---

## Quick map

| Project type | Scaffold | MCPs (project-scoped) | Deploy | Credential gate |
| --- | --- | --- | --- | --- |
| Web app | create-next-app + shadcn | Supabase, Vercel, shadcn | Vercel | PostHog OAuth (when live) |
| Mobile app (Expo) | create-expo-app + eas-cli | Supabase (+ Vercel if web companion) | EAS build, store submit human-gated | app-publish (Apple + Google) |
| Mobile app (Capacitor) | Capawesome CLI + Skill | none (CLI/API; MCP coming) | Capawesome cloud build + store submit | Capawesome token + Apple/Google |
| Web game | create @phaserjs/game | none | Vercel static | none |
| Native game | Godot (install on start) | none | engine export | none |
| Roblox | Studio + Rojo | Roblox Studio MCP (essential) | Studio publish | none |

---

## Google Cloud and Firebase (installed 2026-08-01)

`gcloud` (SDK 578) and `firebase-tools` (15.25) are installed and on PATH. Both need ONE
interactive `gcloud auth login` / `firebase login`; the refresh token then persists in
`%APPDATA%\gcloud` across all later sessions, so nothing is stored by this workflow.

Scriptable, so never hand these to the user: API enablement (`gcloud services enable ...`),
service accounts and IAM bindings, **API keys created pre-restricted** (always mint Gemini and
other keys as `gcloud services api-keys create --api-target=service=... --allowed-application=...`,
never an unrestricted console default), Firebase app registration and SHA fingerprints
(`firebase apps:create android`, `firebase apps:android:sha:create`, `firebase apps:sdkconfig`).

**No API creates Google Sign-In OAuth clients.** Verified 2026-08-01: no `gcloud` command, no
Terraform resource, and the `gcloud iap oauth-clients` path produced IAP-locked clients and was
permanently shut down in March 2026. Firebase's `androidApps.create` does NOT mint one either.
This is console-only, which means it is BROWSER work, not user homework: drive Cloud Console in
the Agent profile. Same for reading the Play app-signing SHA-1 (no androidpublisher resource
exposes it). Genuinely human: consent-screen publishing and verification, billing, first 2FA.

## Machine hygiene: what a session actually costs, and how to reclaim it

**Where Python lives (found 2026-10-10).** `py -3`, which every guard hook runs, resolves to
`the folder Python is installed in`: the Python install manager put
the interpreter inside that Downloads folder in July 2026. Deleting or moving that folder blocks every
Bash command in every session (the guards fail closed without Python). `/health` prints the path and
warns while it lives under Downloads. Move it only as a deliberate step with a re-run of `/health`.

Measured on this machine 2026-08-07, because the user runs a terminal per project
and leaves the laptop up for 10 to 30 days:

| Thing | Cost |
| --- | --- |
| `claude.exe` | ~690 MB per session |
| each LOCAL (stdio) MCP server | 2 to 3 `node.exe` processes, ~200 to 300 MB |
| each REMOTE MCP server (posthog, sentry, context7) | zero locally, it is an HTTP endpoint |

So one session is roughly 1.2 GB, and nine terminals is ~10 GB of a 15.4 GB
machine. That is the 65% seen in Task Manager. **Nothing leaks; it multiplies.**
Note the npx wrapper doubles each stdio server (an `npx-cli.js` process AND the
server), and chrome-devtools additionally spawns a telemetry child.

**Reclaiming it:** `claude-cleanup` (`.ps1` + `.cmd` twins in `~/.claude/bin/`) finds
what Claude left running and, with `-Force`, closes it. Since 2026-10-30 it also runs
by itself (next section). Dry-run is the default by hand. It NEVER blanket-kills
`node.exe`: dev servers (next, vite, expo) are node too, and so are every open
session's own helpers. The 2026-08-07 version only knew orphaned MCP servers; the
current one is below.

**The honest split.** This reclaims the Claude share only. Chrome, Windows itself,
and fragmentation after weeks of uptime are not Claude's doing and no script fixes
them; a restart is the only thing that clears those. If the machine is heavy and
`claude-cleanup` reports nothing, the remainder is not Claude.

**The bigger lever is scope (done 2026-10-30, the owner's decision).** `chrome-devtools` and
`shadcn` were user-scope, so they started in EVERY session, ~0.5 GB each time, in
sessions that stay open for days. Since 1 Sep shadcn had 0 calls anywhere and
chrome-devtools was used on two days: a second online store (6 Oct) and a course site (10 Sep).
- `chrome-devtools` is now LOCAL scope in exactly the folders sessions start in for
  those two projects: `~/projects/a second online store`, `~/projects/a second online store/store-app`
  and `~/projects/a course site` (`claude mcp add -s local chrome-devtools -- npx
  chrome-devtools-mcp@latest --isolated`, run in each; stored in `~/.claude.json` under
  that project, next to a second online store' own `delhivery-one`). Browser work elsewhere uses
  agent-browser and playwright-cli, as it already did.
- `shadcn` MCP is removed; `rules/design.md` now names the shadcn CLI (4.23.0 has
  `search`, `view`, `docs`, `add`), which is what sessions were using anyway.
- User scope now holds only posthog, sentry, context7 and expo: all HTTP, nothing runs
  locally. Open sessions keep the helpers they started with until they restart.
- **Ending a helper in Task Manager breaks it for that session.** An interactive session
  does NOT restart a stdio MCP server that exits (docs, "Stdio servers that exit or fail
  to start": marked failed until `/mcp` Reconnect; only `claude -p` restarts on next
  call). an online store and a live web game had already lost theirs this way on 2026-10-29.

### Leftovers after Claude stops a command (measured 2026-10-29, Claude Code 2.1.312)

**What leaks, and why.** When Claude stops a background command (TaskStop), a command
times out, or a session closes, Claude Code kills the outer Git Bash shell with
`taskkill /PID <shell> /T /F` (read in the binary). That walk follows Windows parent
links, and Git Bash tools (`sleep`, `tail`, `grep`, `find`, `timeout`) have none: a
Git Bash fork-and-exec leaves their Windows parent dead the moment they start, while
Git Bash's own process table (`ps -l`) still knows their real parent. So they keep
running. Native programs (node) survive the same way whenever something between them
and `claude.exe` has already exited (a `(cmd &)` detach, a dead launcher). Open
upstream as anthropics/claude-code #91523, #92583 and #97752 (the last one is
`git.exe` piling up until memory runs out; not seen on this machine).
- Proved with a 10-second A/B in this session: a stopped background `node` died, a
  stopped background `sleep` survived. On the day, three a live web game alarms that the
  memory reaper had "stopped" hours earlier were still running, and a `tail -2` from
  24 Oct (piped from an agent-browser launch, waiting for an end that never comes)
  had used 26 minutes of CPU.
- **Windows misjudges Git Bash tools in BOTH directions.** A live timer inside a
  running background task also shows a dead Windows parent. Any rule built on the
  Windows parent chain alone would kill live timers. Judge Git Bash processes by
  Git Bash's own table; judge native ones by Windows, checking the parent's start
  time so a reused PID does not count as a parent.

**What closes them now.** `hooks/sweep-leftovers.sh` runs `claude-cleanup.ps1 -Force`
in the background (`"async": true`) on SessionStart and Stop, at most once a minute
per event across all sessions; a reply never waits for it. It closes a group only if
it is orphaned, traceable to Claude, and unused:
- **Closed:** Git Bash tools whose shell is gone (nothing can ever read them); stdio
  helpers (MCP servers, the TypeScript language server) whose session is gone, even
  inside an open project; servers and scripts in a project folder with no open
  session. Open sessions come from Claude Code's registry, `~/.claude/sessions/<pid>.json`
  (pid, cwd, sessionId, procStart; a stale file whose pid was reused is ignored).
- **Never closed:** anything under a live `claude.exe`; claude, explorer, terminals,
  VS Code; the shared agent-browser daemon; `~/.claude/scheduled` jobs; anything with a
  visible window; anything under 2 minutes old; anything in a project whose session
  is still open (a live web game starts its test server as `(pnpm start -p 3100 > log &)`,
  which looks orphaned while in use); anything a program on this machine or the LAN
  is connected to; anything it cannot trace to a project. An internet connection
  does NOT protect a leftover: a script still spending on a paid API with no session
  behind it is exactly what spending rule 6 says must stop.
- **Brake:** more than 40 candidates at once closes nothing and logs why.
- **Evidence trail:** every close goes to `~/.claude/state/cleanup.log`; each real
  sweep's summary to `state/cleanup-last-run.json`, which `/health` reads (check 4c4).
- **Tests:** `py -3 hooks/tests/test-sweep-leftovers.py`, 14 cases on real processes
  (live and dead timers, loops inside and outside an open project, servers open,
  closed, connected and untraceable, an orphaned tsserver, the grace period, the
  brake, the log), about 20 s; it closes only its own marked processes. Run it after
  ANY edit to `claude-cleanup.ps1`. First real run (2026-10-30 00:43): closed the
  24 Oct `tail` and the 3 dead alarms, nothing else.
- **Two traps found building it.** Windows PowerShell 5.1 throws "Argument types do
  not match" for `@(<generic List>)` inside an object literal (use `.ToArray()`), and
  under `$ErrorActionPreference = 'Stop'` a native tool's redirected stderr becomes a
  terminating error. A headless `claude -p` exits right after its reply and cuts an
  async Stop hook short; interactive sessions stay alive, so their sweeps finish.
- **Its limit:** closing a terminal window runs no hook. That session's leftovers are
  closed the next time any session starts or finishes a reply.

**A stopped script that acts later keeps running while its session is open (2026-11-08).**
The sweep keeps any leftover whose folder or script path belongs to a session that is still
open ("its project's session is still open"): that protects dev servers, and it protects a
stopped script too. On 7 Nov a live web game stopped a background `bash <script>.sh` (in the
session's scratchpad) that slept until 04:30 UTC the next morning and then sent player
email. TaskStop answered "Successfully stopped", the session stayed open, and 11.5 hours
later the script sent 10 real emails a day early. The check made after the stop looked for
the file the script would write, which a sleeping script had not written yet.
- After stopping a background task that would ACT later (send, write, spend), find it by
  its command line (`Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match
  '<script name>' }`), close the tree (`taskkill //PID <pid> //T //F`) and list again. A
  stop message says nothing about the children.
- Prove "nothing will happen" from the process list, never from missing output files.
- Put timed actions in a session cron (CronCreate / CronDelete), not a sleeping
  background script: deleting a cron is reliable, killing a sleeper is not.

### Idle sessions: the TypeScript server sleeps until needed (2026-10-30)

Sessions here stay open for days and sit idle most of the time: in the week to 30 Oct,
an online store was idle ~121 of 168 hours and a live web game ~118, while their TypeScript language
servers held 1.24 GB and 0.46 GB the whole time. The same sweep (`claude-cleanup.ps1`,
SessionStart and Stop) now closes the language server of any session whose own registry
entry (`~/.claude/sessions/<pid>.json`: `"status": "idle"`, `"statusUpdatedAt"`) shows it
idle for `-IdleHours` (2). Only the `typescript-language-server` child of that session's
`claude.exe` and its subtree; never a busy session, never its Claude, MCP helpers,
background commands, timers or servers.
- **Why it is safe (read in the 2.1.312 binary):** the LSP manager restarts a server
  whose state is `stopped` or `error` before the next use (`if(state==="stopped"||
  state==="error") await start()`), and the crash counter resets to 0 on every
  successful start (`s="running",S=0`). `maxRestarts` (default 3) only stops a crash LOOP.
  The typescript-lsp plugin sets neither `restartOnCrash` nor `maxRestarts`.
- **Proved live in this session:** started the server, closed it with the sweep's exact
  method (`taskkill /T /F` on the `cmd.exe` wrapper), and the next LSP request just worked,
  on fresh PIDs. Four close-and-use cycles in a row, past the 3-crash limit, all fine.
  (Needs TypeScript in the workspace; a folder without `node_modules/typescript` fails
  with "Could not find a valid TypeScript installation", which is unrelated.)
- **What the owner may see:** until that session next touches code, its status area can count
  one LSP failure (`setupIssues.lspFailedCount`) and `/plugin` keeps an error entry. Both
  are cosmetic. The first code edit after a long idle waits a few seconds for the reload.
- **Worth keeping the server:** its diagnostics reached Claude 635 times in an online store,
  961 in a live web game and 162 in a live mobile app across those sessions, catching real errors.
- Tests: `test-sweep-leftovers.py` cases 15 to 19 run three fake sessions (a renamed
  node.exe as claude.exe with a temp registry): only the 3-hour idle one loses its server.

### The memory reaper (measured 2026-10-29, Claude Code 2.1.312)

Claude Code stops an idle session's background commands (`run_in_background`) when the
OS reports CRITICAL memory pressure: idle 30+ minutes, no turn or subagent running.
The env-vars docs say "Windows has no memory-pressure signal, so this variable has no
effect there". The binary disagrees: the reaper listens to the runtime's
`memoryPressure` event, and on anything but Linux its double-check is
`"<platform>: kernel verdict taken as is"`. Between 9 Sep and 29 Oct 2026 it stopped
this machine's background work 32 times (a live web game 16, an online store 12, a live mobile app 3,
WalmartFab 1): builds, test runs, a dependency reinstall, and alarms. Each stopped
alarm's `sleep` kept running anyway (section above), so it freed almost nothing.

**Off since 2026-10-30:** `"CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP": "1"` in the
`settings.json` env block. Not on any of the binary's ignored-in-settings lists. The
check reads `process.env` each time a background command STARTS (the env getter is
live, not a startup snapshot), and a running session applies a settings-file save to
its own environment at once: verified in the session that made the change, where
`echo $CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP` printed 1 with no restart. Commands
already running when the setting changed keep the old behaviour until they end or are
started again. A Windows user variable would do the same job from outside the backup,
so it was not set. `/health` check 4c3 warns if the switch ever disappears.
The trade-off: there is no emergency brake now. If memory truly runs out, Windows pages
to disk instead of Claude stopping idle background work, which is why the leftover
sweep above matters.

### Merged harness changes reach this laptop by themselves (2026-10-30)

The harness that runs is the working copy at `~/.claude`. Sessions (a live web game, an online store,
anywhere the owner learns something) add lessons to it as PRs the owner merges on GitHub, usually
prepared in a scratch worktree, and nothing pulled them back down: on 2026-10-30 this
laptop was 2 commits behind (PR #73, merged 28 Oct, never live).
`hooks/sync-harness.sh` (SessionStart, async, at most once per 10 minutes) fetches
`origin/main` and applies it: a plain fast-forward; or, when the only local edits on the
incoming files are byte-identical to GitHub's (the live-edit-then-PR flow this harness
session uses), `git reset --mixed origin/main` plus a checkout of the untouched files,
which never rewrites an edited file. Anything else (an unsaved edit that differs, local
commits on main, another branch, no network) is left exactly as it is, the reason goes
to `state/harness-sync.log`, and `/health` check 13e warns ("N commits behind GitHub").
The repo's `.gitattributes` (`* text=auto eol=lf`) is what keeps byte comparisons honest
on Windows. Tests: `hooks/tests/test-sync-harness.py`, 11 cases on scratch repos.

**Never write `ref:path` as one argument in a Git Bash script (2026-11-10).** Git Bash
rewrites it before git runs: `origin/main:.gitignore` arrived as `origin\main;.gitignore`,
because a colon beside something that looks like a path reads as a path-list separator.
Every dot-file lookup in the sync's fallback failed, and its restore loop deleted
`.gitignore`, both plugin manifests and the new workflow file the first time a merge
touched dot-files (the PR #80 sync). With `.gitignore` gone, `secrets/` and `.env.local`
showed as files git would add; they were restored before anything was committed. Pass the
path separately (`git ls-tree <ref> -- <path>`), which the sync now does, and the delete
branch only runs when the lookup itself worked. `git show ref:path` typed in the Bash tool
has the same trap for dot-files.

## Agent browser profile (the browser-autonomy layer)

The universal fallback when no CLI/API/MCP covers a chore: Claude drives a real,
already-signed-in Chrome. Decided 2026-08-01 after research; this is the current
state-of-the-art shape, and its honest limits are part of the design.

- **Dedicated Chrome profile, "Claude Agent".** Created and signed in 2026-08-01. The human
  signs it into the dashboards agent work needs and saves those passwords in Chrome for
  one-tap re-login. NEVER signed in: banking, payment-stored accounts. Keep extensions in
  that profile minimal (extensions were the ClaudeBleed prompt-injection vector).
- **Identity convention (what to expect when a login screen appears).** Prefer **Sign in with
  Google as the owner's Google account**; if Google is not offered, use **GitHub SSO on the same
  account**; only then an id/password from Chrome's saved passwords. SSO sessions outlive
  password sessions and there is no credential to type, which is why it is the default here.
  One Google login covers Play Console, Google Cloud, AI Studio, and YouTube Studio; one
  Apple login covers App Store Connect and Apple Developer.
- **Signed in as of 2026-08-01:** Play Console, Google Cloud, AI Studio, YouTube Studio,
  App Store Connect, Apple Developer, GitHub, Vercel, Supabase, RevenueCat, Razorpay, Sentry,
  PostHog, Resend, Apify, Buffer, Capawesome.
- **Division of labor.** Deterministic work stays on CLIs/APIs (fastlane, vercel, supabase,
  eas: they do not drift and need no session). The browser agent covers the long tail:
  Console-only forms, data-safety questionnaires, one-off dashboard toggles, store screens
  with no API.
- **Drivers.** Claude in Chrome (claude-in-chrome MCP) against the Agent profile window is
  the primary driver; `agent-browser` / `playwright-cli` for scripted, repeatable flows.
- **The owner's request is the yes (The owner's decision, 2026-11-10; replaces "agent prepares, human
  clicks").** When the owner has asked for an outcome, Claude makes every click that produces it:
  Send, Save, Submit, Agree, Delete, Publish-as-draft. No second question, no "your click".
  Before 2026-11-10 sessions handed the owner clicks Claude was allowed to make: Save on a directory
  listing the owner had asked to fix, Send on emails the owner had asked for. Claude still stops in three
  cases, and only these:
  1. **The click goes beyond what the owner asked:** another recipient, a price, a promise, an
     amount, more deletions than the owner expected, or a step the owner never mentioned. Ask once, in chat.
  2. **The owner's own buttons:** merge, the final store submit, spending money, bank or financial
     applications. Unchanged.
  3. **Anthropic's hard limits, which no setting or script changes:** typing or submitting a
     password (Chrome's saved passwords included), ID, passport and card numbers, creating an
     account, CAPTCHAs, moving money. These are the product's rules, not this harness's
     (support.claude.com "Manage Claude in Chrome permissions").
  A message Claude wrote itself from facts on a page or in an email is shown to the owner once in chat
  and sent on the owner's yes, with no browser trip for the owner. Logins: "Sign in with Google" (or GitHub
  SSO) is Claude's whenever the account is already in this profile; a password login is the owner's one
  tap, roughly monthly per service, so tick "Remember me" whenever the owner signs in. 2FA codes are
  the owner's. Practitioner data: supervised agents complete ~80% of multi-step dashboard work and
  unattended reliability drops hard, so read the result back after every submit rather than
  assuming it landed. 1Password for Claude (July 2026) fills logins without Claude seeing them,
  but only on Mac with the Claude desktop app; not on this Windows machine.

## Native autonomy features and their limits

Use the built-in Claude Code capabilities, and respect where they stop:
- Checkpoints and rewind: every edit is auto-snapshotted; press Esc twice to roll back
  code or conversation. This is the safety net, so take bold autonomous edits and rewind
  if one goes wrong.
- fallbackModel (set in settings.json): if the primary model is overloaded or unavailable,
  work continues on the next model in the chain for that turn. Keeps unattended runs alive;
  capability drops on fallback, so prefer the primary for hard work. A project-level
  fallbackModel overrides this global chain rather than merging, so do not let a project
  setting silently disable it. Chain is capped at 3 after dedup.
- Model split (planner/executor): `opusplan` runs Opus in plan mode then Sonnet for execution
  (one word, no setup). Alternatively run a cheaper main model plus a STRONGER advisor
  (`/advisor fable`, or `advisorModel` in settings) so the advisor weighs in only at hard
  decision points: the officially-benchmarked win, cheaper AND slightly more accurate than the
  cheap main model alone. The advisor must be at least as capable as the main model, or it adds
  cost and nothing else.
  **Current setup (since 2026-10-30): the advisor is OFF and everything runs Opus 5.5 at 1M.**
  `model` is `claude-opus-5-5[1m]`, with effort xhigh from
  `modelSettings.claude-opus-5-5.effortLevel`, and both subagents (`design-reviewer`,
  `launch-auditor`) are pinned to the same `claude-opus-5-5[1m]`. There is no `advisorModel`
  key. The 1M-and-no-advisor shape was set on 2026-07-30, on Opus 5, and three findings drove it,
  all measured rather than inferred (the model names below are the ones measured then):
  1. **`[1m]` is a real variant and the one you want.** In the `/model` picker it is "Opus 5
     (1M context)", and both "Default (recommended)" and "Opus (1M context)" describe themselves
     as "Opus 5 with 1M context". Plain `claude-opus-5` renders as just "Opus 5" and runs a 200k
     window. Verified via `CLAUDE_CODE_AUTO_COMPACT_WINDOW`: 400000 under `[1m]` (the auto-compact
     threshold while 1M is live), unset under plain.
  2. **The advisor does not support 1M variants.** `/advisor` with `claude-opus-5[1m]` returns
     "the current main model does not support the advisor", so `advisorModel: fable` was silently
     dead. 1M context is worth more here than the advisor.
  3. **Fable 5 is listed "(temporarily unavailable)"** as an advisor option anyway.
  Never write a bare alias (`opus`, `sonnet`) in `model:` anywhere: `opus[1m]` resolved to
  **Opus 4.8**, and `launch-auditor` sat on `model: opus` for exactly that reason. Always the
  explicit id.
- Model lanes at a glance. Each is a launcher in `~/.claude/bin/` (on PATH, bash + cmd twins).
  All of them keep CLAUDE.md, every skill, all 14 wired hooks, the guards, MCP and the statusline
  intact, because those run in the local CLI process and never touch the model endpoint.
  `-c` continues the same conversation in any lane, so switching is: exit, relaunch with `-c`.

  | Command | Model | Billing | Use for |
  | --- | --- | --- | --- |
  | `claude` | Opus 5.5 at 1M, effort xhigh (modelSettings) | Max plan | everything, 99% of the time |
  | `claude-chrome` | Opus 5.5 at 1M, effort xhigh (modelSettings) | Max plan | same, with the browser bridge on |

  **The OpenRouter lane (`claude-or`) was DROPPED on 2026-08-05, deliberately. Do not rebuild it
  without re-reading this paragraph and hq log Session 21.** It worked for plain completions but
  failed in live use three ways at once: (1) `ENABLE_TOOL_SEARCH=auto:5` in settings env forces
  deferred custom tools, which only Anthropic models support, so the first real tool call 400'd
  ("Deferred custom tools are only supported on Anthropic models"); settings-file env BEATS both
  shell env and launcher exports (proven empirically 2026-08-03), so a launcher cannot opt out.
  (2) On that 400, the global `fallbackModel` chain silently escalated the session to Opus 4.8
  THROUGH OpenRouter, per-token with no prompt caching: the user asked for the cheapest model and
  got the most expensive path. (3) Running `/model` inside the routed session wrote a bare `opus`
  alias into the GLOBAL settings.json, silently downgrading every future main-lane session to
  Opus 4.8 at 200k. Total damage was only $0.28, but all three failure modes are structural.
  The Kimi lane was retired on 2026-10-10 without ever being activated (tombstone below).

  **Effort defaults (2026-08-07, corrected; per model since 2026-10-10):** the persistent default is
  `effortLevel: "xhigh"` in settings.json for Opus 5, Fable 5.1 and older, plus
  `modelSettings.claude-opus-5-5.effortLevel: "xhigh"` for Opus 5.5, which ignores the top-level key
  and would otherwise start at medium (it did, unnoticed, from 2026-09-22 to 10-10). NOTHING sets a
  persistent max. That is deliberate. `CLAUDE_CODE_EFFORT_LEVEL`
  was tried and REMOVED: any value other than xhigh disables ultracode entirely (binary message:
  "clear it and ultracode takes over"), and Anthropic documents max as "prone to overthinking" with
  "significant cost for relatively small quality gains" on ordinary work, so pinning it made routine
  coding worse, not better. Never re-add that env var. `effortLevel: "max"` in settings is silently
  DISCARDED (the schema enum ends at xhigh), so max and ultracode are session-only by design:
  `/effort max` or `claude --effort max` for a genuinely hard task, `/effort ultracode` or
  `claude --effort ultracode` for a wide one, `ultrathink` in a prompt for a single hard turn.
  Note ultracode itself runs at xhigh, so the saved default already matches its ceiling.

- Overflow lane (Kimi): RETIRED 2026-10-10, never activated. The key never arrived and the owner decided to
  stay on Claude and stop adding providers (Astra, Kimi, Grok Bot and DeepSeek Harness were dropped
  the same day). Launchers `bin/claude-kimi*` removed, the key slot removed from `.env.local` and the
  secrets map, the health warning removed. The lane's mechanics and its day-one checklist stay in git
  history (PRs #45, #53) and HQ log Sessions 19 to 21; the OpenRouter paragraph above is why no
  provider lane gets rebuilt casually.
- There is no `fableplan` alias. The "Fable orchestrator, 96% at 46% cost" headline is Claude Managed
  Agents (an API/cloud product), NOT this CLI, so it is not a setting to reproduce here.
- Looping: `/goal <condition>` keeps working turn after turn until a checker model confirms the
  condition holds (best with a verifiable end state, e.g. "tests pass and lint clean, or stop after
  N turns"); it wraps a Stop hook so it honors permissions and hooks. Pair with Auto Mode for
  hands-off runs. `/loop` polls a prompt on an interval (babysit a deploy or PR). Keep any loop that
  could touch main/prod in interactive or `claude -p` sessions, never Cloud Routines (they bypass
  the hooks).
- Newer inner-loop tools (verified present in the 2.1.220 binary), all context-cheap:
  `/subtask <task>` spawns a subagent that INHERITS the whole conversation, so it already has the
  background you would otherwise re-paste (this replaced the in-session `/fork`; `/fork` now makes
  a full background session copy). `/btw <question>` answers a quick side question without polluting
  the main thread. `/code-review` runs the bundled reviewer as an isolated background subagent and
  returns findings. **As of v2.1.215 it no longer auto-runs; it must be invoked explicitly**, so
  keep calling it by name (this repo always did, so nothing breaks, but do not assume it fires on
  its own). `/doctor` (v2.1.206+) rightsizes CLAUDE.md and prices the skill listing; run it after
  any big skills/CLAUDE.md change, since Anthropic put its current best-practice guidance inside it.
- Tool Search + standing MCPs: `ENABLE_TOOL_SEARCH=auto:5` defers each MCP's tool schemas until a
  tool is actually called, so extra MCPs no longer bloat context and the old "keep 5 to 7" ceiling
  is relaxed (still prefer a CLI over an MCP for routine work). Three standing user-scope MCPs are
  installed: Context7 (live version-correct library docs, `claude mcp add --scope user --transport
  http context7 https://mcp.context7.com/mcp`), Chrome DevTools (perf/network/console debugging,
  `claude mcp add chrome-devtools --scope user -- npx chrome-devtools-mcp@latest --isolated`), and
  Expo (EAS builds/docs/TestFlight, `claude mcp add --scope user --transport http expo
  https://mcp.expo.dev/mcp` then `/mcp` to OAuth-login). The separate
  `expo@claude-plugins-official` plugin (21 skills) is installed but DISABLED in
  settings.json so it does not spend listing budget on non-mobile sessions. Run
  `claude plugin enable expo` while actively shipping a native app, and disable it after.
  The Expo MCP above is independent of that plugin and stays on. Keep playwright-cli for browser automation; do NOT add Playwright
  MCP (the CLI is ~4x cheaper given shell access, and Chrome DevTools MCP fills the real gap:
  debugging, not duplicate automation).
- /security-review: run it before any public launch alongside the launch-auditor subagent;
  it catches vulnerability classes (exposed secrets, IDOR, missing auth) that taste alone misses.
- Cloud Routines and `claude --bare` BYPASS the guardrails. Cloud Routines run as fully
  autonomous sessions with NO permission prompts and do NOT honor the local hooks or deny
  rules; `--bare` skips hooks, plugin sync, auto-memory and CLAUDE.md auto-discovery (skills still resolve via /skill-name; verified against `claude --help`). NEVER run anything
  that touches main, prod, or store publishing through a cloud Routine or `--bare`. The PreToolUse
  hooks (five command guards: main-push, pr-merge, prod-deploy, stacked-pr-base, guard-tamper;
  plus the fail-open secret-leak scanner and the MCP guard) and the Stop-event branch guard
  protect interactive and `claude -p` runs only. (The ask-tier guard-file-edit prompt was
  deleted on 2026-08-08: `ask` never reached the owner.)
- **The backup lock (2026-11-10), inside guard-tamper.** The private backup,
  FabGemYT/FabClaudeWorkflow, can never be made public or internal, given a collaborator or a
  deploy key, transferred, or pushed to any other repo (a clone of it is recognised by origin
  or by its hq/ and secrets map, so repointing origin does not get past it). The public
  friends' copy, FabGemYT/FabFriendsClaudeSetup, is the opposite: the owner flips it public or
  private at will, and only the share-to-friends workflow writes to it. The owner's yes in chat plus
  the approval token still lets Claude do a blocked step. Pinned by
  `hooks/tests/test-backup-lock.py` (47 cases), which /health runs.
- Store and mobile autonomy: with persisted logins (vercel, supabase, capawesome) plus the two
  account-level store-API keys, the agent can build, sign, deploy previews, fill App Store and
  Play listings, and submit to test tracks for every app. The human-only gates are exactly: the
  final merge to production, the final store submit/release, and a few first-time Console forms
  (Apple's privacy nutrition label, Google's content-rating and app-content declarations) plus
  the legal answers to them. Default to STAGING store-listing changes for review; never auto-submit.
- security-guidance plugin: DISABLED in settings.json since 2026-08-07 (its UserPromptSubmit
  hook makes an LLM HTTP call on every prompt and timed out; README "Plugins"). When on, it is
  a fresh-context security reviewer on every edit, turn and commit. Use /security-review
  before a launch instead.

## Guard incident record (why each gate is shaped the way it is)

Moved out of CLAUDE.md on 2026-08-12. CLAUDE.md is read before every single message, so it
carries the DECISIONS; this section carries the evidence behind them. Read it before changing
any guard, and before adding a new one. Every entry below is also pinned by a test suite that
fails if the behaviour regresses, which is a stronger memory than prose.

**The measured baseline.** Across 283 transcripts and 19 projects the whole guard layer has
blocked **24 things, ever**. Four touched a real product. Every guard except the SQL one has
fired at most once, correctly. That is the target: a gate you never notice because it only
stands where there is genuinely no undo. Before adding a gate, grep the transcripts for how
often it would have fired, and on what. A guard that has never caught anything real is pure cost.

**Store submission was never the owner's decision (2026-08-07).** HQ Session 5 (2026-06-19) already
recorded "the real goal: automate the boring store-listing work and builds". The blocks on
`eas submit` and friends dated from the 2026-05-30 initial backup, BEFORE that clarification,
so they were legacy conservatism carried forward rather than anything the owner asked for.

**Money gates moved out of the deny list (2026-08-07).** `buy_*`, `create_project` and
`confirm_billing_purchase` were `deny` rules. A deny rule cannot be satisfied by the owner saying
yes, so the owner's approval dead-ended in homework. They are hook-gated now: blocked, but the message
tells Claude how to proceed once the owner agrees.

**The destructive-SQL gate, and why it now warns instead of blocking (2026-08-07 to 08-08).**
It shipped with a green 33/33 suite and was measured wrong within a day. Of the 24 guard blocks
in all of history, four touched a real product and THREE were this gate, all false positives:
`drop policy`, `drop policy`, `drop function`, on a live web game. It never caught anything real.
It blocked the standard idempotent RLS idiom (Postgres has no `CREATE POLICY IF NOT EXISTS`, so
`drop policy if exists` + `create policy` is the only re-runnable form), it blocked a script that
merely REWROTE a migration file, and a session stripped a real migration's idempotency guards to
get past it, then wrote the gate's own error text into the codebase as a design rationale. Its
message was false too: it claimed "IRREVERSIBLE, Supabase has no down-migrations" while all five
projects run **Supabase Pro with WAL-G daily backups**, verified against the Management API.
Pinned by `test-destructive-sql.py`, which asserts it never blocks.

**Coverage is a separate question from logic, and the logic suite cannot see a coverage gap.**
The same morning that gate shipped 33/33 green, it was still blind to
`mcp__claude_ai_Supabase__execute_sql` carrying a `DROP TABLE`: every blocking hook was
registered against `matcher: "Bash"` alone while the Supabase MCP sat in `allow`, so the
unguarded route was also the frictionless one. Matchers take regex over tool names (`mcp__.*`).
When adding any guard, ask which ROUTES reach the same outcome, then prove it by replaying a
payload through the hook rather than reasoning about it. Pinned by `test-mcp-guard.py`.

**Reading is not deploying (2026-08-12).** The prod-deploy check tested for `--prod` anywhere in
a vercel command, so five READ-ONLY commands were blocked with "Production deploys are blocked":
`ls`, `list`, `inspect`, `logs`, `deployments list`. A session set an env var on production, hit
that block, concluded production was off-limits entirely, never found `vercel redeploy` (free
since 2026-08-07), and handed the owner a manual dashboard click. The owner's response: "why is claude not
handling all this itself man!!". The guard now judges the SUBCOMMAND, not the flag. The same pass
found `vercel buy` completely ungated on the CLI route while the deny list covered only the MCP
`buy_*` tools. Pinned by `test-vercel-surface.py`, 46 cases.

**The pattern in all of the above:** every one of these was a guard matching a SUBSTRING instead
of understanding the OPERATION, and every one was found by measurement rather than reasoning.

**2026-08-16 -- the credential loader wedged a live session, and the backup would not have restored.**
Two failures, one shape: silent, and only visible at the moment it was too late.

`load-env.sh` appended to `$CLAUDE_ENV_FILE` with `>>`, never truncating, one `printf` PER LINE.
SessionStart fires repeatedly in ONE session (startup, resume, clear AND every compaction), so 16
exports x 7 firings = exactly 112 lines, and one 16-write burst racing five concurrent sessions tore
a line in half. Claude Code inlines that file into EVERY `bash -c`, so `echo ok` failed identically
to `git status`: `bash: -c: line 112: unexpected EOF`. A restart did not help (the file is on disk);
the line number never moved (the file was static); `.env.local` looked innocent (it was). Rewritten
idempotent + atomic + self-healing, 23 cases in `test-load-env.py`. **The general rule: a file you
append to on every session start is a file you will eventually corrupt. Write it whole, or not at all.**
The first attempt at the fix handled only MARKED blocks and would have left the real session just as
dead, because the wedged file was written by the pre-fix hook and had no markers; caught by testing
the actual recovery path rather than assuming it worked.

`skills/store-screenshots` was committed as a GITLINK (mode 160000) because it carried a nested
`.git`. GitHub renders that as an ordinary folder and the push succeeds; a clone gets it EMPTY.
Measured: 20 files on disk, 1 index entry, **0 files after a real clone**. Vendored instead of
submoduled -- the upstream is private, so a submodule would need auth plus `--recursive`, and a plain
`git clone` of the backup has to work. `/health` check 13 now catches the class: gitlink = FAIL,
nested `.git` = WARN, untracked-and-unignored = WARN, unpushed commits = WARN. Verified against a
purpose-built repo containing a real gitlink, with a control clone that restored 0 files.

**What both add to the pattern above:** substring-vs-operation was about guards being WRONG. These
two were about a guard NOT EXISTING for a failure that reports success. When a mechanism's failure
mode is "looks fine until the day you need it", the test is not "did it run" but **"reproduce the
recovery"** -- clone the repo and count the files; wedge a file and heal it.

**2026-08-16 -- `block-guard-tamper.sh` blocked a COMMIT MESSAGE, caught live.** While committing
the write-up of the delete-rule finding above, the guard refused the commit: the message quoted
three delete commands as evidence, and the guard read a target out of that quoted text.

**The first diagnosis was WRONG, and the correction is the useful part.** Bisection initially
pointed at the `cd "$HOME/.claude"` that opened the command: relative targets resolve against the
protected root, and an unresolvable glob is treated conservatively, so `worlds/*.json` looked like
the trigger. That theory survived only because every test built to check it happened to include an
interpreter call.

It bit a SECOND time hours later, blocking the PR body for the same work, and that repeat is what
exposed the real cause. `strip_heredocs` correctly lifts heredoc bodies out of the command text,
but the dispatcher then decided "is this body code?" by asking whether **ANY segment anywhere in
the whole command** resolved to an interpreter. Both blocked commands began with
`sh skills/health/scripts/health.sh`. That one unrelated `sh` flipped the switch, and the prose of
a completely different command -- `git commit -F -` the first time, `gh pr create --body-file -`
the second -- was parsed as a command list. Bisected to the exact line: `echo hi` before the
heredoc is fine, `sh x.sh` before it is not.

**Fixed 2026-08-16.** `strip_heredocs` now returns each body paired with the line that DECLARED
it, and the interpreter check runs against that line alone. `cat <<EOF | bash` still executes,
because the pipe is on the declaring line. Ten cases in `test-delete-guard.py` pin both halves:
five prose-quoting-a-command cases that must be ALLOWED (including after an `sh` call), and five
genuinely-executing heredocs that must still BLOCK (`bash <<EOF`, `bash -s`, `cat <<EOF | bash`,
`sh <<EOF`, and an interpreter after a `cd`).

One limitation was checked and is unchanged, not newly introduced: `python3 - <<EOF` whose body
calls `os.system("rm -rf ...")` still passes. Verified by running the same payload against
main's analyser and the new one side by side -- both allow it. That is the documented
"names no shell binary" class the canary layer exists for, not a regression from this change.

Both blocks were worked around honestly at the time by putting the text in a file
(`git commit -F <file>`, `--body-file <file>`), which subverts nothing: the guard exists to stop
shell writes to guard files, and no such write was ever proposed. Not routed around, not
token-approved.

**Why this one is worth keeping in the record:** it is the read-intent-from-inert-text defect
firing on the very commit, and then the very PR, that documents that defect. A guard that judges
text it will never execute will eventually block the description of itself. And a diagnosis that
only ever gets tested against commands built to confirm it will look right twice before it fails.

**2026-10-08 to 10-10 -- Supabase's own confirmation form, and four things found while fixing it.**
The owner had to press Accept on every destructive-looking statement a live web game's session sent
through the claude.ai Supabase connector. The dialog read "MCP server claude.ai Supabase
requests your input", which is neither Claude Code's permission system nor auto mode: it is
an MCP form elicitation from Supabase's hosted server, which asks before execute_sql and
apply_migration when the SQL looks destructive, and can only ask once the client advertises
form support. Claude Code started advertising it with protocol revision 2026-07-28 (2.1.292
to 2.1.295), so a session that was "perfect two days ago" changed without any edit here.
Supabase documents a `skip_elicitations` URL parameter, but only for a server you configure
yourself, not for the claude.ai connector. Claude Code documents an `Elicitation` hook that
answers a form from a script. That hook now exists (`hooks/answer-supabase-sql-confirm.sh`,
decision in `hooks/elicitation-answer.py`): it accepts only the SQL confirmation from a server
whose name contains Supabase, in form mode, with no non-boolean fields, and never a form that
mentions money, so create_project and create_branch cost confirmations still reach the dialog.
It fails towards the dialog on any doubt. 15 replay cases in `tests/test-elicitation-answer.py`,
wired into `/health`. The destructive-SQL note in chat still comes from `block-mcp-danger.sh`
on the same call, which is the behaviour settled on 2026-08-07/08.

Found on the way: (1) **Opus 5.5 had been running at medium effort for three weeks.** Since
2.1.280 the top-level `effortLevel` in user settings does not apply to Opus 5.5 or newer; the
level lives under `modelSettings.<canonical model>` (the canonical name also covers the `[1m]`
variant). `/health` reported xhigh as fine the whole time; it now checks the per-model entry.
(2) **`MSYS_NO_PATHCONV=1` makes every Python-backed hook fail closed.** With conversion off,
`py -3 /c/Users/...` is read as `C:\c\Users\...`, the secret scanner cannot find its own script
and blocks every Bash command. Headless runs of `/doctor prompt-audit` and `/skill-doctor`
need that variable under Git Bash, so their complaints about a broken scanner are an artifact of
the run, not a real break. Never export it into a session. (3) **`block-guard-tamper.sh` fired
on a `cp` that READ a hook file** (the hook path was the source, not the destination): the
substring-not-operation defect once more. Candidate fix, not made yet: judge the destination.
(4) **The auto mode classifier's `[Self-Modification]` rule denied Edit-tool changes to
`settings.json`** (hook wiring, effort, environment entries) and once to a skill doc, in the very
session implementing the owner's approved plan. The documented way through is the owner's own
message naming the exact change; the `.approved-action` token is for our hooks and does not
reach the classifier.

**2026-10-16 -- `block-prod-deploy.sh` blocked a read-only deployments LIST.** After a second online store
Peptides' PRs merged, a session checked what was live with
`curl -s -H "Authorization: Bearer $VERCEL_TOKEN" "https://api.vercel.com/v6/deployments?projectId=...&target=production&limit=3"`.
The REST branch blocked any call naming `/deployments` and `target=production`, so a GET filtered
to production read as "creating a production deployment": the substring-not-operation defect
again. The session checked the live site instead. Fix (The owner's yes, 16 Oct): the check now
asks `http_writes()` first. A curl or wget call counts as a read only when it is plainly GET or
HEAD (no body flag, or `-G`, or `-X GET`); anything else, httpie included, is judged as before.
Pinned by 8 new block cases (a body alone, `-sSX POST`, `-XPOST`, `--json`, `-sd`, `?target=`
with POST, wget `--post-data`, httpie POST) and 5 new allow cases in `test-command-guards.py`,
plus the exact command in `test-routine-work.py`.

## Auto mode, and what actually causes friction (measured 2026-08-16)

**The headline: auto mode is not the problem, and an earlier draft of this section said it was.
That draft reasoned from the rule list instead of measuring the transcripts. This is the
correction, and it is the exact mistake Law 5 exists to prevent.**

**What was measured.** All 2,717 transcripts on this machine, 2.8 GB, every project.

| | count | what it really was |
| --- | --- | --- |
| auto-mode POLICY refusals | **0** | none, ever |
| "auto mode cannot determine safety" | 96 | transient classifier-model outages, not refusals |
| real harness denials | ~195 | **~190 were `rm -rf`, all routine cleanup** |
| `git push` denials | 6 | the merge gate working correctly |

Sessions run overwhelmingly in auto mode (2,657 turns vs 264 in bypassPermissions in the largest
transcript alone), across Supabase migrations, Vercel env work, DNS records and store uploads,
for months, with **zero** policy blocks. `settings.json` has carried `defaultMode: "auto"` since
the first commit on 2026-05-30 and it has been fine.

**So where did "I have to tap allow soo many times" come from? Our own deny rules.** Four blanket
rules -- `Bash(rm -rf:*)`, `Bash(rm -fr:*)`, `Bash(rm -Rf:*)`, `Bash(rm -R:*)` -- block every
recursive delete regardless of target. What they actually stopped, verbatim from the transcripts:

- `rm -rf .next` (clearing the Next.js build cache: the single most routine command in this stack)
- `rm -rf .review .playwright` (scratch directories Claude created itself minutes earlier)
- `rm -rf .gen/canon-cache worlds/*.json` (regenerating generated files)

None of those can hurt anything. **The rule matches the SUBSTRING `rm -rf`, not the OPERATION**,
which is the precise failure mode the Guard incident record above documents three other times.
It is the most-fired guard in the system by an order of magnitude, and it has never once caught
something dangerous.

**Why narrowing it is safe, not a loosening.** The catastrophic forms are already covered twice
over, by layers that understand the target rather than the text:

1. **Auto mode's own classifier** decides removals targeting the filesystem root or home
   directory (`rm -rf /`, `rm -rf ~`), including inside command or process substitution, and
   since v2.1.205 blocks a recursive forced delete whose target is an unresolved shell variable,
   plus wildcard/age-filter deletes in shared scratch directories.
2. **`block-guard-tamper.sh`** blocks any shell command that would delete or rewrite the guard
   files, the `~/.claude` root, or the home root.

So the blanket deny rules catch only the SAFE cases. The dangerous ones never reach them.

**The one gap worth keeping a rule for:** during a classifier outage (96 observed) auto mode
cannot judge anything, so layer 1 is briefly absent. A narrowed rule that still hard-blocks
`/`, `~`, `$HOME` and unresolved-variable targets covers that window without touching
`rm -rf .next`. That belongs in `command-guard.py`, which already tokenises commands properly
and already judges Vercel by subcommand rather than by flag.

**SHIPPED 2026-08-16.** The four blanket rules are gone from `settings.json` (30 deny rules ->
26) and `guard_catastrophic_delete` in `command-guard.py` replaces them. It blocks exactly two
things, and nothing else:

1. **The filesystem or drive root**, including `/*`, `C:/*` and the msys `/c/` spelling. GNU rm
   refuses a bare `rm -rf /` itself (`--preserve-root` is the default) but NOT the glob form,
   which is the spelling that actually destroys a machine.
2. **A target starting with an unresolved expansion followed by a slash.** Shell state does not
   survive between tool calls, so an unset `$VAR` collapses `rm -rf "$VAR/x"` into `rm -rf /x`.
   This is the Steam bug, and it is an accident rather than obfuscation, which puts it inside
   this guard's threat model.

Resolution order before judging a target: assignments written in the same command, then `$HOME`
and `$USERPROFILE`, then any variable that genuinely exists in the process environment. Measured
before shipping: across every transcript the ONLY variables ever used as `$VAR/` in a recursive
delete are `$HOME` and `$USERPROFILE`, both resolvable, so this newly blocks nothing that has
ever run here.

Proven live in both directions, not just in the suite: `rm -rf .next .review` now runs and
deletes (exit 0), and `rm -rf "$NOPE_NOT_SET/x"` is refused with a message naming the variable.

`test-delete-guard.py` pins it with 33 cases, deliberately split into MUST BLOCK and MUST
ALLOW, with the allow half drawn from commands found in the transcripts. It is wired into
`/health`, which FAILS if either half breaks.

**One test expectation genuinely changed, and it is worth reading before trusting the green.**
`test-guard-tamper.py` had `rm -rf $UNKNOWNVAR/.claude/hooks` in its ALLOW list, on the stated
grounds that unresolved expansions are skipped by design so `rm -f "$TMP/x"` keeps working.
That case now BLOCKS, so the suite went red on the first run. The expectation was moved rather
than flipped: the non-recursive form (`rm -f $UNKNOWNVAR/...`) stays in the ALLOW list and
still passes, so the original property is still pinned one line down. The recursive form is a
deliberate tightening backed by the measurement above. Suite is now 74 cases.

**What auto mode does still constrain, for the record.** From `claude auto-mode defaults` on
v2.1.233 (the binary's own list): 17 allow, 66 soft-deny, 1 hard-deny, 20 environment entries.
A soft-deny clears when the user named the specific action, which in practice the owner's requests do.
The single HARD rule is `Data Exfiltration`, never clearable. Pushing `~/.claude` to its own
configured private remote is not that: it is the repo's own remote as of session start, and
`.gitignore` is an allowlist excluding `.env*`, `secrets/` and transcripts. A mid-session
`git remote set-url` WOULD sever that and make the destination count as public.

Auto mode became the built-in default for new Pro/Max terminal sessions on 2026-08-14
(v2.1.228+ on macOS/Linux/WSL, v2.1.233+ on native Windows). For this setup that changed
nothing, because the setting was already `auto`.

**The lesson, which is the reusable part:** a rule list tells you what a system COULD block.
Only the transcripts tell you what it DID block. Measure the second before acting on the first.

**One claim re-verified, because it is load-bearing.** `ask` RULES still do NOT prompt on
v2.1.233: `claude plugin install <bogus>` matched `Bash(claude plugin install:*)` and ran
straight through to the CLI's own "not found" error. The official docs state that deny AND
explicit ask rules apply in every mode; on this build the ask half is still wrong. **Never build
a gate on an `ask` rule.** The 7 `ask` rules in `settings.json` are therefore decoration, not
protection: they cover `supabase secrets unset`, `supabase branches delete`, `claude mcp
add/remove` and the three `claude plugin` verbs, none of which any hook or deny rule covers.

## Google Search Console and the Indexing API

`py -3 ~/.claude/bin/gsc.py` works in every session, with nothing to log into. The credential is a
service-account key exported by `hooks/load-env.sh`, so there is no token to refresh and nothing
that quietly expires.

    gsc.py properties                     which properties are readable, and which are not yet shared
    gsc.py totals   <site> [days]         clicks / impressions / CTR / average position
    gsc.py top      <site> [days] [rows]  best queries
    gsc.py queries  <site> [days] [rows]  same, explicit
    gsc.py pages    <site> [days] [rows]  best pages
    gsc.py sitemaps <site>                submitted sitemaps, with error and warning counts
    gsc.py inspect  <site> <url>          index status, coverage, last crawl, canonical, robots

`<site>` takes a bare domain (`example.com`) and resolves it to whichever form the property is
actually registered as, so nobody has to remember `sc-domain:` versus `https://`. Data lags about
two days, which the tool already accounts for in its date range.

**WHEN A NEW SITE IS ADDED**, it needs one grant and nothing else. `gsc.py properties` compares
Vercel's live production domains against what the service account can actually read, so the new
domain reports ITSELF as missing, with the exact click path. `/health` runs the same check and
warns. That is deliberately not a hardcoded list: a static list stops being true the moment a
sixth site ships, and the new domain would then be invisible rather than flagged.

**WHY A SERVICE ACCOUNT AND NOT `gcloud auth application-default login`.** ADC refresh tokens
issued while an OAuth consent screen sits in "Testing" expire after exactly 7 days. The credential
then stops working with no warning, which is precisely the silent breakage the FOUNDATION forbids.
A service-account key does not expire. The one-time cost is that the service account must be added
as a user on each Search Console property; `gsc.py properties` reports which are still missing, so
that never has to be remembered.

Scope is `webmasters` (read plus sitemap write). The Indexing API is enabled on the same project
and covered by the same credential, for `urlNotifications` when a page needs recrawling.

