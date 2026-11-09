#!/bin/bash
# Block shell-level modification of the guard layer itself: ~/.claude/hooks/,
# settings.json, the ~/.claude root, and the home directory root (rm -rf ~).
#
# CONTRACT: block = reason on stderr + exit 2. Clean exit 0 = no opinion.
#
# WHY: one shell command (rm/mv/tee/sed -i/chmod/git rm/redirect) against the
# hooks directory or settings.json disables all six guardrails at once, and
# nothing stopped that before this guard. Edit/Write tool edits to the same
# paths are covered separately by "ask" permission rules in settings.json,
# which prompt the user; this guard closes the shell route so the two layers
# meet. Detection lives in command-guard.py (mode guard-tamper), shared with
# the other four command guards.
#
# FAILS CLOSED: missing resolver, empty payload, no interpreter, missing
# analyser, or any analyser error all BLOCK, so a broken guard can never
# silently stop guarding.

INPUT=$(cat)

block() { printf '%s
' "$1" >&2; exit 2; }

DIR="$(dirname "${BASH_SOURCE[0]}")"
RESOLVER="$DIR/_resolve-python.sh"
[ -f "$RESOLVER" ] || block "block-guard-tamper: _resolve-python.sh is missing so the command cannot be inspected; failing closed."
# shellcheck source=/dev/null
. "$RESOLVER"

[ -n "$INPUT" ] || block "block-guard-tamper: empty hook payload; failing closed."

resolve_hook_python || block "block-guard-tamper: no working Python 3 interpreter found so the command cannot be inspected; failing closed. Install Python 3, or set CLAUDE_HOOK_PYTHON to an absolute interpreter path."

GUARD="$DIR/command-guard.py"
[ -f "$GUARD" ] || block "block-guard-tamper: command-guard.py is missing so the command cannot be inspected; failing closed."

ERR=$(mktemp 2>/dev/null || printf '%s' "${TMPDIR:-/tmp}/block-guard-tamper.$$")
printf '%s' "$INPUT" | "$HOOK_PY" $HOOK_PYARGS "$GUARD" guard-tamper 2>"$ERR"
STATUS=$?
REASON=$(cat "$ERR" 2>/dev/null)
rm -f "$ERR"

if [ "$STATUS" -eq 0 ]; then
  exit 0
fi
if [ "$STATUS" -eq 2 ]; then
  printf '%s
' "$REASON" >&2
  exit 2
fi
block "block-guard-tamper: the command could not be inspected (${REASON:-analyser error $STATUS}); failing closed."
