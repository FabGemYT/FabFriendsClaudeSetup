# Skill Sources & Reinstall Commands

All skills in `~/.claude/skills/` are **real directories** (not symlinks). This file lets you re-pull from source if anything corrupts. **78 skills on disk (counted 2026-11-10); all 78 are accounted for below.** (Was 30 until the 2026-09-14 Phase 0 commit vendored 46 more, then `harness-review` and the rest arrived; the 2026-07-30 HyperFrames update had retired `gsap` and `hyperframes-media` into their surviving siblings — see Removed.)

## Reinstall pattern

```bash
npx -y skills add <repo> [--skill <name>] -g -y
```

**Important caveat:** the `skills` CLI installs to `~/.agents/skills/<name>/` and tries to create a symlink at `~/.claude/skills/<name>/`. Since these are now real dirs, a re-install will likely fail or be a no-op on the `.claude/skills/` side. To genuinely reinstall: (1) `mv ~/.claude/skills/<name> ~/.claude/skills/<name>.bak`, (2) run `npx skills add ...`, (3) replace the freshly-created symlink with `cp -r ~/.agents/skills/<name> ~/.claude/skills/<name>` again to keep self-contained.

> ⚠️ **A reinstall reverts local edits.** Several third-party skills below carry local fixes (see "Local patches on third-party skills"). Re-read that section before reinstalling anything, or you will silently reintroduce a broken skill.

## Installed via the `skills` CLI (verified install commands)

| Skill | Install command |
|---|---|
| agent-browser | `npx -y skills add vercel-labs/agent-browser -g -y` |
| vercel-react-best-practices | `npx -y skills add vercel-labs/agent-skills --skill vercel-react-best-practices -g -y` |
| remotion-best-practices | `npx -y skills add remotion-dev/skills --skill remotion-best-practices -g -y` |
| playwright-cli | `npx -y skills add microsoft/playwright-cli --skill playwright-cli -g -y` |
| impeccable | `npx -y skills add pbakaus/impeccable -g -y` |

## The HyperFrames family (managed by its own CLI, not `skills add`)

These 8 install and update through `npx hyperframes`, which tracks freshness by content hash. Do **not** hand-install them with `skills add`.

| Skill | Role |
|---|---|
| hyperframes | the router; picks a workflow and owns the intent layer |
| hyperframes-core | shared contracts (brief format, project shape) |
| hyperframes-cli | init, lint, check, preview, render, publish, diagnostics |
| hyperframes-animation | animation domain rules (absorbed the retired standalone `gsap` skill) |
| hyperframes-keyframes | keyframe domain rules |
| hyperframes-creative | creative direction + audio extraction |
| hyperframes-registry | registry blocks and components |
| media-use | images, icons, logos, audio, captions, grades, LUTs, TTS, transcription, background removal (absorbed the retired `hyperframes-media`) |

```bash
npx hyperframes skills check --json     # freshness report, installs nothing
npx hyperframes skills update           # refresh core + anything already installed
npx hyperframes skills update <name>    # also install that named workflow/domain skill
npx hyperframes skills                  # install the FULL published set
```

**Lazy workflows are not missing files.** The router references ~11 workflow skills by slash name (`/general-video`, `/product-launch-video`, `/slideshow`, `/embedded-captions`, `/talking-head-recut`, `/music-to-video`, `/motion-graphics`, `/pr-to-video`, `/faceless-explainer`, `/remotion-to-hyperframes`, plus the `/figma` domain skill). They install on demand when routing selects them, and `references/workflow-catalog.md` carries the contract for the ten workflows so routing works before they exist. `skills check` correctly reports them as `missing`, not as failures.

### Upstream state as of 2026-07-30 (after the update)

On 2026-07-30 the family was brought fully current with `npx hyperframes@latest skills update`, and the diff was reviewed before committing. Result:

- `coreMissing: 0` — the core set is complete.
- **All 8 installed family skills are now `current`** (were: 2 current, 6 outdated). The 6 outdated skills — hyperframes, hyperframes-animation, hyperframes-cli, hyperframes-core, hyperframes-creative, media-use — were refreshed to latest upstream. Local patches were re-applied on top where the update reintroduced the old bugs (see the patch table below).
- **`gsap` was removed** by the updater (unpublished upstream; its animation role was absorbed into `hyperframes-animation`). Not orphaned-and-kept as previously planned — the CLI deleted it during update, which is the correct outcome.
- **`hyperframes-media` was removed** (retired upstream; the updated `media-use` explicitly states "hyperframes-media retired / gone" and now owns the full audio engine — TTS, transcription, captions, background removal). Our stale local copy was deleted to prevent the router picking up a dead duplicate.
- **Lazy workflows still install on demand** (`skills check` reports them `missing`, not broken — see the note above).
- Re-run `npx hyperframes@latest skills check --json` before the next update to see fresh drift.

