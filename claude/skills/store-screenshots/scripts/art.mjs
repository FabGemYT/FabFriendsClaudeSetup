/**
 * Background art via OpenRouter. Art only — never type, never devices, never UI.
 *
 *   node scripts/art.mjs <prompt-file> <out-name> [seed] [model]
 *
 * Generates at 4K because store frames are TALLER than any model's maximum
 * aspect ratio (see references/traps.md #10): 1320x2868 is 0.4603 and 9:16 is
 * 0.5625. Generating above target and cropping down means every pixel in the
 * final frame is a downsample. Generating at target and stretching is how art
 * starts looking cheap.
 *
 * Reads OPENROUTER_API_KEY from the environment or from .env.local in the
 * current working directory.
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { basename, dirname, join } from "node:path";

const [promptFile, outName, seed = "11", model = "google/gemini-3.1-flash-image"] =
  process.argv.slice(2);

if (!promptFile || !outName) {
  console.error("usage: node art.mjs <prompt-file> <out-name> [seed] [model]");
  process.exit(1);
}

function apiKey() {
  if (process.env.OPENROUTER_API_KEY) return process.env.OPENROUTER_API_KEY;
  for (const f of [".env.local", ".env"]) {
    if (!existsSync(f)) continue;
    for (const line of readFileSync(f, "utf8").split("\n")) {
      if (line.startsWith("OPENROUTER_API_KEY=")) return line.split("=", 2)[1].trim();
    }
  }
  throw new Error("no OPENROUTER_API_KEY in env or .env.local");
}

const prompt = readFileSync(promptFile, "utf8").trim();
if (!/no text|no letters/i.test(prompt)) {
  console.log("  WARNING: prompt has no exclusion clause. Models WILL draw text.");
  console.log("           See references/playbook.md 'Art prompt contract'.");
}

const outDir = dirname(outName) === "." ? "art" : dirname(outName);
mkdirSync(outDir, { recursive: true });

const t0 = Date.now();
const res = await fetch("https://openrouter.ai/api/v1/images/generations", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${apiKey()}`,
    "Content-Type": "application/json",
    "X-Title": "store-screenshots",
  },
  body: JSON.stringify({
    model,
    prompt,
    aspect_ratio: "9:16",
    resolution: "4K",
    n: 1,
    seed: Number(seed),
  }),
});

const text = await res.text();
if (!res.ok) {
  console.error(`  HTTP ${res.status}: ${text.slice(0, 600)}`);
  process.exit(1);
}

const json = JSON.parse(text);
const item = json.data?.[0];
const b64 = item?.b64_json ?? item?.image_url?.url?.split(",")[1];
if (!b64) {
  console.error(`  no image bytes in response: ${text.slice(0, 400)}`);
  process.exit(1);
}

const buf = Buffer.from(b64, "base64");
// The endpoint returns JPEG regardless of any output_format you ask for.
const out = join(outDir, `${basename(outName).replace(/\.(jpe?g|png)$/i, "")}-s${seed}.jpg`);
writeFileSync(out, buf);

console.log(
  `  ${basename(out)}  ${Math.round(buf.length / 1024)}KB  ` +
    `$${(json.usage?.cost ?? 0).toFixed(4)}  ${((Date.now() - t0) / 1000).toFixed(1)}s`,
);
console.log(`  next: py -3 scripts/fit.py ${out} <out.jpg> <width> <height>`);
