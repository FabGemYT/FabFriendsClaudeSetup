# store-screenshots

A Claude Code skill for making App Store and Google Play listing screenshots
that convert, for any app.

The core idea, and the thing that separates this from every "AI makes your
screenshots" tool: **an image model draws background art and nothing else.**
Type, device frames and UI are rendered in HTML/CSS at exact pixels. Ask a model
for the whole frame and you get warped nested phones and melted small text,
every time.

## What is actually in here

**A pipeline** — research the category, derive the target app's design tokens,
generate art, render frames, prove they read at listing size, upload.

**Eleven silent failure modes and a guard for each.** This is most of the value.
Every one of them was hit for real, none of them throws, and each ships a broken
or worse screenshot that looks fine on the machine that made it. A font that
silently falls back. A headline fitted against the wrong measurement. An alpha
channel both stores reject. A rebuilt screen with 650px of dead space nobody
noticed. See [`references/traps.md`](references/traps.md).

**Verified store specs**, with instructions for re-verifying them rather than
trusting any doc page — on one check, Apple's own help page was summarised back
as the wrong dimensions, which would have produced a rejected upload. See
[`references/specs.md`](references/specs.md).

**A design playbook** — the frame structure that converts, copy rules, ordering,
the art-prompt contract, and the IP-safety rules that keep a listing from
getting an entire developer account terminated. See
[`references/playbook.md`](references/playbook.md).

## The frame that converts

Not "headline + phone". Three parts:

```
   HEADLINE          the promise, in the biggest type on the screen
      ↓
   A DEVICE          a small diagram that teaches the mechanic in one second
      ↓
   THE PHONE         the app actually doing that thing
```

The middle part is what most listings are missing.

## Install

```bash
git clone <this repo> ~/.claude/skills/store-screenshots
```

Then `/store-screenshots` in Claude Code, or just ask for store screenshots and
it triggers on its own.

## Requirements

```bash
npm i -g playwright && npx playwright install chromium
py -3 -m pip install pillow fonttools brotli pyjwt cryptography
```

- `OPENROUTER_API_KEY` for art generation
- `APPLE_KEY_ID`, `APPLE_ISSUER_ID`, `APPLE_P8_PATH` for App Store Connect upload

## Scripts

| | |
|---|---|
| `derive-tokens.mjs` | read the target app's palette, fonts and radii — the step that makes this universal |
| `reviews.mjs` | mine competitors' 1- and 2-star App Store reviews (public RSS, no key) |
| `art.mjs` | background art via OpenRouter at 4K |
| `fit.py` | centre-crop and downsample to the store frame; refuses to upscale |
| `fetch-fonts.mjs` | local webfonts, and tells you which families are not actually free |
| `inspect-fonts.py` | glyph coverage, embedding permission and licence strings of supplied font files |
| `render.mjs` | render + assert; non-zero exit on anything that would ship broken |
| `finish.py` | flatten alpha, verify dimensions, emit 175px and 300px legibility proofs |
| `contact.py` | contact sheet and the final submittability gate |
| `upload-asc.py` | App Store Connect upload, with all three of its silent failures handled |

## Licence

MIT.
