---
description: Web design lessons measured on the an online store makeover (Oct 2026), for every site. First screen fit, phone hero framing, what reads as AI, how to run a design review with the owner, consistent product photos from one master, pricing UX, proof and story sections, dark emails, canvas mockup tooling. Loads with UI work; read it before planning any site design.
paths:
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.vue"
  - "**/*.svelte"
  - "**/*.astro"
  - "**/*.css"
  - "**/*.scss"
  - "**/*.dc.html"
  - "components/**"
  - "app/**"
---

# Web design lessons (an online store makeover, 24 to 27 Oct 2026)

Two review rounds with the owner took example.com from three directions to one locked look the owner called
"absolutely beautiful". Every point below cost a round trip to learn. Apply them on every site
(a second online store, a live web game, the next store) so the owner never has to say them again. `rules/design.md` holds
the standing bans; this file holds what the work taught.

## The first screen shows everything
- The whole hero fits the first screen: offer line, headline, sub line, two buttons, trust
  line AND the product. The owner's benchmark is tunedresearch.com on the owner's laptop and phone.
- Test these windows, not one: laptop 1280x600 (a 1080p laptop at 150% scaling, minus Chrome's
  bars), 1366x650, 1536x730, 1920x920; phones 360x700, 390x700, 412x760, 430x800; tablets
  768x1024 and 1024x768. Desktop headline about `clamp(40px, 3.6vw, 54px)`, two lines.
