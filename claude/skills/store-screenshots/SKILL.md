---
name: store-screenshots
description: Use this skill WHENEVER the task involves App Store or Google Play store listing screenshots — designing them, writing their captions, generating their artwork, rendering them, checking them, or uploading them to App Store Connect. Trigger it for any mention of app store screenshots, Play Store screenshots, store listing images, app previews, ASO creatives, "screenshots for my app", store assets, or a listing that needs to convert better. ALSO use it when someone asks why their store screenshots look amateur, or wants to beat a competitor's listing. It carries verified store specs, eleven silent failure modes that ship broken screenshots, a competitor-review miner, and a deterministic render pipeline. Do NOT hand-make store screenshots in Figma or by prompting an image model for the whole frame — both routes produce warped device frames and melted text.
user-invocable: true
---

# Store screenshots

Deterministic App Store and Play Store screenshots for any app.

The core idea, and the thing that separates this from every "AI makes your
screenshots" tool: **an image model draws background art and nothing else.**
Type, device frames, and UI are rendered in HTML/CSS at exact pixels. Ask a
model for the whole frame and you get warped nested phones and melted small
text, every time.

## The shape of a frame that converts

Not "headline + phone". Three parts:

```
   HEADLINE          the promise, in the biggest type on the screen
      ↓
   A DEVICE          a small diagram that teaches the mechanic in one second
      ↓
   THE PHONE         the app actually doing that thing
```

The middle part is what most listings are missing and what makes the good ones
good. Four typed prompts funnelling into the one that is live on screen. Two
turn cards 231 turns apart with the gap called out between them. Three people
with three different wants. A before/after pair of the app's own status pills.

Read `references/playbook.md` before designing anything.

## Workflow

### 1. Scope

Ask, or infer from the repo:

- Which store(s)? App Store, Play, or both.
- How many frames? App Store allows 1–10 and 6–8 is normal. Play allows 2–8.
- Is there a web codebase to derive design tokens and screens from, or is this a
  native app where real device captures are the input?
- Who is the audience, and what are they currently using instead?

### 2. Research the category — do not skip this

```bash
node scripts/reviews.mjs "competitor one" "competitor two" ...
```

Apple publishes customer reviews as a public RSS feed with no key. This pulls
every 1- and 2-star review across the competitors you name and counts the
words. **Whatever people are angriest about is what your listing should
promise.** On one real run across seven apps in a category, 415 low-star
reviews ranked: ads (101 mentions), forced ID verification (131), paywalls
(137), message limits, and memory "worse than a goldfish".

That is a claims frame writing itself, from evidence rather than guesswork.

### 3. Derive the app's own design language

```bash
node scripts/derive-tokens.mjs <path-to-app-repo>
```

Reads `globals.css`, the theme file, `tailwind.config.*`, and the font
registrations, and emits a token block: palette, display face, reading face, UI
face, radii.

**This step is what makes the skill universal.** Skip it and every app you touch
comes out looking like the last one.

Two adjustments the tokens always need for print:

- **Lift the palette.** An app palette is tuned for a phone held close in a dark
  room. On a store listing scrolled past in daylight the same greys go to murk.
  Ground up a step, secondary and dim text up two, body copy near-white.
- **Split the type roles.** A display face carries the headline and the wordmark
  and nothing else. Anything a person actually reads gets a reading face. Setting
  body copy in a heavy display face turns eight lines into a wall.

### 4. Write the set

Order matters: store search shows the first two or three, so those carry the
strongest claims. Build one continuous story across the frames rather than six
disconnected feature demos — a reader who swipes should feel like they are
following something.

Every caption: 5th-to-7th-grade words, no jargon, no em dashes, nothing that
reads like marketing filler. See `references/playbook.md` for the copy rules and
the IP-safety rules, which are not optional.

### 5. Art

```bash
node scripts/art.mjs <prompt-file> <out-name> [seed]
py -3 scripts/fit.py <in.jpg> <out.jpg> <width> <height>
```

Uses OpenRouter. Every prompt must end with the composition contract and the
exclusion list in `references/playbook.md` — dark empty top for the headline,
light in the bottom third, and an explicit ban on text, letters, devices, UI and
people.

Image models cap out at 9:16 and store frames are taller than that, so generate
at 4K and centre-crop down. **Never upscale.**

### 6. Build and render

Copy `templates/` into a working directory, fill the tokens, write one HTML file
per frame.

```bash
node scripts/fetch-fonts.mjs <font-spec...>      # local webfonts, no CDN
py -3 scripts/inspect-fonts.py <dir>             # if fonts were supplied as files
node scripts/render.mjs <frame.html> <w> <h>     # renders AND asserts
py -3 scripts/finish.py <frame> <w> <h>          # flatten + legibility proofs
py -3 scripts/contact.py <out-dir> <w> <h>       # contact sheet + final gate
```

`render.mjs` fails loudly on the things that otherwise ship silently: a
substituted typeface, a headline running past the frame edge, a screen that ran
out of content, wrong canvas dimensions. Read `references/traps.md` for what each
guard is catching and why.

### 7. Prove it reads

`finish.py` emits every frame at **175px** (store search results) and **300px**
(the product page). If the headline does not survive 175px it is the wrong
typeface, not the wrong size. Look at those files before showing anyone the
full-size versions.

### 8. Upload

```bash
py -3 scripts/upload-asc.py <app-id> <frame-dir>
```

App Store Connect only. Handles the three-step reserve → PUT → finalise dance
and the three ways it fails silently (see `references/traps.md`). Play uploads go
through the Play Developer API or the console; there is no equivalent script yet.

## Hard rules

- **The image model never draws type, devices, or UI.** Background art only.
- **Never upscale.** Generate above target and come down.
- **Flatten every output.** Both stores reject alpha and every headless browser
  writes RGBA.
- **Never invent a rating, a review, an award, or a user count.** Apple guideline
  2.3.1 rejects misleading metadata. Read real numbers out of the product's own
  database instead — they are usually more interesting anyway.
- **Never show a franchise name or another user's content.** Guideline 2.3.1(a)
  covers advertising content the app does not have, and the stated penalty is
  termination of the developer account.
- **Cut elements rather than shrink them.** A crowded frame is not fixed by
  making everything smaller.
- **Measure, do not eyeball.** Every layout decision in this pipeline is a number
  the renderer prints back.

## References

- `references/specs.md` — exact dimensions and formats for both stores, with how
  to re-verify them rather than trusting any doc page
- `references/traps.md` — eleven silent failure modes and the guard for each
- `references/playbook.md` — the design system, copy rules, ordering, art prompt
  contract, IP safety
