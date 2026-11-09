"""Harness review scanner: what actually happened in recent sessions, measured.

Reads every transcript under ~/.claude/projects touched since the last review and
prints the numbers the review needs. Read-only, no network, no model calls.

    py -3 review.py [--since YYYY-MM-DD] [--mark]

--mark records today's date and the installed Claude Code version in
~/.claude/state/harness-review.json so the next run knows where to start.
"""
import argparse
import collections
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

HOME = os.path.expanduser("~")
PROJECTS = os.path.join(HOME, ".claude", "projects")
STATE = os.path.join(HOME, ".claude", "state", "harness-review.json")
ANSWERS = os.path.join(HOME, ".claude", "state", "elicitation-answers.log")

DENIAL_RE = re.compile(r"denied by the Claude Code auto mode classifier\. Reason: (\[[^\]]*\])")
TS_RE = re.compile(r'"timestamp":"(\d{4}-\d\d-\d\d)T(\d\d:\d\d)')
VER_RE = re.compile(r'"version":"(\d+\.\d+\.\d+)"')


def installed_version():
    try:
        out = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=60, shell=True).stdout
        m = re.search(r"\d+\.\d+\.\d+", out)
        return m.group(0) if m else "?"
    except Exception:
        return "?"


def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return {}


def scan(path, since):
    """One transcript. Returns counters for lines dated on or after `since`."""
    r = collections.Counter()
    denials = collections.Counter()
    versions = collections.Counter()
    max_ctx = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = TS_RE.search(line)
            if not m or m.group(1) < since:
                continue
            r["lines"] += 1
            v = VER_RE.search(line)
            if v:
                versions[v.group(1)] += 1
            if "compact_boundary" in line or '"isCompactSummary":true' in line:
                r["compactions"] += 1
            if "[Usage limit reached" in line:
                r["usage_limit_stops"] += 1
            if "cannot determine the safety" in line or "could not evaluate this action" in line:
                r["classifier_no_verdict"] += 1
            d = DENIAL_RE.search(line)
            if d:
                denials[d.group(1)] += 1
            if '"type":"assistant"' in line and '"usage"' in line:
                try:
                    u = json.loads(line)["message"]["usage"]
                    ctx = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                           + u.get("cache_creation_input_tokens", 0))
                    r["turns"] += 1
                    r["context_tokens_sent"] += ctx
                    r["output_tokens"] += u.get("output_tokens", 0)
                    max_ctx = max(max_ctx, ctx)
                except Exception:
                    pass
    return r, denials, versions, max_ctx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since")
    ap.add_argument("--mark", action="store_true")
    a = ap.parse_args()
    state = load_state()
    since = a.since or state.get("date") or (dt.date.today() - dt.timedelta(days=21)).isoformat()
    ver = installed_version()
    print("harness review | installed %s | last reviewed %s on %s | window from %s" % (
        ver, state.get("version", "never"), state.get("date", "never"), since))

    cutoff = dt.datetime.fromisoformat(since).timestamp()
    files = [p for p in glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")) if os.path.getmtime(p) >= cutoff]
    print("transcripts touched in window: %d" % len(files))

    total = collections.Counter()
    denials = collections.Counter()
    versions = collections.Counter()
    rows = []
    for p in sorted(files, key=os.path.getsize, reverse=True):
        r, d, v, mx = scan(p, since)
        if not r["lines"]:
            continue
        total.update(r)
        denials.update(d)
        versions.update(v)
        rows.append((os.path.basename(os.path.dirname(p)), os.path.getsize(p) // 1048576, mx,
                     r["turns"], r["compactions"], r["usage_limit_stops"]))

    print("\nper session (project, size MB, largest context, turns, compactions, limit stops):")
    for row in rows[:12]:
        print("  %-36s %5d MB  ctx %9s  turns %5d  compactions %3d  limit stops %d" % (
            row[0], row[1], "{:,}".format(row[2]), row[3], row[4], row[5]))
    print("\ntotals: turns %s, context tokens sent %s, output tokens %s" % (
        "{:,}".format(total["turns"]), "{:,}".format(total["context_tokens_sent"]),
        "{:,}".format(total["output_tokens"])))
    print("usage-limit stops: %d | compactions: %d | classifier gave no verdict: %d" % (
        total["usage_limit_stops"], total["compactions"], total["classifier_no_verdict"]))
    print("classifier denials: %s" % (dict(denials) or "none"))
    print("builds seen: %s" % dict(versions.most_common(5)))

    n_answers = 0
    try:
        with open(ANSWERS, encoding="utf-8") as fh:
            n_answers = sum(1 for l in fh if l[:10] >= since)
    except Exception:
        pass
    print("MCP forms answered by the harness (Supabase SQL confirmations): %d" % n_answers)

    if a.mark:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump({"date": dt.date.today().isoformat(), "version": ver},
                  open(STATE, "w", encoding="utf-8"))
        print("marked: next review starts from %s / %s" % (dt.date.today().isoformat(), ver))
    return 0


if __name__ == "__main__":
    sys.exit(main())
