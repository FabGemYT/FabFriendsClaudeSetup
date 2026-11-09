# The playbook

## The frame that converts

Three parts, top to bottom. Most listings ship the first and third and wonder
why they feel flat.

```
   HEADLINE      one promise, the biggest type on the screen
      ↓
   A DEVICE      a small diagram that teaches the mechanic in one second
      ↓
   THE PHONE     the app doing exactly that, bleeding off the bottom edge
```

The middle is the whole game. Devices that have worked:

- **A funnel.** Several typed prompts stacked, the last one lit, flowing into the
  phone where it is live.
- **A distance.** Two moments from the same save, far apart, with the gap named
  on the thread between them ("231 turns later").
- **A cast.** Three people, three different wants, one line each.
- **A before/after.** The app's own status pill twice, with an arrow between.
- **A tick list.** Only when the message *is* the content — and then drop the
  phone entirely, because one text frame in a set of seven is variety, not a
  guideline problem.

## Ordering

Store search shows roughly the first two or three. Someone who swipes past that
is already interested. So:

1. **The hook.** What is this, in one line.
2–3. **The two strongest differentiators.** Ideally the ones your competitors'
   1-star reviewers complain about.
4–6. **Depth.** The things that keep people.
Last. **Reassurance.** Privacy, ownership, "it's yours".

Build **one continuous story** across the set. The same character, the same
world, the same names, from frame two through to the ending. A reader following
a life is engaged; a reader watching six feature demos is scrolling.

## Copy rules

- 5th-to-7th-grade words. If a thirteen-year-old would stumble, rewrite it.
- Two lines maximum. The second line gets the accent colour and takes the
  emphasis word.
- Say the thing. "The world remembers everything. Forever." beats "Persistent
  long-term memory".
- No em dashes. No "seamlessly", "effortlessly", "unleash", "revolutionise",
  "game-changing", "powered by AI".
- Present tense. "everything you do", not "everything you did".
- The eyebrow is a second, smaller claim, not a label. Use it to carry the half
  of the message that will not fit in the headline.

## IP safety — not optional

- **Never name a franchise.** Write the genre so the reader decodes it
  instantly: "a ninja village where im the weakest student", "a wizard school
  that already hates me", "the boy i love is a vampire and my dad hunts them".
  Every one of those lands its fandom and none is a trademark.
- **Never show another user's content.** UGC feeds, recent-activity tickers,
  public galleries — crop them out or suppress them for the capture.
- **Never advertise content the app does not contain.** Guideline 2.3.1(a). The
  stated penalty is termination of the developer account, which takes every
  other app on it down too.
- **Never invent a rating, a review, an award, a press quote, or a user count.**
  Guideline 2.3.1 rejects misleading metadata. Read real numbers out of the
  product's own database — "7,542 things remembered" is both true and better
  copy than a made-up star rating.

## Typography

- **Split the roles.** A display face for the headline and the wordmark. A
  reading face for anything a person actually reads. Setting body copy in a
  heavy display face turns eight lines into a wall.
- **Auto-fit the headline, never hardcode it.** Binary-search the largest size
  that fits the frame's safe width for whichever face is loaded. A narrower face
  then gets to be physically bigger for free, and swapping typefaces does not
  require re-laying out the frame.
- **Test at 175 px.** That is the store search result. If the headline dissolves
  there, the typeface is wrong — not the size. High-contrast serifs lose their
  hairlines first; heavy faces survive.
- **Heavy faces want less negative tracking.** A `-0.03em` that flatters a text
  serif closes the counters on a heavy rounded face.
- **A hairline rule under a heavy headline reads as an accident.** Scale the
  underline with the weight of the type above it.

## Colour

- Lift the app's palette for print. An app palette is tuned for a phone held
  close in a dark room; the same greys go to murk on a listing scrolled past in
  daylight.
- **Warm centre, cool edges** (or the reverse). A frame in a single hue is flat
  no matter how good the art is. A cool rim at the margins gives the warm
  subject something to sit against.
- If the product themes itself per item, per world, per category — use those
  colours. Colour that encodes something true is the difference between a
  scannable list and a rainbow.
- Uniform brightness on repeated items. An opacity ramp down a list looks
  designed and means half your content is unreadable.

## Art prompt contract

Every prompt ends with these two blocks. They are what keep six separately
generated plates reading as one set.

**Composition:**

> CRITICAL COMPOSITION, identical for every frame in this set: the TOP 45% of
> the frame must be near-black empty void with only a faint scatter of tiny
> distant stars or motes — no light source, no detail, nothing up there at all.
> The MIDDLE band stays dark and calm. ALL of the light lives in the BOTTOM
> THIRD and fades completely by the middle of the frame.
>
> Strong cinematic vignette on all four corners. Extreme contrast between the
> near-black ground and the light. Subtle film grain, painterly brushwork, no
> digital sharpness. Vertical portrait orientation.

**Exclusions:**

> Absolutely no text, no letters, no words, no numbers, no interface, no phone,
> no device, no screen, no logo, no watermark, no signature, no people, no
> faces, no characters, no creatures.

Adjust the light-zone for the layout — a text-only frame wants light lower, a
frame with a tall device wants it wrapping the bottom corners — but keep the
dark-top rule identical across the set or the frames stop looking related.

## The phone

- Author the screen at the device's real point width (430 for a 6.9" iPhone) and
  `zoom` it to the pixel width. `zoom` re-lays-out and stays crisp; `transform:
  scale()` rasterises at 1× and blurs.
- Let it bleed off the bottom edge. A phone that ends inside the frame looks like
  a sticker; one that runs off looks like a window.
- Fill the visible screen. See `traps.md` #8.
- Reconstruct from the app's **own CSS tokens**, not from memory. Radii, borders,
  glows and type sizes copied out of the real stylesheet are what make a rebuilt
  screen indistinguishable from a capture.
- Real captures are fine and sometimes better — but a real capture squeezed into
  a marketing frame usually fights the layout, which is why reconstruction wins
  more often than people expect.

## Competitor research

`scripts/reviews.mjs`. Apple's customer-review RSS is public and unauthenticated.
Pull 1- and 2-star reviews across the category, count the words, and read the
top ten by hand.

You are looking for two things:

1. **What people are angry about.** Those become your claims, if they are true of
   your app. Verify each one in the codebase before printing it — "no ads" means
   checking there is no ad SDK in `package.json`, not assuming.
2. **The language they use.** "worse than a goldfish after a few lines" is better
   copy than anything a marketer writes about memory.

## Anti-slop

Do not ship any of these:

- A headline in Inter, Roboto or Arial.
- A purple-to-blue gradient behind a phone.
- Three feature bullets with generic icons.
- "Powered by AI" anywhere.
- A device frame drawn by the image model.
- Stock photography of a smiling person holding a phone.
- The same layout seven times with different words.