- Phones: the product image comes FIRST, then headline and buttons (Tuned's order). Search turns
  into an icon, and the top bar is one line (shorter copy under 761px, drop its icon under 380px).
- Size the phone's product frame with `aspect-ratio`, never a fixed height. A width-sized image
  inside a fixed-height frame grows on wider phones and covers the text: on example.com a kit at
  66% width spilled about 77px out of a 214px frame on the owner's 412px phone and hid the offer line,
  while a 390px test looked fine. Check at least 360, 390, 412 and 430.
- Nothing ever covers a product photo: no floating "badge" cards on images, on any screen.
- Motion is transform and opacity only, slow, and off under `prefers-reduced-motion`. Floating
  objects get a soft ground shadow that shrinks as they rise.

## What reads as AI (The owner spots it instantly)
- Anthropic's own frontend-aesthetics prompt (claude-cookbooks, `coding/prompting_for_frontend_
  aesthetics.ipynb`, read from the raw file) tells models to use JetBrains Mono, Fira Code, Space
  Grotesk, Playfair Display, Crimson Pro, Fraunces, Clash Display, Satoshi, Cabinet Grotesk, IBM
  Plex, Source Sans 3, Bricolage Grotesque, Obviously and Newsreader. So AI-built sites converge
  on those. A Newsreader design got "very AI slop, generic Claude" from the owner at a glance.
- The two default AI looks: cream paper (about `#F4F1EA`) with a high-contrast serif and clay or
  deep-green ink, and the older purple-to-blue gradient with gradient text. Also centered heroes,
  a pill badge above the headline, three rounded feature cards and numbered mono section labels
  ("01 / THE CATALOG"). The owner disliked a centered layout even in colors the owner loved.
- Fonts that passed the owner (free, self-hostable with `next/font`): Funnel Display with Funnel Sans
  (The owner's pick for an online store), Archivo (width axis 62 to 125), Host Grotesk, Mona Sans (width 75 to 125).
- A label above the headline should carry an offer or a fact ("Bulk pricing: up to 42% off"),
  never a generic category name.

## Running a design review with the owner
- Round 1: three clearly different directions, each with home, product page and cart, phone and
  desktop, on one Design canvas link. Round 2: one merged look built from the owner's comments, part by
  part ("Porcelain's layout, Night's colors, Journal's tables"). Then the owner locks a few picks.
- Show competing options in the SAME colors so the owner judges shape and type, not color: in round 1
  the owner picked a logo "due to the colors".
- Fonts: the same headline, prices and buttons in each pairing, stacked. Logos: drawn by hand as
  SVG, each with a true one-line story, shown big, at 48/32/24/16 px, in the lockup and on white.
  AI sketches (GPT Image 2.5, medium, 0.5 credits each) only to find ideas; redraw the winners.
- Make mockups work, not just look right: a ladder you can click and a cart whose numbers move
  won the owner over. Prices in mockups are the live site's real numbers.
- The owner reviews by voice. Expect transcription slips ("Lies Labs" = an online store, "whales" and "files"
  = vials, "Procellane" = Porcelain) and read the owner's attached screenshots for what the owner means.

## Product photos: one master, labels printed by code
- Never generate each product separately: AI images drift between shots and misspell names.
- Make ONE master photo per object (kit, vial) with GPT Image 2.5 (high, 2k, transparent, 2.75
  credits; pass the approved earlier render as a reference) where the label is a flat solid
  magenta `#FF00FF` placeholder. Then code prints every product's label onto it: a perspective
  warp for flat stickers, a cylinder wrap with edge shading for vials, and the magenta halo
  neutralised. Every product matches exactly, every name is right, a QR code can open the real
  product page, and the whole catalog costs no more credits. Tool: `bin/label-composite.cjs`.
- Draw the labels as HTML (real fonts) and screenshot them with headless Chrome on a transparent
  background; the same drawing is the print file for the supplier.

## Pricing that sells (tiered or bulk products)
- Product ladder: quantity, price per item, price per unit inside it, savings in money. The chosen
  row lights up and the price rolls in. A strength picker swaps the photo so the label matches.
- Bulk table on the home page: add price per mg (or per unit of active ingredient) only there and
  on the bulk page, where it shows the drop. Keep it off product cards when the brand is
  premium-priced: directories rank by per mg and invite the comparison.
- Cart: a bar that fills toward the next price break, and the REAL cost of the next item, computed
  as the difference of the two totals: "Add a 4th kit for just $320. All 4 drop to $380 each."
  People speed up near a reward (goal gradient). With all-units tiers the next item can lower
  the total (19 to 20 kits on an online store); say it plainly. Celebrate when a break unlocks, and suggest
  one more item priced at the next break.
- Prove every number with an automated click test (16 checks on an online store, mixed carts included).

## Proof and story sections
- Customer screenshots: show them whole, never cropped, in a slow strip that pauses on touch or
  hover and stops for reduced motion. Read every screenshot first: at full size the chat text is
  readable, and some say things the home page must not (customs tricks, paying for reviews).
- Brand story section (the a second online store pattern, which the owner loves): a glowing seal on the left (ring
  text around the mark), a one-line name origin, two short lines and "Read our story". Add one
  two-second typographic moment (on an online store, part of a word fades out to leave the brand name). The
  logo's own story sits under the seal.
- Copy: concrete moments beat promise lists; never name a worry you don't answer on the spot;
  a premium brand is never a "seller" and has no humble-start story. Run /unslop on every page.

## Emails
- The owner wants emails to match a dark site. Gmail's phone app recolors emails, so set dark
  backgrounds as `bgcolor` plus a same-color `background-image: linear-gradient(...)` (left
  alone), fix every text color, and check on a real phone before anything goes live.
- Follow-ups for consumables: 1, 2, 3, 6 and 12 months after delivery, stopping the moment the
  buyer reorders, never more than one a month, one-tap unsubscribe. US law (CAN-SPAM) requires a
  postal address in marketing emails, not in order emails; a registered agent's or a mail-
  service address works. Start only once orders are marked delivered.

## Mockups on a Design canvas, verified locally
- `.dc.html` artboards support state, `onClick`, `<sc-for>` and `<sc-if>`. Uploaded images give
  `/_blob/<id>` URLs, which also work inside script strings. A page shared by several screens
  (product plus cart drawer) is one artboard with a flag in state.
- Verify before showing the owner: save the type's `artifact-type/dc-runtime.js` (Artifact read with
  `path`) as `support.js` next to the page, map `/_blob/` ids to local files, and render with
  headless Chrome. Phones: load the page in an exact-width iframe (headless Chrome won't make a
  window narrower than about 500px). Click tests: `playwright-core` driving the installed Chrome.
  Tool: `bin/canvas-preview.cjs`.
- Traps met: an `inline-flex` button with `{{holes}}` in its label spaces every piece apart (wrap
  the label in one span); a fixed-height frame with width-sized images overflows on wider phones.
