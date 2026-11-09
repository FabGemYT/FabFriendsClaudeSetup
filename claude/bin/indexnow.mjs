#!/usr/bin/env node
/**
 * Tell Bing, Copilot, Yandex, Naver and the other IndexNow engines that pages changed.
 * Google is NOT part of IndexNow: it learns from the sitemap and Search Console (gsc.py,
 * and "Request indexing" in the browser). ChatGPT Search and Copilot lean on Bing's index,
 * so this is also the quick road into AI answers.
 *
 *   node ~/.claude/bin/indexnow.mjs example.com /pricing /blog/new-post   just these pages
 *   node ~/.claude/bin/indexnow.mjs example.com --changed-days 3          sitemap pages dated in the last 3 days
 *   node ~/.claude/bin/indexnow.mjs example.com --all                     every sitemap URL (first launch only)
 *   add --dry-run to print what would be sent and send nothing
 *   add --key <32 hex> when the key file is not in ./public of the current project
 *
 * Generalised from two scripts that run in production: a second online store' scripts/indexnow.mjs
 * (paths or the whole sitemap, key file in public/) and an online store' daily cron
 * (src/app/api/cron/indexnow: only pages whose sitemap date is within three days, because a
 * page's date is set when the change is written, not when it ships, and a 31-hour window
 * missed changes merged the next morning).
 *
 * Rules that come with it:
 *  - Only pages that actually changed. IndexNow's FAQ: it "is not designed for submitting
 *    every URL on your site at once"; the sitemap carries the whole site. --all is for a
 *    first launch, after the launch checklist, never as a habit.
 *  - Production only, after the deploy is live. Never a preview URL.
 *  - The key is public by design (served at https://<host>/<key>.txt); it only proves the
 *    site is yours, and it must never change. This script checks it is live before sending.
 * Protocol: https://www.indexnow.org/documentation (POST host, key, keyLocation, urlList;
 * up to 10,000 URLs a request; 200 or 202 means accepted).
 */
import fs from "node:fs";
import path from "node:path";

const ENDPOINT = "https://api.indexnow.org/IndexNow";
const MAX_PER_REQUEST = 10000;

function usage(msg) {
  if (msg) console.error(`indexnow: ${msg}`);
  console.error("usage: node indexnow.mjs <host> [/path ...] [--changed-days N | --all] [--key <32hex>] [--dry-run]");
  process.exit(2);
}

