#!/bin/bash
# Block merging a pull request (the user merges in the GitHub UI).
#
# CONTRACT: block = reason on stderr + exit 2. Clean exit 0 = no opinion.
#
# This is a thin wrapper. All detection lives in command-guard.py, shared by the
# four command guards, because the previous per-hook bash pattern-matching lost
# to six confirmed evasions (quoted arguments, binary prefixes like npx/env/VAR=,
# alternate flag spellings, other tools such as `gh api`, interpreters like
# `bash -c`, and destinations that only resolve at runtime). The Python analyser
# tokenises properly and resolves the real binary instead of matching text.
#
# FAILS CLOSED: missing resolver, empty payload, no interpreter, missing
# analyser, or any analyser error all BLOCK, so a broken guard can never
# silently stop guarding.

INPUT=$(cat)

block() { printf '%s
' "$1" >&2; exit 2; }

DIR="$(dirname "${BASH_SOURCE[0]}")"
RESOLVER="$DIR/_resolve-python.sh"
[ -f "$RESOLVER" ] || block "block-pr-merge: _resolve-python.sh is missing so the command cannot be inspected; failing closed."
# shellcheck source=/dev/null
. "$RESOLVER"

[ -n "$INPUT" ] || block "block-pr-merge: empty hook payload; failing closed."

resolve_hook_python || block "block-pr-merge: no working Python 3 interpreter found so the command cannot be inspected; failing closed. Install Python 3, or set CLAUDE_HOOK_PYTHON to an absolute interpreter path."

GUARD="$DIR/command-guard.py"
[ -f "$GUARD" ] || block "block-pr-merge: command-guard.py is missing so the command cannot be inspected; failing closed."

ERR=$(mktemp 2>/dev/null || printf '%s' "${TMPDIR:-/tmp}/block-pr-merge.$$")
printf '%s' "$INPUT" | "$HOOK_PY" $HOOK_PYARGS "$GUARD" pr-merge 2>"$ERR"
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
block "block-pr-merge: the command could not be inspected (${REASON:-analyser error $STATUS}); failing closed."