## Pre-existing (best-guess sources — confirm via `npx skills add <repo> -l` before reinstalling)

| Skill | Best-guess install |
|---|---|
| ai-sdk | `vercel/ai`, folder `skills/use-ai-sdk` (frontmatter `name: ai-sdk`; traced 2026-11-10; Apache-2.0). The local description is rewritten to be directive. |
| deploy-to-vercel | `vercel-labs/agent-skills --skill deploy-to-vercel` (confirmed in the repo listing; the repo README licenses it MIT). Locally reworded: never deploys to production. |
| react-native-best-practices | `vercel-labs/agent-skills`, folder `skills/react-native-skills` (MIT per the repo README) |
| supabase | `npx -y skills add supabase/agent-skills -g -y` (MIT; the Supabase MCP server's own instructions name this repo) |
| supabase-postgres-best-practices | same repo as `supabase` (`supabase/agent-skills`, MIT) |

## Real local (hand-authored, not from `skills` CLI)

These have no upstream repo — they live only in `~/.claude/skills/<name>/`. This git repo IS their backup.

- blogs
- commit-push-pr
- frontend-design-official (originally from anthropic-skills plugin, then locally edited)
- homepage
- kickoff
- health (the /health silent-failure check; `scripts/health.sh` is the whole skill)
- plan-first (the feature-sized planning interview + plan-format checklist that CLAUDE.md Law 1 delegates to)
- skill-creator
- store-screenshots (App Store / Play Store screenshot generator. Has its own private upstream at `github.com/FabGemYT/store-screenshots`, but the files are **vendored** into this repo rather than referenced. That is deliberate: it was originally committed as a gitlink, which made it clone EMPTY — 20 files, silently zero restored. A private-repo submodule would also need auth plus `--recursive` at clone time, so a plain `git clone` of this repo must contain the real files. To resync from upstream: clone it elsewhere and copy the files in, do NOT leave a nested `.git` behind. `/health` check 13 fails if one reappears.)
- ui-ux-pro-max (originally from anthropic-skills plugin, then locally copied + directive description)
- unslop (hand-authored; the text twin of impeccable, a universal anti-AI-slop text editor; built from research plus Wikipedia "Signs of AI writing")
- web-design-guidelines (originally from anthropic-skills plugin, then locally copied + directive description)

## Local patches on third-party skills

Read this before reinstalling any of these. Each fix addresses a defect that made the skill fail at runtime, so a clean reinstall reintroduces the bug.

| Skill | Patch | Why |
|---|---|---|
| impeccable | Substituted 69 `{{...}}` template placeholders (15 in SKILL.md, 54 across the reference/ and scripts/ bundle) (`{{scripts_path}}`, `{{command_prefix}}`, `{{command_hint}}`, `{{model}}`) | The installer shipped them unsubstituted, so the skill emitted literally `node {{scripts_path}}/load-context.mjs`, which cannot run. Script paths now point at `~/.claude/skills/impeccable/scripts/` and were verified to resolve. |
| ui-ux-pro-max | Rewrote 14 `python3 skills/ui-ux-pro-max/scripts/search.py` invocations to absolute `~/.claude/skills/...` paths | The relative form only resolved when the working directory happened to be `~/.claude`. From any real project directory all 14 failed. Verified `search.py` now runs from an unrelated cwd. |
| ui-ux-pro-max | Replaced "on Windows use `python` instead of `python3`" with `py -3` | On this machine a bare `python` resolves into an unrelated tool's virtualenv (`hermes-agent/venv`, Python 3.11), not the system interpreter, so scripts could run without their dependencies. `py -3` is immune to that PATH shadowing — the same reason `hooks/_resolve-python.sh` prefers it. |
| blogs, homepage | Replaced "use Playwright MCP for visual verification" with the `agent-browser` / `playwright-cli` Bash CLIs | Playwright MCP is explicitly rejected in `TOOLS.md` and `rules/design.md` (the CLI is far cheaper given shell access). These two skills contradicted the standing decision. |
| media-use | Defined `<SKILL_DIR>` once at the top | The token is used across ~10 reference files and was never defined anywhere, so every command required a guess. **The 2026-07-30 upstream update reintroduced this — the patch was re-applied.** One definition line (= `~/.claude/skills/media-use`) fixes them all without touching the usages. |
| media-use | `audio/references/bgm.md` + `tts.md`: `../SKILL.md` → `../../SKILL.md`, and retargeted the setup pointer | From `audio/references/`, `../SKILL.md` points at `audio/SKILL.md`, which does not exist; the real file is two levels up. **The 2026-07-30 update reintroduced this too, and also renamed the target section**, so the pointer now reads `../../SKILL.md` plus `../../references/setup-providers.md` (where setup actually lives in the new structure). Re-verified both targets resolve. |

## Removed

| Skill | Date | Reason | Backup | Reinstall command |
|---|---|---|---|---|
| endgame | 2026-05-24 | Merged into the `launch-auditor` subagent (audit-only, isolated context). Unique content (severity definitions, the Beyond-It-Works gut-check trio, the tool-stack-underpowered question, performance nuances, the 12-item output structure) was folded into `~/.claude/agents/launch-auditor.md`. | **None. Gone.** The note here used to claim `~/.claude/skills/_archive/endgame-SKILL.md.bak`; that path does not exist on disk and never appeared in this repo's git history, so it was never a real recovery route. The merged content in `launch-auditor.md` is the only surviving copy. | none — hand-authored; rebuild from `launch-auditor.md` |
| find-skills | 2026-05-24 | Low value on a frozen skill roster; broad misroute risk ("how do I do X" auto-fires on innocent how-to questions, grabbing turns from the actual task skill). | n/a | `npx -y skills add vercel-labs/skills --skill find-skills -g -y` |
| gsap | 2026-07-30 | **Removed by `npx hyperframes skills update`** (unpublished upstream). Its animation role was absorbed into `hyperframes-animation`. | none — was already unpublished upstream | none; use `hyperframes` (routes animation to `hyperframes-animation`) |
| hyperframes-media | 2026-07-30 | **Retired upstream and merged into `media-use`.** The updated `media-use` states "hyperframes-media retired / gone" and now owns TTS, transcription, captions, and background removal. Deleted our stale local copy so the router cannot pick up a dead duplicate. | this git repo's history (`git show 3300de3:skills/hyperframes-media/SKILL.md`) | none; use `media-use` |

## Supply-chain vetting (audit before you install)

Third-party skills are now a real attack surface: a 2026 Snyk audit of ~4,000 marketplace
skills found 13.4% with a critical issue and 76 with confirmed malicious payloads (invisible
unicode instructing credential exfiltration; `!`command`` dynamic-context lines that run
`curl … | sh` at skill LOAD time, before the model ever reviews the text). This roster is
frozen and hand-curated, which is the main defence — but vet anything new before adding it.

**Audit run 2026-07-30 across all skills + agents + hooks + rules (701 files): CLEAN.**
Zero invisible-unicode characters. The only `!`command`` dynamic-context lines are
`commit-push-pr`'s own intentional git-status gathering (`git branch`, `git status`,
`git diff`, `gh pr list`) — reviewed and benign. `allowed-tools` grants are mostly narrow
(`Bash(git …)`, `Bash(agent-browser:*)`), and none is a blanket `Bash(*)`. The broadest is
`playwright-cli`'s `Bash(npx:*)`, which is effectively arbitrary-package execution; accepted
because the skill is first-party Microsoft and npx is already allow-listed in settings.json.

