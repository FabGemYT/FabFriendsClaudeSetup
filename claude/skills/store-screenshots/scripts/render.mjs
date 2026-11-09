/**
 * Render a frame to an exact-size PNG, and assert everything that otherwise
 * ships silently.
 *
 *   node scripts/render.mjs <frame.html> [width] [height] [--out dir]
 *   node scripts/render.mjs frames/f1.html 1320 2868
 *
 * The rendering is the easy half. The assertions are the point: every check
 * here corresponds to a real failure that produced a broken screenshot nobody
 * noticed (references/traps.md).
 *
 * Exit code is non-zero if any hard check fails, so this can gate a build.
 */
import { mkdirSync, existsSync } from "node:fs";
import { basename, resolve, join } from "node:path";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";
import { execSync } from "node:child_process";

/**
 * A skill lives in ~/.claude/skills/ and gets run against whatever repo the
 * user is in. A bare `import "playwright"` resolves relative to THIS file, so
 * it never sees the caller's node_modules and dies with ERR_MODULE_NOT_FOUND.
 * Try the working directory first, then a global install, then this file.
 */
async function loadChromium() {
  const attempts = [
    () => createRequire(pathToFileURL(join(process.cwd(), "_.js")).href)("playwright"),
    () => createRequire(pathToFileURL(join(process.cwd(), "_.js")).href)("playwright-core"),
    () => {
      const root = execSync("npm root -g", { encoding: "utf8" }).trim();
      return createRequire(pathToFileURL(join(root, "_.js")).href)("playwright");
    },
  ];
  for (const attempt of attempts) {
    try {
      const mod = attempt();
      if (mod?.chromium) return mod.chromium;
    } catch {}
  }
  try {
    return (await import("playwright")).chromium;
  } catch {
    console.error(
      "  playwright not found. Install it where you are running this:\n" +
        "    npm i -D playwright && npx playwright install chromium\n" +
        "  or globally:\n" +
        "    npm i -g playwright && npx playwright install chromium",
    );
    process.exit(1);
  }
}
const chromium = await loadChromium();

const args = process.argv.slice(2);
const src = args[0];
const W = Number(args[1] ?? 1320);
const H = Number(args[2] ?? 2868);
const outIdx = args.indexOf("--out");
const OUT = outIdx > -1 ? args[outIdx + 1] : "out";

if (!src || !existsSync(src)) {
  console.error("usage: node render.mjs <frame.html> [width] [height] [--out dir]");
  process.exit(1);
}
mkdirSync(OUT, { recursive: true });
const name = basename(src).replace(/\.html?$/i, "");

let hard = 0;
const fail = (msg) => { hard++; console.log(`  FAIL  ${msg}`); };
const warn = (msg) => console.log(`  WARN  ${msg}`);

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: W, height: H },
  deviceScaleFactor: 1,
  colorScheme: "dark",
});
const page = await ctx.newPage();

const netFails = [];
page.on("requestfailed", (r) => netFails.push(r.url().slice(-70)));
page.on("console", (m) => m.type() === "error" && netFails.push(`console: ${m.text().slice(0, 90)}`));

await page.goto(pathToFileURL(resolve(src)).href, { waitUntil: "networkidle" });
// Frames may expose a layout pass (headline fitting, device seating).
await page.evaluate(() => window.__ready).catch(() => {});
await page.waitForTimeout(700);

if (netFails.length) fail(`resources failed: ${netFails.join(" | ")}`);

