/**
 * Mine competitors' 1- and 2-star App Store reviews.
 *
 *   node scripts/reviews.mjs "character ai" "talkie" "polybuzz" ...
 *
 * Apple publishes customer reviews as a public RSS feed with no key and no
 * auth. This is the single highest-value research step in the whole pipeline,
 * because it replaces guessing about your positioning with counting what your
 * competitors' own angriest users write.
 *
 * On one real run across seven apps in a category, 415 low-star reviews ranked:
 * ads (101 mentions), age/ID verification (131), paywalls and subscriptions
 * (137), message limits, and memory "worse than a goldfish after a few lines".
 * Every one of those became a line in a claims frame — verified true of the
 * product first.
 *
 * Two things to take away:
 *   1. WHAT they are angry about  -> your claims, if you can honestly make them
 *   2. HOW they say it            -> better copy than any marketer writes
 */
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

const terms = process.argv.slice(2);
if (!terms.length) {
  console.error('usage: node reviews.mjs "competitor one" "competitor two" ...');
  process.exit(1);
}

const country = process.env.STORE_COUNTRY ?? "us";

// Resolve by search rather than hardcoding IDs, which rot.
const apps = [];
for (const t of terms) {
  try {
    const r = await fetch(
      `https://itunes.apple.com/search?term=${encodeURIComponent(t)}&entity=software&country=${country}&limit=3`,
      { headers: { "User-Agent": UA } },
    );
    const hit = JSON.parse(await r.text()).results?.[0];
    if (!hit) { console.log(`  ${t}: no match`); continue; }
    apps.push({ id: hit.trackId, name: hit.trackName });
    console.log(
      `  ${String(hit.trackId).padEnd(12)} ${hit.trackName.slice(0, 42).padEnd(44)} ` +
        `${(hit.averageUserRating ?? 0).toFixed(2)}  ${hit.userRatingCount ?? 0} ratings`,
    );
  } catch (e) {
    console.log(`  ${t}: ${String(e).slice(0, 60)}`);
  }
}

const bag = [];
for (const a of apps) {
  for (const page of [1, 2, 3, 4]) {
    try {
      const r = await fetch(
        `https://itunes.apple.com/${country}/rss/customerreviews/page=${page}/id=${a.id}/sortby=mostrecent/json`,
        { headers: { "User-Agent": UA } },
      );
      for (const e of JSON.parse(await r.text()).feed?.entry ?? []) {
        const stars = Number(e["im:rating"]?.label ?? 5);
        if (stars > 2) continue;
        bag.push({
          app: a.name.split(":")[0].trim(),
          stars,
          title: e.title?.label ?? "",
          body: (e.content?.label ?? "").replace(/\s+/g, " ").trim(),
        });
      }
    } catch {}
  }
}

console.log(`\n  === ${bag.length} reviews at 1-2 stars ===\n`);
for (const r of bag.slice(0, 50)) {
  console.log(`  [${r.stars}* ${r.app}] ${r.title}`);
  console.log(`      ${r.body.slice(0, 220)}`);
}

const STOP = new Set(
  ("the a an and or but if is are was were be been it its this that they them their you your i me my we our to of in on for with at as so not no do does did have has had can could would should will just like get got very really much more most about than then there here what when who how why all any some out up down over after before also im ive dont doesnt cant wont isnt thats one two app apps ai chat make made makes making use used using time" +
    " even now back want because from many good only too new people anymore way old thing things say let never every please").split(" "),
);
const freq = new Map();
for (const r of bag) {
  for (const w of (r.title + " " + r.body).toLowerCase().match(/[a-z']{3,}/g) ?? []) {
    if (STOP.has(w)) continue;
    freq.set(w, (freq.get(w) ?? 0) + 1);
  }
}

console.log("\n  === what they are angry about (word counts) ===");
const top = [...freq].sort((a, b) => b[1] - a[1]).slice(0, 40);
console.log("  " + top.map(([w, n]) => `${w}:${n}`).join("  "));

console.log(`
  Now read the top ten reviews by hand. The counts tell you the theme; the
  sentences give you the words. Then verify each claim against the product
  before it goes on a frame — "no ads" means grepping package.json for an ad
  SDK, not assuming.
`);
