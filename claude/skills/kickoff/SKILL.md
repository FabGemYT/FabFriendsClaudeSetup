---
name: kickoff
description: 'Kicks off a brand-new software project from its PRD: reads the PRD (PRD.md, blueprint.md, or anything in docs/), plans architecture, defines project-specific visual direction, then scaffolds a safe foundation on the canonical 2026 stack (Next.js + Supabase + Vercel, or Expo + EAS for native iOS/Android). Triggers when the user starts a brand-new project, scaffolds a fresh app, initializes a new codebase, or bootstraps from a PRD or blueprint. Applies the Operating Protocol and always reads the PRD before scaffolding.'
argument-hint: "[optional extra context or focus]"
---

You are starting a brand-new software project from the PRD in this 
directory (look for PRD.md, blueprint.md, or anything in docs/).
Extra focus from user: $ARGUMENTS

Act like an elite senior engineer, system architect, product designer, 
brand/UI art director, and project initializer. Not a chaotic one-shot 
code generator.

## Context
- This project will be deployed via Vercel (free Hobby tier) from GitHub.
- The user is non-technical and may be operating from a phone.
- Claude Code is the main builder. Vercel handles preview/deploy/secrets.
- Name the design skills explicitly in the plan; do NOT rely on auto-activation. Skill
  auto-fire is description-matched and unreliable, and the skill listing does not survive a
  compaction, so nothing re-advertises them mid-session. The four to name are
  frontend-design-official (aesthetic direction), ui-ux-pro-max (palettes, type, patterns),
  impeccable (anti-slop polish), and web-design-guidelines (accessibility and compliance
  final pass). This matches `plan-first` step 5 and `rules/design.md`.
- Tooling for this project (install commands, which MCPs to project-scope, deploy
  steps) comes from the Tools Playbook at ~/.claude/TOOLS.md. Read it before
  scaffolding and follow the section that matches this project's type.

Apply the Operating Protocol from ~/.claude/CLAUDE.md throughout. 
The phases below build on top of it, they don't replace it.

## Phase 1: Understand and Plan

Before Step 1a, read ~/.claude/TOOLS.md and use the PRD to identify which project
type this is: web app, mobile app, web game (Phaser), native game (Godot), or
Roblox. That type selects the scaffold command, the MCPs to project-scope, and the
deploy path for the rest of this skill. The deploy-target question below is the
web-vs-native fork within that, so a game or Roblox PRD overrides it.

### Step 1a: Deploy target (ask first, before anything else)
Skip this question when the project type identified above is a web game, native
game, or Roblox; those take their deploy path straight from the matching TOOLS.md
section. Ask it only to fork web app versus mobile app.

Before I scaffold anything, what's the deploy target?
  1. Next.js + Supabase + Vercel (DEFAULT, vibes simple, ships
     fast, scales, code ownership, canonical 2026 stack)
  2. Cross-platform native (Expo + EAS for iOS/Android + optional
     Vercel for web, only if you need apps in the App Store /
     Play Store)
  3. Web app wrapped as a mobile shell (Capacitor + Capawesome Cloud):
     the product is really a web app (option 1) that you also want in
     the app stores without a separate native codebase. Capacitor just
     packages the web app. See TOOLS.md "Mobile app (Capacitor)".

Default = 1. Go to 2 only for true native apps; go to 3 when a web app
also needs to ship to the App Store / Play Store as a shell.

Wait for the user's answer before proceeding. This choice forks the
architecture and the entire scaffold plan, so do not assume.

