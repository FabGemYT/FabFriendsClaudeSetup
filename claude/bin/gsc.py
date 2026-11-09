#!/usr/bin/env python3
"""Google Search Console, for every the owner site, from any session.

WHY A SERVICE ACCOUNT AND NOT `gcloud auth application-default login`:
ADC refresh tokens issued by an OAuth consent screen still in "Testing" expire
after exactly 7 days. That is silent breakage -- the credential simply stops
working with no warning, which is the failure mode the FOUNDATION forbids. A
service-account key does not expire, so this keeps working untouched.

THE ONE-TIME COST of that choice: the service account is not automatically an
owner of anything, so its email must be added as a user on each Search Console
property. Run `gsc.py properties` and it will tell you exactly which are missing.

USAGE
    py -3 ~/.claude/bin/gsc.py properties
    py -3 ~/.claude/bin/gsc.py top          <site> [days] [rows]
    py -3 ~/.claude/bin/gsc.py queries      <site> [days] [rows]
    py -3 ~/.claude/bin/gsc.py pages        <site> [days] [rows]
    py -3 ~/.claude/bin/gsc.py totals       <site> [days]
    py -3 ~/.claude/bin/gsc.py sitemaps     <site>
    py -3 ~/.claude/bin/gsc.py submit       <site> [sitemapUrl]
    py -3 ~/.claude/bin/gsc.py inspect      <site> <url>
    py -3 ~/.claude/bin/gsc.py coverage     <site> [--all] [--limit N]

<site> accepts a bare domain (example.com) and resolves it to whichever form the
property is registered as, so callers never have to remember whether a property
is `sc-domain:` or `https://`.

COVERAGE answers "how much of the site does Google actually have, and which page
types does it refuse", which Search Console will not say through its API: the
Sitemaps API's per-sitemap `indexed` count is deprecated and returns 0, and the
Page Indexing report is web-only. So it inspects every page in the site's sitemaps
with the URL Inspection API and groups the answers by page type (the first path
segment of the page's default-language address). By default one address per page,
the default language; --all adds every language version, reported per language.

The quota is 2,000 inspections per property per day, so a snapshot is saved as it
goes, under ~/.claude/state/gsc-coverage/<domain>/, and a run that stops (quota,
network, Ctrl+C) resumes on the next run within two days. Once complete, a rerun
the same day only reprints the report, and every report compares itself with the
previous complete snapshot of the same scope. The API is free; nothing is billed.

Credential: $GSC_SERVICE_ACCOUNT_PATH, exported into every session by
hooks/load-env.sh. Nothing to pass, nothing to log in to.
"""
import collections
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/webmasters"]
API = "https://searchconsole.googleapis.com/webmasters/v3"
INSPECT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
STATE = os.path.expanduser("~/.claude/state/gsc-coverage")


def creds():
    path = os.environ.get("GSC_SERVICE_ACCOUNT_PATH", "")
    if not path:
        path = os.path.expanduser("~/.claude/secrets/gsc-service-account.json")
    path = os.path.expanduser(path.strip('"'))
    if not os.path.exists(path):
        sys.exit("No GSC credential at %s. See rules/secrets-map.md." % path)
    c = service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
    c.refresh(Request())
    return c


def call(url, method="GET", body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read()).get("error", {}).get("message", "")
        except Exception:
            pass
        raise SystemExit("HTTP %s: %s" % (e.code, detail or e.reason))


def sites(token):
    return [s["siteUrl"] for s in call(API + "/sites", token=token).get("siteEntry", [])]


def vercel_domains():
    """Every production domain Vercel is serving, as the source of truth for
    which sites SHOULD be in Search Console.

    Deliberately not a hardcoded list: the moment a sixth site ships, a static
    list stops being true and the new domain never gets reported as missing its
    one-time grant. Returns [] on any failure so the caller can fall back."""
    import re
    import subprocess
    try:
        p = subprocess.run(["vercel", "project", "ls"], capture_output=True,
                           text=True, timeout=90)
    except Exception:
        return []
    out = []
    for line in (p.stdout or "").splitlines():
        m = re.search(r"https://([a-z0-9.-]+\.[a-z]{2,})", line)
        if not m:
            continue
        host = m.group(1)
        if host.endswith(".vercel.app"):     # preview hosts are not GSC properties
            continue
        out.append(host)
    return sorted(set(out))


