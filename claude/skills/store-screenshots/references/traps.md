# Eleven silent failures

Every one of these was hit for real. None of them throw. Each ships a broken or
worse screenshot that looks fine on the screen you built it on.

The pattern they share: **a thing that appears to work, reports success, and is
wrong.** That is why every one has a guard in the pipeline rather than a note in
someone's head.

---

## 1. `document.fonts.ready` resolves before your fonts exist

`document.fonts.ready` resolves when the fonts *currently in use* have settled.
If nothing on the page uses a face yet — which is the case the moment before you
apply it — **it resolves instantly with zero fonts loaded.** Every measurement
taken after it then measures the fallback.

Observed symptom: a type comparison reported eight completely different
typefaces all fitting the same headline at the same pixel size. They were all
being measured as system-ui.

```js
// wrong
await document.fonts.ready;
el.style.fontFamily = '"Fraunces"';
measure(el);                       // measured the fallback

// right
await document.fonts.load('700 120px "Fraunces"');
await document.fonts.ready;
el.style.fontFamily = '"Fraunces"';
measure(el);
```

**Guard:** `render.mjs` derives every `(style, weight, size, family)` in use from
the DOM and asserts each with `document.fonts.check()`. A MISS is a real
substitution, never an unused face.

## 2. A Google Fonts subset 404s and the page silently falls back

One unicode-range slice failing is enough. Nothing throws, the page renders,
the typeface is wrong.

**Guard:** `fetch-fonts.mjs` downloads the faces to disk and emits local
`@font-face` rules. No network at render time, no fallback path.

## 3. A 200 from Google Fonts is not proof of a licence

`css2?family=Proxima+Nova` returns **200**. So does `Times+New+Roman`. Neither
is on Google Fonts and neither response contains a font file. If you check
licences by status code you will conclude that commercial faces are free.

```
Proxima Nova      200   gstatic slug: (none)     <- NOT free
Times New Roman   200   gstatic slug: (none)     <- NOT free
Abril Fatface     200   gstatic slug: abrilfatface
Helvetica Now     400
```

**Guard:** match `fonts.gstatic.com/s/([a-z0-9]+)/` in the response body. A real
slug is the only proof.

## 4. A headline that wraps stops getting wider

Fitting a headline by binary search on its measured width only works while it is
one line. The moment it wraps, the measured width stops growing, the search
concludes it can always go bigger, and it runs to the cap.

**Guard:** `white-space: nowrap` on the measured line is load-bearing, not
cosmetic. `templates/frame.css` marks it as such.

## 5. Fit to the longer line, not the first line

On some captions the second line is longer than the first. Fitting to line one
runs line two off the frame.

**Guard:** `templates/fit.js` measures every line and fits to the max.

## 6. A cloned probe element loses letter-spacing

Copying `getComputedStyle(el).font` onto a probe does **not** carry
`letter-spacing` — it is not part of the `font` shorthand. A headline set at
`-0.03em` measures wider on the probe than in reality, so every face is fitted
smaller than it can actually go.

**Guard:** measure the real element. Never a copy.

## 7. Headless browsers always write RGBA

Both stores reject alpha. The screenshot looks identical either way.

**Guard:** `finish.py` flattens onto black and asserts `mode == "RGB"` before it
will pass a frame.

## 8. A reconstructed screen that runs out of copy

Rebuild an app screen in HTML, put less text in it than the real screen has, and
the bottom of the phone becomes a slab of flat background above the frame edge.
It reads as a rendering bug, not as a design.

Real numbers from one build: four frames had **650–690 px** of dead screen and
nobody spotted it at full size.

**Guard:** `render.mjs` measures the gap between the last element in the
scroller and the frame cut, and flags anything over 150 px.

## 9. "DEMO" and "FREE" font files are not the font

A file named `Vanguard FREE.otf` turned out to be by a different foundry
entirely and contained **56 glyphs** — no digits, no period, no comma, no
apostrophe. The headline it was chosen for contains two full stops. It could not
set the copy at all, and its `fsType` forbade webfont embedding anyway.

`Recoleta-RegularDEMO.otf` renders beautifully and names itself "DEMO" in its
own name table.

**Guard:** `inspect-fonts.py` reports glyph coverage against the actual string
you intend to set, plus `fsType`, trademark, licence and licence URL from the
name table.

## 10. Image models cap at 9:16 and store frames are taller

`1320 × 2868` is 0.4603. The tallest aspect these models accept is 9:16 =
0.5625. Requesting an explicit pixel size gets converted to an aspect ratio and
rejected.

Generating at 2K and stretching to fit is how art starts looking cheap.

**Guard:** `art.mjs` requests 4K (3072 × 5504), `fit.py` centre-crops to the
target ratio and downsamples with Lanczos. Every pixel is a downsample.

## 11. Three ways an App Store Connect upload fails quietly

- **Sending your bearer token to the pre-signed upload URL.** Returns a bare 400
  with no explanation. Send *only* the headers in `op.requestHeaders`.
- **A body with no `Content-Type`.** Some HTTP clients label a typeless body as
  form data. Apple stores it, then cannot decode it, and the asset lands
  `FAILED` at **0 × 0**.
- **An orphaned stub blocking every retry.** If reserve succeeded and the PUT
  failed, the asset record exists with no bytes behind it, and the next attempt
  is refused with "Screenshot already exists". You have to DELETE the stub first.

**Guard:** `upload-asc.py` clears existing assets before reserving, sets an
explicit `Content-Type`, sends only Apple's headers on the PUT, and polls
`assetDeliveryState` until it is not `AWAITING_UPLOAD`.

---

## The meta-lesson

Every one of these was found by **measuring rather than looking**. The pipeline
prints numbers back at every stage — fitted headline size, eyebrow margin,
screen fill, canvas dimensions, resolved font families — precisely so that the
next silent failure announces itself instead of shipping.