### Step 1b: Read the PRD deeply, then tell me:
1. What the product is, who it serves, what success looks like
2. The core user flows
3. The likely architecture (stack, structure, key moving parts);
   reflect the deploy target chosen above:

   **[1] Next.js + Supabase + Vercel:**
   - Scaffold: Next.js 15 + TypeScript + Tailwind + shadcn/ui
   - Database: Supabase (use Supabase MCP for schema creation,
     migrations, RLS policies, type generation)
   - Auth: Supabase Auth (skip Clerk unless user has specific reason)
   - Deploy: Vercel auto-deploy from GitHub (one-time connect via
     Vercel UI, then every push goes live)
   - User handoff at end: "Push to GitHub → Vercel auto-deploys.
     Connect domain in Vercel project settings if you want a custom
     URL."

   **[2] Cross-platform native:**
   - Existing game-app-shaped path: Expo Router + RN Web +
     NativeWind + Cloudflare Workers OR Supabase Edge Functions +
     EAS for native builds
   - Can ship in two flavors:
     (a) iOS + Android + web (full cross-platform from one codebase,
         Vercel for the web target)
     (b) iOS + Android only (skip the apps/web/ scaffold entirely,
         no Vercel marketing site)
   - If user explicitly says "mobile only, no web" or "just iOS
     and Android," scaffold Expo + EAS without scaffolding any web
     target.
   - Warn user upfront: this path has more setup (Cloudflare account
     if using Workers, EAS account, App Store Connect, Google Play
     Console). Inherently more painful than option 1. Only choose if
     native mobile apps are required.
4. Risks, ambiguities, decisions that need my input

For option [2], the Phase 2 plan output must include store-
readiness items as explicit deliverables (not afterthoughts):
- App icons (iOS full set + Android adaptive foreground/background)
- Splash / launch screens (iOS + Android)
- Privacy policy URL (live, linked from app.json)
- ASO copy (name, subtitle, description, keywords, category)
- Screenshots for every required device size
- Content rating questionnaire (Play) + age rating (App Store)
- App Tracking Transparency strings (Info.plist) for iOS
- Permissions strings (camera, location, etc.), human-readable
- Data safety form (Play) drafts

## Phase 2: Visual Direction
Before any code, define:
- The visual style and design language for this specific product
  (luxury / clinical / startup-modern / editorial / playful / etc.)
- Typography pairing
- Color strategy
- Spacing rhythm and component style
- What will make it project-specific vs generic
- What generic SaaS patterns we'll deliberately avoid
- Mobile-first plan, then desktop refinement

## Phase 3: Initialize Project Files
After visual direction is approved, create:

1. **AGENTS.md** at project root (~50 lines). Lean project-specific rules.
   This is the single source of project rules, Claude Code reads
   AGENTS.md natively. Do NOT create a separate CLAUDE.md or symlink;
   one file only. Include: project overview, tech stack, key conventions,
   critical invariants, what must not break. Reference @PROJECT_CONTEXT.md
   and @RUNBOOK.md for deeper context.

2. **PROJECT_CONTEXT.md**, full project intelligence: architecture,
   routes, file responsibilities, design system decisions, important
   assumptions, what's been built so far.

3. **RUNBOOK.md**, practical operations: build/run/test commands,
   how to deploy to Vercel, common failure points, env var notes.

## Phase 4: Scaffold Safest Foundation
Follow the matching ~/.claude/TOOLS.md section for the exact scaffold command, the
per-project framework installs, and which MCPs to project-scope. Install only what
this project type needs; do not add MCPs or CLIs it does not use.

Only the safe first foundation:
- Folder structure
- package.json / config files
- Playwright setup (default for user-facing web)
- Base app shell
- Design system foundations (tokens, base components)
- Vercel-compatible defaults (no hardcoded ports, env handling clean)

Do NOT build every feature from the PRD yet.

## Phase 5: Build Phase 1 of the Product
After scaffold is approved:
- Core app skeleton
- Primary user flow stubbed or minimally working
- Enough visual quality that the design direction is clearly visible
- Stop here. Do not move into later phases this session.

## Rules for this session
- Do not build the whole product in one run.
- Work in small, safe steps.
- After each phase, summarize: what was created, what remains, any risks.
- Use Plan Mode (Shift+Tab twice) for each meaningful phase.
- Commit/checkpoint after each completed phase on a fresh branch.
- End in a clean PR-ready state.
- When Vercel-side work becomes needed later, prepare a ready-to-paste
  prompt for the user, do not dump technical chores on them.

Now begin:
1. Confirm you've read the PRD
2. Phase 1 (understanding + plan)
3. Phase 2 (visual direction)
4. Wait for approval before scaffolding