def resolve(token, name):
    """Accept a bare domain and return the property id actually registered."""
    have = sites(token)
    if name in have:
        return name
    bare = name.replace("https://", "").replace("http://", "").rstrip("/")
    for cand in ("sc-domain:" + bare, "https://%s/" % bare, "https://www.%s/" % bare):
        if cand in have:
            return cand
    for s in have:
        if bare in s:
            return s
    sys.exit("'%s' is not a property this service account can see.\nIt can see: %s"
             % (name, ", ".join(have) or "(nothing yet)"))


def query(token, site, dims, days, rows):
    end = date.today() - timedelta(days=2)      # GSC data lags ~2 days
    start = end - timedelta(days=days)
    body = {"startDate": start.isoformat(), "endDate": end.isoformat(),
            "rowLimit": rows}
    if dims:
        body["dimensions"] = dims
    url = "%s/sites/%s/searchAnalytics/query" % (API, urllib.parse.quote(site, safe=""))
    return call(url, "POST", body, token), start, end


def show(rows, label):
    if not rows:
        print("   (no data)")
        return
    print("   %-52s %8s %8s %7s %6s" % (label, "clicks", "impr", "CTR", "pos"))
    for r in rows:
        k = (r.get("keys") or ["(total)"])[0]
        print("   %-52s %8d %8d %6.1f%% %6.1f"
              % (k[:52], r.get("clicks", 0), r.get("impressions", 0),
                 100 * r.get("ctr", 0), r.get("position", 0)))


def norm(u):
    """One spelling per URL: lower-case host and "/" for an empty path, so a sitemap's
    "https://x.com" and its hreflang "https://x.com/" compare as the one URL they are."""
    p = urllib.parse.urlsplit(u.strip())
    return "%s://%s%s%s" % (p.scheme, p.netloc.lower(), p.path or "/",
                            "?" + p.query if p.query else "")


def domain_of(site):
    return (site[len("sc-domain:"):] if site.startswith("sc-domain:")
            else urllib.parse.urlsplit(site).netloc)


def sitemap_pages(token, site):
    """Every page in the property's registered sitemaps, one level of sitemap index
    followed, as [(loc, lastmod, {hreflang: href})]."""
    import gzip
    import xml.etree.ElementTree as ET
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
          "x": "http://www.w3.org/1999/xhtml"}
    listed = call("%s/sites/%s/sitemaps" % (API, urllib.parse.quote(site, safe="")),
                  token=token).get("sitemap", [])
    feeds = [s["path"] for s in listed if s.get("path")] or [
        "https://%s/sitemap.xml" % domain_of(site)]
    depth = dict.fromkeys(feeds, 0)
    queue, out, seen = list(feeds), [], set()
    while queue:
        feed = queue.pop(0)
        try:
            req = urllib.request.Request(feed, headers={"User-Agent": "gsc.py coverage"})
            with urllib.request.urlopen(req, timeout=120) as r:
                body = r.read()
        except Exception as e:      # one stale registration must not sink the rest
            print("   skipped %s: %s" % (feed, e))
            continue
        if body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
        root = ET.fromstring(body)
        if root.tag.endswith("sitemapindex"):
            for loc in root.findall("sm:sitemap/sm:loc", ns):
                child = loc.text.strip()
                if depth[feed] < 1 and child not in depth:
                    depth[child] = depth[feed] + 1
                    queue.append(child)
            continue
        for u in root.findall("sm:url", ns):
            loc = u.findtext("sm:loc", "", ns).strip()
            if not loc or loc in seen:
                continue
            seen.add(loc)
            alts = {a.get("hreflang"): a.get("href") for a in u.findall("x:link", ns)
                    if a.get("rel") == "alternate" and a.get("hreflang")}
            out.append((loc, u.findtext("sm:lastmod", "", ns).strip(), alts))
    return out