// ---- 1. no silently substituted typeface --------------------------------
// Derived from what the frame actually renders, so a MISS always means a real
// substitution rather than an unused face that was never fetched.
const fonts = await page.evaluate(() => {
  const seen = new Map();
  for (const el of document.querySelectorAll("*")) {
    const hasText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!hasText) continue;
    const s = getComputedStyle(el);
    const fam = s.fontFamily.split(",")[0].replace(/["']/g, "").trim();
    const spec = `${s.fontStyle === "italic" ? "italic " : ""}${s.fontWeight} ${Math.round(parseFloat(s.fontSize))}px "${fam}"`;
    if (!seen.has(spec)) seen.set(spec, { ok: document.fonts.check(spec), who: (el.className || el.tagName).toString().slice(0, 26) });
  }
  return [...seen].map(([spec, v]) => ({ spec, ...v }));
});
const missing = fonts.filter((f) => !f.ok);
console.log(`  fonts in use: ${fonts.length}`);
for (const f of missing) fail(`typeface not loaded: ${f.spec}  <- .${f.who}`);

// ---- 2. exact canvas -----------------------------------------------------
const box = await page.locator(".frame").first().boundingBox();
if (!box) {
  fail("no .frame element found");
} else {
  console.log(`  canvas: ${Math.round(box.width)}x${Math.round(box.height)}`);
  if (Math.round(box.width) !== W || Math.round(box.height) !== H) {
    fail(`canvas is ${Math.round(box.width)}x${Math.round(box.height)}, expected ${W}x${H}`);
  }
}

// ---- 3. nothing crowding the frame edge ----------------------------------
const edges = await page.evaluate((frameW) => {
  const out = [];
  for (const sel of [".headline", ".eyebrow"]) {
    const el = document.querySelector(sel);
    if (!el) continue;
    const r = el.getBoundingClientRect();
    out.push({ sel, left: Math.round(r.left), right: Math.round(frameW - r.right), w: Math.round(r.width) });
  }
  return out;
}, W);
for (const e of edges) {
  const m = Math.min(e.left, e.right);
  console.log(`  ${e.sel.padEnd(10)} ${e.w}px wide, ${m}px margin`);
  if (m < 40) fail(`${e.sel} is ${m}px from the frame edge`);
  else if (m < 70) warn(`${e.sel} is tight at ${m}px from the edge`);
}

// ---- 4. nothing clipped inside its container -----------------------------
// Two different measurements, because summing children only means anything for
// a container laying them out in a ROW. Applying it to a block card whose
// children stack vertically reports every card as 3x overflowing, and a guard
// that cries wolf gets ignored.
const overflow = await page.evaluate(() =>
  [...document.querySelectorAll("[data-nowrap], .qcard, .card, .tick, .person, .chip, .chiprow")].flatMap((c) => {
    const s = getComputedStyle(c);
    const isRow = s.display.includes("flex") && s.flexDirection === "row" && s.flexWrap === "nowrap";
    const label = (c.className || c.tagName).toString().slice(0, 26);

    if (isRow) {
      const kids = [...c.children];
      const pad = parseFloat(s.paddingLeft) + parseFloat(s.paddingRight);
      const gap = (parseFloat(s.columnGap) || parseFloat(s.gap) || 0) * Math.max(0, kids.length - 1);
      const used = kids.reduce((n, el) => n + el.getBoundingClientRect().width, 0) + gap + pad;
      return used > c.clientWidth + 1 ? [`${label}: row needs ${Math.round(used)}px, has ${c.clientWidth}px`] : [];
    }
    // Anything else: nowrap text that runs past its box is what scrollWidth catches.
    return c.scrollWidth > c.clientWidth + 1
      ? [`${label}: content is ${c.scrollWidth}px, box is ${c.clientWidth}px`]
      : [];
  }),
);
for (const o of overflow) fail(`clipped — ${o}`);

// ---- 5. a rebuilt screen that ran out of content -------------------------
const fill = await page.evaluate(() => {
  const scroller = document.querySelector(".app .scroller");
  const screen = document.querySelector(".screen");
  if (!scroller || !screen || !scroller.children.length) return null;
  const last = [...scroller.children].pop().getBoundingClientRect().bottom;
  const cut = Math.min(screen.getBoundingClientRect().bottom, window.innerHeight);
  return { dead: Math.round(cut - last) };
});
if (fill) {
  console.log(`  screen fill: ${fill.dead}px empty below the last element`);
  if (fill.dead > 150) warn(`${fill.dead}px of dead screen — a rebuilt screen that ran out of copy reads as a rendering bug`);
}

await page.screenshot({ path: `${OUT}/${name}-raw.png`, clip: { x: 0, y: 0, width: W, height: H } });
await browser.close();

console.log(`  wrote ${OUT}/${name}-raw.png`);
console.log(`  next: py -3 scripts/finish.py ${name} ${W} ${H} --dir ${OUT}`);
if (hard) {
  console.log(`\n  ${hard} hard failure(s) — do not ship this frame.`);
  process.exit(1);
}
