/**
 * Read a target app's own design language so its store frames look like it,
 * not like the last app this skill touched.
 *
 * This is the step that makes the skill universal. Without it every set comes
 * out in whatever palette the templates happened to ship with.
 *
 *   node scripts/derive-tokens.mjs <path-to-app-repo> [--json]
 *
 * Looks in the usual places (globals.css, theme files, tailwind config,
 * next/font registrations) and prints a token block ready to paste into
 * templates/frame.css, plus the two adjustments print always needs.
 */
import { readFileSync, existsSync, readdirSync, statSync } from "node:fs";
import { join, extname } from "node:path";

const root = process.argv[2];
const asJson = process.argv.includes("--json");
if (!root) {
  console.error("usage: node derive-tokens.mjs <path-to-app-repo> [--json]");
  process.exit(1);
}

const CSS_CANDIDATES = [
  "app/globals.css", "src/app/globals.css", "styles/globals.css",
  "src/styles/globals.css", "app/global.css", "src/index.css", "app.css",
];
const CONFIG_CANDIDATES = [
  "tailwind.config.ts", "tailwind.config.js", "tailwind.config.mjs",
  "app/layout.tsx", "src/app/layout.tsx", "app/_layout.tsx",
];

function readIf(rel) {
  const p = join(root, rel);
  return existsSync(p) ? readFileSync(p, "utf8") : null;
}

/** Fall back to a shallow scan when the file is not where it usually is. */
function findFirst(exts, needle, maxDepth = 3) {
  const walk = (dir, depth) => {
    if (depth > maxDepth) return null;
    let entries;
    try { entries = readdirSync(dir); } catch { return null; }
    for (const e of entries) {
      if (e === "node_modules" || e === ".next" || e === ".git" || e.startsWith(".")) continue;
      const p = join(dir, e);
      let s;
      try { s = statSync(p); } catch { continue; }
      if (s.isDirectory()) {
        const hit = walk(p, depth + 1);
        if (hit) return hit;
      } else if (exts.includes(extname(e))) {
        const body = readFileSync(p, "utf8");
        if (body.includes(needle)) return { path: p, body };
      }
    }
    return null;
  };
  return walk(root, 0);
}

let css = CSS_CANDIDATES.map(readIf).find(Boolean);
let cssPath = CSS_CANDIDATES.find((c) => readIf(c));
if (!css) {
  const hit = findFirst([".css"], "--color");
  if (hit) { css = hit.body; cssPath = hit.path; }
}

const configs = CONFIG_CANDIDATES.map((c) => ({ rel: c, body: readIf(c) })).filter((c) => c.body);

// ---- palette -------------------------------------------------------------
// Custom properties first: they are the app's own vocabulary, and their names
// tell you what each colour is FOR, which a raw hex sweep cannot.
const vars = new Map();
if (css) {
  for (const m of css.matchAll(/(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\))\s*;/g)) {
    if (!vars.has(m[1])) vars.set(m[1], m[2]);
  }
}

const pick = (...needles) => {
  for (const n of needles) {
    for (const [k, v] of vars) if (k.includes(n)) return { name: k, value: v };
  }
  return null;
};

const palette = {
  ground: pick("bg-primary", "background", "-bg", "surface"),
  card: pick("bg-card", "bg-secondary", "card", "panel"),
  text: pick("text-primary", "foreground", "-text"),
  text2: pick("text-secondary", "muted"),
  dim: pick("text-dim", "subtle", "faint"),
  accent: pick("accent", "primary", "brand"),
};

// ---- fonts ---------------------------------------------------------------
const fonts = new Set();
for (const c of configs) {
  for (const m of c.body.matchAll(/import\s*\{([^}]+)\}\s*from\s*["']next\/font\/google["']/g)) {
    for (const f of m[1].split(",")) if (f.trim()) fonts.add(f.trim().replace(/_/g, " "));
  }
  for (const m of c.body.matchAll(/variable:\s*["'](--font-[a-z-]+)["']/g)) fonts.add(`var: ${m[1]}`);
}
if (css) {
  for (const m of css.matchAll(/font-family:\s*([^;]+);/g)) {
    const first = m[1].split(",")[0].trim().replace(/["']/g, "");
    if (first && !first.startsWith("var(") && first.length < 40) fonts.add(first);
  }
}

// ---- radii ---------------------------------------------------------------
const radii = new Set();
if (css) for (const m of css.matchAll(/border-radius:\s*([0-9.]+(?:px|rem))/g)) radii.add(m[1]);

const out = {
  cssSource: cssPath ?? "(not found)",
  configs: configs.map((c) => c.rel),
  palette: Object.fromEntries(Object.entries(palette).map(([k, v]) => [k, v ? `${v.value}  (${v.name})` : null])),
  fonts: [...fonts],
  commonRadii: [...radii].slice(0, 8),
};

if (asJson) {
  console.log(JSON.stringify(out, null, 2));
  process.exit(0);
}

console.log(`\n  source: ${out.cssSource}`);
console.log(`  configs: ${out.configs.join(", ") || "(none)"}\n`);
console.log("  --- palette found ---");
for (const [role, v] of Object.entries(out.palette)) console.log(`    ${role.padEnd(8)} ${v ?? "(not found)"}`);
console.log("\n  --- fonts referenced ---");
for (const f of out.fonts) console.log(`    ${f}`);
console.log(`\n  --- common radii ---\n    ${out.commonRadii.join("  ") || "(none)"}`);

console.log(`
  --- paste into templates/frame.css, then apply BOTH print adjustments ---

  1. LIFT THE PALETTE. These values are tuned for a phone held close in a dark
     room. On a listing scrolled past in daylight they read as murk. Ground up
     one step, secondary and dim text up two, body copy near-white. Keep the
     hue and the relationships; change only the exposure.

  2. SPLIT THE TYPE ROLES. Pick ONE display face for the headline and wordmark.
     Everything a person actually reads gets the reading face. If the app has a
     single font, find a display partner rather than setting a headline in the
     body face.
`);