**Checklist before installing ANY new skill** (a 30-second grep pays for itself):
```bash
S=~/.claude/skills/<name>
grep -rERn '!`[^`]*(curl|wget|nc|bash|sh|Invoke-WebRequest)' "$S"   # load-time exec
grep -rEn 'allowed-tools:.*Bash\(\*\)' "$S"                          # blanket shell grant
grep -rEnP '[\x{200B}-\x{200F}\x{202A}-\x{202E}\x{2060}-\x{2064}\x{FEFF}]' "$S"  # invisible unicode
grep -rEn 'https?://' "$S/SKILL.md"                                  # unexpected external URLs
```
Any hit = read that file fully and understand WHY before trusting it. `hooks/tests/` fixtures
assemble credential *shapes* on purpose and are exempt from the invisible-unicode concern.

**`disableSkillShellExecution` is deliberately NOT set.** That managed-settings flag (verified
present in the 2.1.220 binary) globally disables the `!`command`` preprocessing — which would
break `commit-push-pr`, which uses it legitimately to gather git context. The frozen roster +
this checklist is the right control here, not a global kill-switch that also disables a skill we
depend on. Revisit only if an untrusted skill with dynamic context is ever added.

## How to verify any skill's repo

```bash
# List skills in a repo
npx -y skills add <repo> -l

# Search the catalog
npx -y skills find <query>
```

## SEO family, added 2026-08-22 (approved by the owner)

Installed for the a live web game search work. They began as symlinks into
`~/.agents/skills/`; since the 2026-09-14 Phase 0 commit they are **vendored as
real directories** like everything else (checked 2026-11-10: every tracked file
is a regular file, and `~/.agents/skills/` no longer exists). A `skills` CLI
reinstall would still overwrite them, so read "Local patches" first.

| Source | Skills | Install command |
|---|---|---|
| addyosmani/web-quality-skills | accessibility, best-practices, core-web-vitals, performance, web-quality-audit | `npx -y skills add addyosmani/web-quality-skills -g -y` |
| coreyhaines31/marketingskills | ai-seo, aso, programmatic-seo, schema, site-architecture | `npx -y skills add coreyhaines31/marketingskills --skill <name> -g -y` |
| sanity-io/agent-toolkit | seo-aeo-best-practices | `npx -y skills add sanity-io/agent-toolkit --skill seo-aeo-best-practices -g -y` |
| AgriciDaniel/claude-seo | seo, seo-audit, seo-backlinks, seo-cluster, seo-competitor-pages, seo-content, seo-content-brief, seo-dataforseo, seo-drift, seo-ecommerce, seo-flow, seo-geo, seo-google, seo-hreflang, seo-image-gen, seo-images, seo-local, seo-maps, seo-page, seo-plan, seo-programmatic, seo-schema, seo-sitemap, seo-sxo, seo-technical | `npx -y skills add AgriciDaniel/claude-seo -g -y` |

> **TWO NAME COLLISIONS, resolved by install order.** `seo` and `seo-audit` exist
> in more than one of these repos. claude-seo installed last and **overwrote**
> addyosmani's `seo` and coreyhaines31's `seo-audit` on disk. The surviving
> versions are the more capable ones (full-site crawl, subagent delegation), so
> this was left as-is rather than renamed — but it is a real loss, and
> re-pulling addyosmani's repo would silently flip `seo` back the other way.
> **Install order matters here. It is not idempotent.**

Three of these need paid accounts to do anything and are inert without them:
`seo-dataforseo` (DataForSEO), `seo-image-gen` (nanobanana/Gemini),
`seo-maps` beyond its free tier. Everything else runs on nothing.

## Traced 2026-11-10: the 11 skills that had no recorded source

All arrived with the 2026-09-14 Phase 0 commit except `harness-review`. The `mk-`
prefix is local, added so the marketing skills could not collide with the SEO
family's names; inside, each keeps its upstream `name:`.

| Folder | Upstream `name:` | Source | Licence |
|---|---|---|---|
| claude-ads | ads | `AgriciDaniel/claude-ads` | MIT |
| mk-ad-creative | ad-creative | `coreyhaines31/marketingskills` | MIT |
| mk-ads | ads | `coreyhaines31/marketingskills` | MIT |
| mk-copywriting | copywriting | `coreyhaines31/marketingskills` | MIT |
| mk-cro | cro | `coreyhaines31/marketingskills` | MIT |
| mk-lead-magnets | lead-magnets | `coreyhaines31/marketingskills` | MIT |
| mk-marketing-psychology | marketing-psychology | `coreyhaines31/marketingskills` | MIT |
| mk-offers | offers | `coreyhaines31/marketingskills` | MIT |
| lp-conversion-audit | landing-page-conversion-audit | `autonnel/autonnel-skills` (also mirrored in `github/awesome-copilot`) | Apache-2.0 |
| server-side-tracking | server-side-conversion-tracking | `autonnel/autonnel-skills` (same) | Apache-2.0 |
| harness-review | harness-review | hand-authored 2026-10-10; this repo is its backup | The owner's |

`hyperframes-media`, listed under Removed, came back on 2026-10-10 (commit fe1677b) as a single
`SKILL.md` from `heygen-com/hyperframes` (Apache-2.0); it is one of the 78.

## Licences, for the public friends' copy (checked 2026-11-10)

`bin/export-shareable.py` builds FabGemYT/FabFriendsClaudeSetup from this folder,
and a public copy is redistribution, so each skill's licence decides how it travels:

- **Copied as the owner's patched version, with credit** (MIT or Apache-2.0, or the owner's own):
  everything except the line below. Apache-2.0 skills the owner patched (impeccable,
  media-use) carry a "modified" note in the friends' CREDITS file, as the licence asks.
- **Downloaded from its source by the friends' installer instead:**
  `remotion-best-practices` (`remotion-dev/skills` publishes no licence, so it is
  not ours to redistribute).

Re-check this list whenever a skill is added: the export refuses a skill folder that
is in neither list.