def when(s):
    """A sitemap or API timestamp as an aware datetime, or None."""
    try:
        d = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def coverage(token, site, argv):
    everything = "--all" in argv
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    scope = "all" if everything else "primary"

    # One address per page unless --all: the default-language one, which is the
    # hreflang x-default where the site declares languages and the page itself where
    # it does not. The type is read from that address, so /de/product/x is a product.
    pages = []
    for loc, lastmod, alts in sitemap_pages(token, site):
        primary = alts.get("x-default") or loc
        if not everything and norm(primary) != norm(loc):
            continue
        lang = next((h for h, href in alts.items()
                     if h != "x-default" and norm(href) == norm(loc)), "-")
        kind = urllib.parse.urlsplit(primary).path.strip("/").split("/")[0] or "home"
        pages.append((loc, lastmod, lang, kind))
    if not pages:
        sys.exit("No pages found in the sitemaps of %s." % site)

    folder = os.path.join(STATE, domain_of(site))
    os.makedirs(folder, exist_ok=True)
    today = date.today()
    mine = sorted(f for f in os.listdir(folder) if f.endswith("-%s.json" % scope))
    path = snap = None
    if mine:
        last = json.load(open(os.path.join(folder, mine[-1]), encoding="utf-8"))
        age = (today - date.fromisoformat(mine[-1][:10])).days
        unfinished = len(last["results"]) < last["total"]
        if (unfinished and age <= 2) or (not unfinished and age == 0):
            path, snap = os.path.join(folder, mine[-1]), last    # resume, or report only
    if snap is None:
        path = os.path.join(folder, "%s-%s.json" % (today.isoformat(), scope))
        snap = {"site": site, "scope": scope, "started": today.isoformat(),
                "total": len(pages), "results": {}}

    def save():
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=1)
        os.replace(path + ".tmp", path)

    todo = [] if len(snap["results"]) >= snap["total"] else [
        p for p in pages if p[0] not in snap["results"]]
    if limit is not None:
        todo = todo[:limit]
    print("%s: %d pages in scope (%s), %d already inspected, %d to inspect now"
          % (site, len(pages), scope, len(snap["results"]), len(todo)), flush=True)
    fields = ("verdict", "coverageState", "indexingState", "robotsTxtState",
              "pageFetchState", "lastCrawlTime", "googleCanonical", "userCanonical")

    # One inspection takes several seconds, so a few run at once. Their starts pass
    # through one gate at least 0.11s apart, which keeps the run under Google's 600
    # a minute however fast the answers come back.
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    gate, last, tok = threading.Lock(), [0.0], [token, time.time()]

    def inspect(loc):
        with gate:
            if time.time() - tok[1] > 2700:            # a token lasts an hour
                tok[:] = [creds().token, time.time()]
            time.sleep(max(0.0, 0.11 - (time.time() - last[0])))
            last[0] = time.time()
        for attempt in (1, 2):
            try:
                return call(INSPECT, "POST", {"inspectionUrl": loc, "siteUrl": site}, tok[0])
            except (SystemExit, OSError) as e:          # call() reports HTTP errors as SystemExit
                if attempt == 2 or "429" in str(e) or "quota" in str(e).lower():
                    raise
                time.sleep(5)

    pool = ThreadPoolExecutor(max_workers=6)
    jobs = {pool.submit(inspect, p[0]): p for p in todo}
    try:
        for i, job in enumerate(as_completed(jobs), 1):
            loc, lastmod, lang, kind = jobs[job]
            idx = job.result().get("inspectionResult", {}).get("indexStatusResult", {})
            rec = {k: idx.get(k) for k in fields}
            rec.update(lang=lang, type=kind, lastmod=lastmod,
                       at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            snap["results"][loc] = rec
            if i % 25 == 0:
                save()
                print("   %d/%d" % (i, len(todo)), flush=True)
    except (SystemExit, OSError, KeyboardInterrupt) as e:
        pool.shutdown(wait=False, cancel_futures=True)
        save()
        print("\nStopped at %d of %d pages: %s\nSaved to %s\nRun the same command again to "
              "resume; the daily quota resets at midnight Pacific time."
              % (len(snap["results"]), snap["total"], str(e) or "interrupted", path))
        sys.exit(1)
    pool.shutdown()
    save()
    report(snap, previous(folder, scope, path))
    print("\n   snapshot: %s" % path)


def previous(folder, scope, current):
    """The newest COMPLETE snapshot of the same scope from an earlier day."""
    for f in sorted(os.listdir(folder), reverse=True):
        if f.endswith("-%s.json" % scope) and f < os.path.basename(current):
            s = json.load(open(os.path.join(folder, f), encoding="utf-8"))
            if len(s["results"]) >= s["total"]:
                return s
    return None


def report(snap, prev):
    rows = list(snap["results"].values())
    if len(rows) < snap["total"]:
        print("\nPARTIAL: %d of %d pages inspected so far." % (len(rows), snap["total"]))

    def table(key, title):
        groups = collections.defaultdict(list)
        for r in rows:
            groups[r[key]].append(r)
        print("\n   %-24s %6s %8s        %s" % (title, "pages", "indexed", "the rest, and why"))
        for name, rs in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            ok = sum(r["verdict"] == "PASS" for r in rs)
            why = collections.Counter(r["coverageState"] or "?" for r in rs if r["verdict"] != "PASS")
            print("   %-24s %6d %8d %5.0f%%  %s" % (
                name[:24], len(rs), ok, 100.0 * ok / len(rs),
                "; ".join("%d %s" % (c, s) for s, c in why.most_common(3))))

    table("type", "page type")
    if snap["scope"] == "all":
        table("lang", "language")
    ok = sum(r["verdict"] == "PASS" for r in rows)
    print("\n   TOTAL %d pages, %d indexed (%.0f%%)" % (len(rows), ok, 100.0 * ok / max(1, len(rows))))
    for s, c in collections.Counter(r["coverageState"] or "?" for r in rows).most_common():
        print("      %5d  %s" % (c, s))

    # When Google last fetched each page, and whether it has changed since: the
    # sitemap's lastmod newer than the last crawl means Google holds an old copy.
    now = datetime.now(timezone.utc)
    ages, behind = [], 0
    for r in rows:
        crawled, mod = when(r.get("lastCrawlTime")), when(r.get("lastmod"))
        ages.append((now - crawled).days if crawled else None)
        behind += bool(mod and (crawled is None or mod > crawled))
    known = [a for a in ages if a is not None]
    print("\n   last crawled: never %d, within 30 days %d, 30-90 days %d, over 90 days %d"
          % (len(ages) - len(known), sum(a <= 30 for a in known),
             sum(30 < a <= 90 for a in known), sum(a > 90 for a in known)))
    print("   changed since Google last crawled them: %d" % behind)

    odd = [(u, r["googleCanonical"]) for u, r in snap["results"].items()
           if r.get("googleCanonical") and norm(r["googleCanonical"]) != norm(u)]
    if odd:
        print("\n   Google picked a different canonical for %d:" % len(odd))
        for u, g in odd[:8]:
            print("      %s  ->  %s" % (u, g))

    if prev:
        def indexed(s):
            c = collections.Counter()
            for r in s["results"].values():
                c[r["type"]] += r["verdict"] == "PASS"
            return c
        a, b = indexed(prev), indexed(snap)
        print("\n   indexed, %s -> %s:" % (prev["started"], snap["started"]))
        for k in sorted(set(a) | set(b), key=lambda k: (-b[k], k)):
            print("      %-24s %5d -> %5d  (%+d)" % (k[:24], a[k], b[k], b[k] - a[k]))
        print("      %-24s %5d -> %5d  (%+d)" % ("TOTAL", sum(a.values()), sum(b.values()),
                                               sum(b.values()) - sum(a.values())))


def main():
    argv = sys.argv[1:]
    if not argv:
        sys.exit(__doc__)
    cmd = argv[0]
    token = creds().token

    if cmd == "properties":
        have = sites(token)
        print("Properties this service account can read:")
        for s in have:
            print("   %s" % s)
        if not have:
            print("   (none yet)")
        # Discover the expected domains from Vercel rather than a hardcoded list.
        # A hardcoded list silently stops being true the moment a sixth site
        # ships: the new domain would simply not appear anywhere, so nobody would
        # learn it still needs its one-time grant. Falling back to the known five
        # keeps this useful when the vercel CLI is missing or not logged in.
        expected = vercel_domains() or [
            "example.com", "example.com", "example.com",
            "example.com", "example.com"]
        missing = [d for d in expected
                   if not any(d in s for s in have)]
        if missing:
            print("\nNOT YET SHARED WITH THE SERVICE ACCOUNT:")
            for d in missing:
                print("   %s" % d)
            print("\nFor each one: Search Console -> that property -> Settings ->")
            print("Users and permissions -> Add user ->")
            print("   %s" % os.environ.get("GSC_SERVICE_ACCOUNT_EMAIL", "(see .env.local)"))
            print("   permission: Full  (Restricted also works for read-only use)")
        return

    if cmd in ("top", "queries", "pages", "totals", "sitemaps", "submit", "inspect", "coverage"):
        if len(argv) < 2:
            sys.exit("usage: gsc.py %s <site> ..." % cmd)
        site = resolve(token, argv[1])

        if cmd == "coverage":
            coverage(token, site, argv[2:])
            return

        if cmd == "sitemaps":
            url = "%s/sites/%s/sitemaps" % (API, urllib.parse.quote(site, safe=""))
            for s in call(url, token=token).get("sitemap", []):
                print("   %-58s submitted=%s errors=%s warnings=%s"
                      % (s.get("path"), (s.get("lastSubmitted") or "")[:10],
                         s.get("errors", 0), s.get("warnings", 0)))
            return

        if cmd == "submit":
            # Re-submitting an already-known sitemap is how you tell Google the
            # contents changed. It is a PUT with an empty body against the
            # sitemap's own path; there is no separate "ping" that works any
            # more, and the old /ping endpoint was retired.
            feed = argv[2] if len(argv) > 2 else "%s/sitemap.xml" % (
                site[len("sc-domain:"):] if site.startswith("sc-domain:") else site.rstrip("/")
            )
            if not feed.startswith("http"):
                feed = "https://" + feed.lstrip("/")
            url = "%s/sites/%s/sitemaps/%s" % (
                API, urllib.parse.quote(site, safe=""), urllib.parse.quote(feed, safe=""),
            )
            call(url, "PUT", None, token)
            print("   submitted %s" % feed)
            return

        if cmd == "inspect":
            if len(argv) < 3:
                sys.exit("usage: gsc.py inspect <site> <url>")
            body = {"inspectionUrl": argv[2], "siteUrl": site}
            res = call(INSPECT, "POST", body, token).get("inspectionResult", {})
            idx = res.get("indexStatusResult", {})
            print("   verdict        :", idx.get("verdict"))
            print("   coverage       :", idx.get("coverageState"))
            print("   last crawl     :", (idx.get("lastCrawlTime") or "")[:19])
            print("   canonical      :", idx.get("googleCanonical"))
            print("   robots         :", idx.get("robotsTxtState"))
            return

        days = int(argv[2]) if len(argv) > 2 else 28
        rows = int(argv[3]) if len(argv) > 3 else 20
        dims = {"top": ["query"], "queries": ["query"], "pages": ["page"],
                "totals": []}[cmd]
        data, start, end = query(token, site, dims, days, rows)
        print("%s  %s -> %s" % (site, start, end))
        show(data.get("rows", []), {"pages": "page"}.get(cmd, "query"))
        return

    sys.exit(__doc__)


main()
