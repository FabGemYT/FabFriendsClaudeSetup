---
description: Premium design standards for any UI work (anti-slop bans, component stack, the review loop). Auto-loads when touching UI files; also read it explicitly for any design task.
paths:
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.vue"
  - "**/*.svelte"
  - "**/*.astro"
  - "**/*.css"
  - "**/*.scss"
  - "**/components.json"
  - "components/**"
  - "app/**"
---

# Design system (premium by default)

Premium by default. Never ship generic AI output. Every UI is project-specific,
mobile-first, with real hierarchy and intentional spacing, type, and color.

What the an online store makeover taught (first-screen fit, phone hero framing, the AI font list,
review rounds, product photos, pricing UX, dark emails): `rules/web-design-lessons.md`.

## Layered prompt protocol
Work in order: vibe, palette, typography, layout, components. Anchor the vibe to a
NAMED reference brand (e.g. "feel like Linear", "like Stripe", "like Vercel"), never
"make it nice". If the user named no reference, propose two or three and confirm one
before building (Law 6: options before build on costly decisions).

## Anti-slop bans (these scream AI-generated; never ship them)
- No Inter, Roboto, or Arial as the headline font. Choose a characterful display face
  and pair it on purpose.
- No default purple-to-blue AI gradient, no generic glassmorphism.
- No fake names, numbers, logos, or avatars. No Unsplash placeholders.
- Always customize shadcn defaults (color, radius, spacing, type); stock shadcn is a
  starting point, not a finished look.
- Production-ready only: no lorem ipsum, no placeholder UI, no dead links.

## Favicon: Google shows a grey globe without a PNG or ICO
Google Search shows a site's icon only from BMP, GIF, ICO, PNG, JPEG, PPM or TIFF, never
SVG (favicon guide, updated 2026-08-28). a second online store launched 2026-10-15 with only
app/icon.svg and Google showed the globe; the owner's six other sites declare a PNG or ICO icon and
all show their logo. Every site ships, from the real logo: `app/favicon.ico` (16, 32 and
48 px) and a square PNG icon of 192 px or more (`app/icon.png`, or `icon1.png` beside an
`icon.svg`). An SVG icon is fine as an extra, never alone. After launch, check that Google
holds it (200 = the logo, 404 = the globe):

    curl -s -o /dev/null -w "%{http_code}" "https://t1.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://<domain>&size=64"

then request indexing of the home page. Google takes days to weeks to show a new icon.

## Component stack (per project)
shadcn/ui is the base, pulled via the shadcn CLI (`npx shadcn@latest search`, `view`,
`docs`, `add`), never hand-rolled. (The shadcn MCP server was removed 2026-10-30: 0 calls
in two months while it held ~0.23 GB in every open session; the CLI reads the same registry.)
Register two premium registries in the project's components.json so heroes and motion
come from them:
   "registries": {
     "@aceternity": "https://ui.aceternity.com/registry/{name}.json",
     "@magicui": "https://magicui.design/r/{name}.json"
   }
Then npx shadcn@latest add @aceternity/<x> or @magicui/<y>. Needs shadcn CLI 3.0+,
Tailwind v4 (Aceternity keeps a v3 legacy path), and the motion package (not
framer-motion). Use these for hero sections, backgrounds, and animation; hand-code only
the bespoke parts.

## The loop (no UI is "done" until this runs)
Generate, then agent-browser desktop screenshot, then the design-reviewer subagent
critiques against premium standards, then iterate; 2 to 3 rounds minimum before handoff.
For mobile, screenshot with playwright-cli in real device profiles (iPhone/Pixel);
agent-browser is desktop-only on this Windows setup. NEVER claim mobile is verified from
code: render and look. Emulation catches layout and responsive breaks but runs in a
desktop engine, so it misses real iOS Safari rendering, touch, PWA, and performance.
After emulation passes, hand over the preview URL for the real-phone check, the mobile
source of truth.

## Security (registry components are third-party code)
Before installing an @aceternity or @magicui component, review its source via the
registry JSON or `npx shadcn@latest view <item>`. After install, run the shadcn audit checklist (imports,
next/image remotePatterns, deps, lint, types). Keep paid registries (e.g. @magicui-pro)
behind an env-var Bearer token in .env.local, never inline.

## Living mascots and characters (learned on a live web game's Scribe, 15 Oct 2026; the owner asked for this here)
A mascot should feel ALIVE: it breathes, moves, reacts. Pick the lightest rung that does it,
and measure one before planning on any paid tool.
1. **CSS motion on the real art. The default, and what shipped for the Scribe.** Keyframes on
   the existing PNG/WebP, `transform` and `opacity` only: a float plus a breath squash from the
   feet (`transform-origin: 50% 92%`), a slight sway, a pop-in on every state change (key the
   element so it replays), body language per state (a hop with squash-and-stretch to
   celebrate, a lean to ask, a bow to thank), a giggle on tap, CSS-drawn sparkles (a
   `clip-path` star), a soft ground shadow that shrinks as it rises. Zero runtime, the same
   character, works on every theme, and `prefers-reduced-motion: reduce` stills it.
2. **Layered SVG plus CSS**, when it must blink, follow the finger or talk: it needs the art as
   separate layers (eyes, lids, mouth, limbs). Only from art you control (a designer's layered
   file, or a careful vectorization of the real art). An AI redraw from a text prompt drifts
   off-model; Recraft vector on Higgsfield takes text only, no reference image.
3. **Rive** (Duolingo's choice: state machines, lip-sync) when a human animator exists. It is
   authored in Rive's GUI editor, not in code; budget ~100-200 KB of runtime.
4. **Lottie** for designer-made After Effects clips; it plays clips, it does not react.
5. **AI frame animation** (sprite sheet or animated WebP): Higgsfield AutoSprite (2 credits a
   sheet on turbo, failures refunded) failed 4 of 4 on the Scribe, a round non-humanoid mascot,
   with a transparent PNG and with a solid 1024px copy. It is built for humanoid game sprites;
   try one before promising it. Higgsfield GPT Image 2.5 (0.5 credits) re-renders a mascot
   faithfully on a plain background, but adds outlines the original may not have.
Rules for any of them: never animate text or layout; decorative pieces are `aria-hidden` and
`pointer-events: none`; tint them from the theme's own tokens so a light theme still shows
them; the mascot must hold still when the OS asks for less motion.

## Trusted design skills (name them in the plan, never rely on auto-fire)
frontend-design-official (aesthetic direction), ui-ux-pro-max (palettes, type, patterns),
impeccable (anti-slop polish), web-design-guidelines (accessibility and compliance final pass).
