/**
 * Download webfonts to disk and emit local @font-face rules.
 *
 *   node scripts/fetch-fonts.mjs "Newsreader:opsz,wght@6..72,400;6..72,500" "Inter:wght@400;600"
 *
 * A render that fetches fonts over the network can fall back SILENTLY: one 404
 * on one unicode-range subset and the frame ships in Times with nothing in the
 * output saying so (references/traps.md #2). Local files remove the failure
 * mode and make renders reproducible.
 *
 * Also prints whether each family is genuinely on Google Fonts. A 200 is not
 * proof — the API answers 200 for Proxima Nova and Times New Roman while
 * serving no font at all (traps.md #3). Only a real gstatic slug counts.
 */
import { writeFileSync, mkdirSync } from "node:fs";

const specs = process.argv.slice(2);
if (!specs.length) {
  console.error('usage: node fetch-fonts.mjs "Family:axes" ["Family:axes" ...]');
  process.exit(1);
}

const OUT = "fonts";
mkdirSync(OUT, { recursive: true });
// A modern UA is what makes Google Fonts serve woff2 rather than ttf.
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

const faces = [];
for (const spec of specs) {
  const family = spec.split(":")[0];
  const url = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(spec).replace(/%3A/g, ":").replace(/%40/g, "@").replace(/%3B/g, ";").replace(/%2C/g, ",").replace(/%20/g, "+")}&display=block`;

  const res = await fetch(url, { headers: { "User-Agent": UA } });
  const css = res.ok ? await res.text() : "";
  const slug = /fonts\.gstatic\.com\/s\/([a-z0-9]+)\//i.exec(css)?.[1];

  if (!slug) {
    console.log(`  ${family.padEnd(22)} NOT ON GOOGLE FONTS (status ${res.status}, no font served)`);
    console.log(`  ${" ".repeat(22)} -> commercial or OS-bundled. Needs a paid webfont licence.`);
    continue;
  }

  let n = 0;
  for (const block of css.split("@font-face").slice(1)) {
    const range = /unicode-range:\s*([^;]+);/.exec(block)?.[1] ?? "";
    // Keep the latin blocks only; the rest is what 404s and we never render it.
    const isLatin = range === "" || range.includes("U+0000") || range.includes("U+0025-00FF");
    if (!isLatin) continue;
    const src = /url\((https:[^)]+\.woff2)\)/.exec(block)?.[1];
    if (!src) continue;
    const weight = (/font-weight:\s*([^;]+);/.exec(block)?.[1] ?? "400").trim();
    const style = (/font-style:\s*([^;]+);/.exec(block)?.[1] ?? "normal").trim();

    const file = `${family.toLowerCase().replace(/\s+/g, "")}-${style}-${weight.replace(/\s+/g, "_")}-${n++}.woff2`;
    const buf = Buffer.from(await (await fetch(src, { headers: { "User-Agent": UA } })).arrayBuffer());
    writeFileSync(`${OUT}/${file}`, buf);
    faces.push(
      `@font-face{font-family:"${family}";font-style:${style};font-weight:${weight};` +
        `font-display:block;src:url("../fonts/${file}") format("woff2");}`,
    );
    console.log(`  ${family.padEnd(22)} ${file}  ${Math.round(buf.length / 1024)}KB  (${style} ${weight})`);
  }
}

writeFileSync(`${OUT}/faces.css`, faces.join("\n") + "\n");
console.log(`\n  wrote ${OUT}/faces.css  (${faces.length} faces)`);
console.log(`  link it from every frame BEFORE the frame stylesheet.`);
