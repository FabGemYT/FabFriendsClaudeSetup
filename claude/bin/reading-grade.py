#!/usr/bin/env python3
"""Reading grade of the words a customer actually reads: a page, a file, or text.

    py -3 ~/.claude/bin/reading-grade.py https://example.com/pricing
    py -3 ~/.claude/bin/reading-grade.py src/content/home.md
    py -3 ~/.claude/bin/reading-grade.py --max 7 --all page.html
    echo "Some copy." | py -3 ~/.claude/bin/reading-grade.py -

WHY A TOOL AND NOT AN EYEBALL: reading level degrades invisibly. Every edit that
adds a clause or a longer word moves it up a grade, and nobody notices until the
page reads like a datasheet. The goal (rules/the-goal.md) asks for grade 5 to 7
where it fits, so it gets measured, not guessed.

WHAT IS MEASURED: Flesch-Kincaid Grade Level, ported line for line from the
an online store check that gates its paid-traffic copy (scripts/verify-readability.ts,
Oct 2026), so the two give the same number on the same text:

    0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59

It is a proxy (short words in short sentences score well whether or not they
mean anything) and syllables are counted by the usual vowel-group heuristic, so
read it as a drift alarm, not a verdict. Passages under --min-words (default 20)
are listed but never judged: a four-word button carries no useful grade.

"WHERE POSSIBLE, NOT EVERYWHERE": spec tables, science, legal and technical
pages stay exact. Point this at the pages that sell (home, product, pricing,
offers, emails, captions), not at the terms of service.

Exit code: 0 when every judged passage and the whole text sit at or below --max,
1 when something reads above it, 2 on a usage or fetch error. Standard library
only, so it runs anywhere Python 3 does.
"""
import argparse
import html
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser

MAX_GRADE = 7.0
MIN_WORDS = 20


def syllables(word):
    """Vowel groups, minus a silent trailing e, minimum one. The usual heuristic,
    identical to the an online store check."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    trimmed = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    trimmed = re.sub(r"^y", "", trimmed)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", trimmed)))


def grade(text):
    clean = re.sub(r"\s+", " ", text).strip()
    sentences = max(1, len(re.findall(r"[.!?]+(?:\s|$)", clean)))
    words = [w for w in clean.split(" ") if re.search(r"[a-z]", w, re.I)]
    if not words:
        return {"fk": 0.0, "words": 0, "sentences": sentences}
    syl = sum(syllables(w) for w in words)
    fk = 0.39 * (len(words) / sentences) + 11.8 * (syl / len(words)) - 15.59
    return {"fk": fk, "words": len(words), "sentences": sentences}


class _Blocks(HTMLParser):
    """Visible text of a page, one passage per block element. Navigation,
    footers, scripts and styles are skipped: they are not what a buyer reads."""
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "template", "head"}
    BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote",
             "figcaption", "td", "th", "dd", "dt", "summary", "caption"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.stack = []
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.stack.append((tag, []))

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK and self.stack:
            # Close the innermost open block of this tag; a stray end tag is ignored.
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    t, parts = self.stack.pop(i)
                    text = re.sub(r"\s+", " ", "".join(parts)).strip()
                    if text:
                        self.out.append((t, text))
                    break

    def handle_data(self, data):
        if self.skip or not self.stack:
            return
        self.stack[-1][1].append(data)


def passages_from_html(raw):
    p = _Blocks()
    p.feed(raw)
    p.close()
    return [("<%s>" % t, x) for t, x in p.out]


def passages_from_markdown(raw):
    raw = re.sub(r"(?s)^---\n.*?\n---\n", "", raw)          # frontmatter
    raw = re.sub(r"(?s)```.*?```", "", raw)                  # code blocks
    out = []
    for n, block in enumerate(re.split(r"\n\s*\n", raw), 1):
        t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", block)       # images
        t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)      # links keep their text
        t = re.sub(r"<[^>]+>", " ", t)                        # inline html
        t = re.sub(r"(?m)^\s{0,3}(#{1,6}|>|[-*+]|\d+[.)])\s+", "", t)
        t = re.sub(r"[*_`|]", "", t)
        t = re.sub(r"\s+", " ", html.unescape(t)).strip()
        if t:
            out.append(("block %d" % n, t))
    return out


def load(source):
    if source == "-":
        return sys.stdin.read(), "text"
    if re.match(r"^https?://", source):
        req = urllib.request.Request(source, headers={"User-Agent": "reading-grade/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace"), "html"
    with open(source, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    if re.search(r"\.html?$", source, re.I):
        return raw, "html"
    if re.search(r"\.(md|mdx|markdown)$", source, re.I):
        return raw, "markdown"
    return raw, "html" if re.search(r"<(p|h1|div|body)\b", raw, re.I) else "markdown"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Flesch-Kincaid grade of what customers read.")
    ap.add_argument("source", help="a URL, a .html/.md/.txt file, or - for stdin")
    ap.add_argument("--max", type=float, default=MAX_GRADE, help="highest acceptable grade (default 7)")
    ap.add_argument("--min-words", type=int, default=MIN_WORDS, help="shorter passages are listed, not judged (default 20)")
    ap.add_argument("--all", action="store_true", help="print every judged passage, not only the ones above --max")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args(argv)
    try:
        raw, kind = load(a.source)
    except Exception as e:
        print("reading-grade: could not read %s: %s" % (a.source, e), file=sys.stderr)
        return 2
    items = passages_from_html(raw) if kind == "html" else passages_from_markdown(raw)
    if kind == "text":
        items = [("text", re.sub(r"\s+", " ", raw).strip())]
    judged, short, over = [], 0, []
    for where, text in items:
        g = grade(text)
        if g["words"] < a.min_words:
            short += 1
            continue
        row = dict(where=where, text=text, **g)
        judged.append(row)
        if g["fk"] > a.max:
            over.append(row)
    whole = grade(" ".join(t for _, t in items))
    if a.json:
        print(json.dumps({"source": a.source, "max": a.max, "whole": whole, "judged": len(judged),
                          "short": short, "over": [{k: r[k] for k in ("where", "fk", "words", "sentences", "text")} for r in over]},
                         indent=2))
    else:
        print("Flesch-Kincaid grade, %s\n" % a.source)
        for r in (judged if a.all else over):
            flag = "OVER" if r["fk"] > a.max else "ok  "
            print("  %s grade %4.1f  %-10s %s" % (flag, r["fk"], r["where"], r["text"][:110]))
            if r["fk"] > a.max:
                print("       %d words over %d sentences (%.1f per sentence)"
                      % (r["words"], r["sentences"], r["words"] / r["sentences"]))
        print("\n  Whole text: grade %.1f over %d words, %d sentences" % (whole["fk"], whole["words"], whole["sentences"]))
        print("  Judged %d passages; %d shorter than %d words were listed, not judged." % (len(judged), short, a.min_words))
    failed = len(over) + (1 if whole["fk"] > a.max and whole["words"] >= a.min_words else 0)
    if not a.json:
        print("\n%s" % ("PASS: everything judged reads at or below grade %g." % a.max if not failed
                        else "ABOVE GRADE %g: %d passage(s)%s." % (a.max, len(over), " and the whole text" if whole["fk"] > a.max else "")))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
