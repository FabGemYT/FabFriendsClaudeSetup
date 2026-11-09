"""SessionStart hook: remind Claude, right after a compaction, that path-scoped
rules (rules/*.md, e.g. rules/design.md) are not confirmed to survive it.

Verified against the current SessionStart contract: `source` is one of
"startup" | "resume" | "clear" | "compact" | "fork", and only SessionStart,
Setup, and SubagentStart can inject `additionalContext` -- PreCompact can only
block, and PostCompact has no decision control at all (side effects only), so
SessionStart with source=="compact" is the one hook that can actually do this.

CONTRACT: silent no-op (exit 0, no output) on every source except "compact".
Never blocks; this hook only ever informs.
"""
import sys
import json

try:
    payload = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)

if payload.get("source") != "compact":
    sys.exit(0)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": (
            "This session just compacted. Path-scoped rules (rules/*.md, e.g. "
            "rules/design.md) are not confirmed to survive compaction -- re-read "
            "the relevant one explicitly before continuing any matching work "
            "(e.g. UI/design files), rather than assuming its standards are "
            "still loaded."
        ),
    }
}))
sys.exit(0)