const args = process.argv.slice(2);
if (!args.length || args.includes("-h") || args.includes("--help")) usage();
const host = args[0].replace(/^https?:\/\//, "").replace(/\/.*$/, "");
if (!/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(host)) usage(`"${args[0]}" is not a host like example.com`);
const origin = `https://${host}`;
const dryRun = args.includes("--dry-run");
const all = args.includes("--all");
const daysAt = args.indexOf("--changed-days");
const days = daysAt === -1 ? null : Number(args[daysAt + 1]);
if (daysAt !== -1 && !(days > 0)) usage("--changed-days needs a number of days, e.g. 3");
const keyAt = args.indexOf("--key");
let key = keyAt === -1 ? null : args[keyAt + 1];
// Git Bash on Windows rewrites a leading-slash argument into a Windows path before node
// sees it ("/pricing" arrives as "C:/Program Files/Git/pricing"). Undo that for the
// default Git install; refuse anything else that looks like a drive path, with the fix.
const paths = args.slice(1)
  .filter((a, i, arr) => !a.startsWith("--") && arr[i - 1] !== "--key" && arr[i - 1] !== "--changed-days")
  .map((a) => {
    const m = a.replace(/\\/g, "/").match(/^[A-Za-z]:\/(?:.*\/)?Git\/(.*)$/i);
    if (m) return `/${m[1]}`;
    if (/^[A-Za-z]:[\\/]/.test(a)) usage(`"${a}" is a Windows path, not a page. Pass the page without its leading slash (pricing) or as a full URL.`);
    return a;
  });
if ((all ? 1 : 0) + (days ? 1 : 0) + (paths.length ? 1 : 0) !== 1) usage("give pages, or --changed-days N, or --all (exactly one)");

if (!key) {
  const pub = path.join(process.cwd(), "public");
  const found = fs.existsSync(pub) ? fs.readdirSync(pub).find((f) => /^[0-9a-f]{32}\.txt$/.test(f)) : null;
  if (!found) usage("no key: put a 32-hex <key>.txt in ./public (served at the site root) or pass --key");
  key = found.slice(0, 32);
}
if (!/^[0-9a-f]{32}$/i.test(key)) usage("the key must be 32 hex characters");
const keyLocation = `${origin}/${key}.txt`;

async function text(url) {
  const r = await fetch(url, { headers: { "User-Agent": "indexnow.mjs" }, redirect: "follow" });
  if (!r.ok) throw new Error(`${url} answered ${r.status}`);
  return r.text();
}

// Every <url> in the sitemap, following sitemap index files (split sitemaps).
async function sitemapEntries(url, depth = 0) {
  const xml = await text(url);
  if (/<sitemapindex[\s>]/i.test(xml) && depth < 3) {
    const subs = [...xml.matchAll(/<sitemap>[\s\S]*?<loc>\s*([^<\s]+)\s*<\/loc>[\s\S]*?<\/sitemap>/gi)].map((m) => m[1]);
    const nested = await Promise.all(subs.map((s) => sitemapEntries(s, depth + 1)));
    return nested.flat();
  }
  return [...xml.matchAll(/<url>([\s\S]*?)<\/url>/gi)].map((m) => ({
    loc: (m[1].match(/<loc>\s*([^<\s]+)\s*<\/loc>/i) || [])[1],
    lastmod: (m[1].match(/<lastmod>\s*([^<\s]+)\s*<\/lastmod>/i) || [])[1],
  })).filter((e) => e.loc);
}

async function main() {
  let urlList;
  if (paths.length) {
    urlList = paths.map((p) => (p.startsWith("http") ? p : origin + (p.startsWith("/") ? p : `/${p}`)));
  } else {
    const entries = await sitemapEntries(`${origin}/sitemap.xml`);
    const since = days ? Date.now() - days * 24 * 60 * 60 * 1000 : null;
    urlList = entries
      .filter((e) => !since || (e.lastmod && new Date(e.lastmod).getTime() >= since))
      .map((e) => e.loc);
  }
  urlList = [...new Set(urlList)].filter((u) => {
    try { return new URL(u).host === host && u.startsWith("https://"); } catch { return false; }
  });
  if (!urlList.length) {
    console.log(days ? `Nothing to send: no sitemap page is dated within the last ${days} day(s).` : "Nothing to send.");
    { process.exitCode = 0; return; }
  }

  // IndexNow rejects a submission whose key file is not live, so check before sending.
  let keyLive = false;
  try { keyLive = (await text(keyLocation)).trim().startsWith(key); } catch { keyLive = false; }

  if (dryRun) {
    console.log(`DRY RUN, nothing sent. host ${host}, key file ${keyLocation} (${keyLive ? "live" : "NOT live"})`);
    console.log(`${urlList.length} URL(s) would be sent${urlList.length > 10 ? "; first 10:" : ":"}`);
    for (const u of urlList.slice(0, 10)) console.log(`  ${u}`);
    { process.exitCode = keyLive ? 0 : 1; return; }
  }
  if (!keyLive) {
    console.error(`indexnow: the key file ${keyLocation} is not live, so IndexNow would reject this. Deploy it first.`);
    { process.exitCode = 1; return; }
  }

  let failed = false;
  for (let i = 0; i < urlList.length; i += MAX_PER_REQUEST) {
    const batch = urlList.slice(i, i + MAX_PER_REQUEST);
    const res = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ host, key, keyLocation, urlList: batch }),
    });
    const ok = res.status === 200 || res.status === 202;
    console.log(`${batch.length} URL(s): ${res.status} ${ok ? "accepted" : await res.text()}`);
    if (!ok) failed = true;
  }
  { process.exitCode = failed ? 1 : 0; return; }
}

await main();
