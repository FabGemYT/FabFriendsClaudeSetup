"""Status line renderer for Claude Code.

Reads the statusLine JSON payload on stdin and prints ONE line to stdout.

DESIGN RULE: print only what is actually present in the payload. Every field is
probed defensively, because the statusLine payload shape is not fully documented
and varies by version. A missing field is silently skipped, never guessed at and
never rendered as "None" or "0". This script must never crash: any unexpected
input degrades to a minimal line rather than an error, because a failing
statusline command shows up as noise on every single turn.

Verified present in the v2.1.220 binary and used here:
  session_id, transcript_path, model.display_name, workspace.current_dir,
  workspace.project_dir, cost.total_cost_usd, cost.total_duration_ms,
  exceeds_200k_tokens, output_style.name

Deliberately NOT used: context_window.tokens_used / .percent_used /
.auto_compact_at / .tokens_remaining. Those field names appear in some docs but
have ZERO occurrences in the shipped binary, so they do not exist. Context usage
is instead computed from the transcript, which is real data.

Set CLAUDE_STATUSLINE_DEBUG=1 to dump the raw payload to
~/.claude/statusline-payload.json so the true shape can be inspected later.
"""
import json
import os
import subprocess
import sys

# ANSI colors. Claude Code renders these in the status line.
DIM = "\033[2m"
RESET = "\033[0m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"


def dig(obj, *path):
    """Walk a nested dict, returning None the moment anything is missing."""
    for key in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def git_branch(cwd):
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0:
            branch = out.stdout.strip()
            return branch or None
    except Exception:
        pass
    return None


def git_dirty(cwd):
    # --no-optional-locks: a plain `git status` refreshes the index and holds
    # .git/index.lock while it does. During a heavy build it can run past the
    # 2 s timeout, gets killed, and leaves the lock behind, which then blocks
    # the next commit in that repo (store-app, 6-7 Nov 2026, five times).
    try:
        out = subprocess.run(
            ["git", "--no-optional-locks", "status", "--porcelain"],
            cwd=cwd, capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0 and out.stdout.strip():
            return True
    except Exception:
        pass
    return False


def context_tokens(transcript_path):
    """Recover current context size from the last usage record in the transcript.

    The statusLine payload carries no context-size field, so this reads the
    transcript JSONL backwards for the most recent assistant message that
    reported usage. Input + both cache counters is the real occupied context;
    output_tokens is excluded because it is not resident context.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
        size = os.path.getsize(transcript_path)
        # Only the tail matters, and transcripts get very large.
        with open(transcript_path, "rb") as fh:
            if size > 400_000:
                fh.seek(size - 400_000)
                fh.readline()  # discard the partial line
            lines = fh.read().decode("utf-8", errors="replace").splitlines()
    except Exception:
        return None

    for line in reversed(lines):
        line = line.strip()
        if not line or '"usage"' not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        usage = dig(rec, "message", "usage") or dig(rec, "usage")
        if not isinstance(usage, dict):
            continue
        total = 0
        for key in ("input_tokens", "cache_read_input_tokens",
                    "cache_creation_input_tokens"):
            val = usage.get(key)
            if isinstance(val, (int, float)):
                total += int(val)
        if total > 0:
            return total
    return None


def fmt_tokens(n):
    if n >= 1_000_000:
        return "{:.1f}M".format(n / 1_000_000)
    if n >= 1_000:
        return "{:.0f}k".format(n / 1_000)
    return str(n)


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        payload = {}

    if os.environ.get("CLAUDE_STATUSLINE_DEBUG") == "1":
        try:
            dump = os.path.join(os.path.expanduser("~"), ".claude",
                                "statusline-payload.json")
            with open(dump, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
        except Exception:
            pass

    parts = []

    # --- model ---------------------------------------------------------
    model = dig(payload, "model", "display_name") or dig(payload, "model", "id")
    if isinstance(model, str) and model:
        parts.append(MAGENTA + model + RESET)

    # --- directory + git branch ----------------------------------------
    cwd = dig(payload, "workspace", "current_dir") or payload.get("cwd")
    if isinstance(cwd, str) and cwd:
        parts.append(CYAN + os.path.basename(cwd.rstrip("/\\")) + RESET)
        branch = git_branch(cwd)
        if branch:
            mark = "*" if git_dirty(cwd) else ""
            color = YELLOW if mark else GREEN
            label = branch + mark
            # A branch that is not a fresh task branch is worth flagging: the
            # user's Law 4 is "one task = one fresh branch".
            if branch in ("main", "master"):
                label = "!" + label
                color = RED
            parts.append(color + label + RESET)

    # --- context usage --------------------------------------------------
    used = context_tokens(payload.get("transcript_path"))
    if used:
        # The token count is always trustworthy; the percentage depends on
        # knowing the model's real context window, which this payload does not
        # carry. Use the explicit override when one is set, otherwise assume the
        # 200k baseline -- and if that assumption produces a nonsense figure
        # (over 100%), drop the percentage and show only the count rather than
        # display something false.
        raw = os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW", "")
        window = int(raw) if raw.isdigit() and int(raw) > 0 else 200_000
        pct = int(round(100.0 * used / window))
        label = "ctx " + fmt_tokens(used)
        color = GREEN
        if pct <= 100:
            label += " " + str(pct) + "%"
            if pct >= 85:
                color = RED
            elif pct >= 60:
                color = YELLOW
        parts.append(color + label + RESET)
    elif payload.get("exceeds_200k_tokens") is True:
        parts.append(RED + "ctx >200k" + RESET)

    # --- session cost ---------------------------------------------------
    cost = dig(payload, "cost", "total_cost_usd")
    if isinstance(cost, (int, float)) and cost > 0:
        parts.append(DIM + "${:.2f}".format(cost) + RESET)

    # --- rate limits (probed, never assumed) ----------------------------
    # `rate_limit` and `five_hour` are present as literals in the binary but it
    # is unconfirmed whether they reach the statusLine payload. Rather than
    # invent a field path, render whatever actually arrives and skip otherwise.
    limits = payload.get("rate_limit") or payload.get("rate_limits")
    if isinstance(limits, dict):
        for key in ("five_hour", "fiveHour", "weekly", "seven_day"):
            entry = limits.get(key)
            pct = None
            if isinstance(entry, dict):
                for cand in ("used_pct", "percent_used", "utilization"):
                    val = entry.get(cand)
                    if isinstance(val, (int, float)):
                        pct = int(round(val if val > 1 else val * 100))
                        break
            elif isinstance(entry, (int, float)):
                pct = int(round(entry if entry > 1 else entry * 100))
            if pct is not None:
                short = "5h" if key in ("five_hour", "fiveHour") else "wk"
                color = RED if pct >= 85 else (YELLOW if pct >= 60 else DIM)
                parts.append(color + short + " " + str(pct) + "%" + RESET)

    # --- output style ---------------------------------------------------
    style = dig(payload, "output_style", "name")
    if isinstance(style, str) and style and style.lower() not in ("default", "null"):
        parts.append(DIM + style + RESET)

    if not parts:
        return

    # Windows consoles default to cp1252, which cannot encode the box-drawing
    # separator. Force UTF-8 when possible, and fall back to an ASCII pipe if
    # the stream still refuses it, so the line degrades instead of vanishing.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    try:
        sys.stdout.write((DIM + " │ " + RESET).join(parts))
    except UnicodeEncodeError:
        sys.stdout.write((DIM + " | " + RESET).join(parts))


try:
    main()
except Exception:
    # Never let the status line surface a traceback on every turn.
    pass
sys.exit(0)
