/**
 * Layout pass. Include this at the end of every frame.
 *
 * Two things, in order, and both depend on the fonts genuinely being loaded:
 *
 *   1. fit the headline to the widest it can be for whichever face is loaded
 *   2. seat the phone under whatever height that produced, so a taller
 *      headline pushes the device down instead of colliding with it
 *
 * THE TRAP THIS EXISTS TO AVOID: document.fonts.ready resolves INSTANTLY when
 * no element is using a face yet, so measuring after it measures the FALLBACK.
 * That is how eight different typefaces once reported the same fit size. Every
 * face has to be requested by hand and awaited first.
 *
 * Frames set window.__fonts to the list of faces they use, e.g.
 *   window.__fonts = ['400 120px "BlockBerthold"', '400 42px "Newsreader"'];
 */
window.__ready = (async () => {
  const SAFE = parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue("--safe-w"),
  ) || 1164;
  const CAP = 180, FLOOR = 60;

  // 1. Actually load every face this frame renders.
  const specs = window.__fonts ?? [];
  if (!specs.length) {
    // Fall back to deriving them from the DOM, which is better than nothing
    // but slower and misses faces applied later.
    for (const el of document.querySelectorAll(".headline, .body, .said, .narration, .eyebrow")) {
      const s = getComputedStyle(el);
      specs.push(`${s.fontStyle === "italic" ? "italic " : ""}${s.fontWeight} ${parseInt(s.fontSize)}px ${s.fontFamily.split(",")[0]}`);
    }
  }
  await Promise.all(specs.map((s) => document.fonts.load(s).catch(() => {})));
  await document.fonts.ready;

  // 2. Fit the headline. Measure the REAL elements, never a clone: a cloned
  //    probe loses letter-spacing (not part of the `font` shorthand) and every
  //    face then fits smaller than it can. Measure BOTH lines, because the
  //    second is sometimes the longer one.
  const h = document.querySelector(".headline");
  let px = null;
  if (h) {
    const lines = [...h.querySelectorAll(".l1, .gold")];
    const measure = () => Math.max(...lines.map((el) => el.getBoundingClientRect().width));
    let lo = FLOOR, hi = 420;
    for (let i = 0; i < 40; i++) {
      const mid = (lo + hi) / 2;
      h.style.fontSize = mid + "px";
      if (measure() > SAFE) hi = mid; else lo = mid;
    }
    px = Math.min(CAP, Math.floor(lo));
    h.style.fontSize = px + "px";
  }

  // 3. Seat the device under the last thing in the stack, using the gap this
  //    frame asked for, so each layout can breathe differently.
  const wrap = document.getElementById("phoneWrap");
  let top = null;
  if (wrap) {
    const stack = document.querySelector(".stack");
    const last = stack?.lastElementChild;
    const gap = Number(wrap.dataset.gap ?? 80);
    if (last) {
      top = Math.round(last.getBoundingClientRect().bottom + gap);
      wrap.style.top = top + "px";
    }
  }

  return { headline: px ? px + "px" : null, phoneTop: top };
})();
