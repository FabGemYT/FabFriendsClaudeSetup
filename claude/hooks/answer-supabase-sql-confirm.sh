#!/bin/bash
# Answer Supabase's "this SQL includes destructive operations" form the way the
# owner decided destructive SQL is handled on the owner's own projects (FOUNDATION,
# "Supabase specifically", 2026-08-07/08): the statement runs, and the note in
# chat comes from block-mcp-danger.sh on the same call.
#
# CONTRACT (Elicitation hook): print a hookSpecificOutput JSON to answer the
# form; print NOTHING to leave it to the dialog. Exit 0 always. Exit 2 would
# decline the request, which this hook never does.
#
# FAILS TOWARDS THE DIALOG. Any problem here (no Python, bad payload, unknown
# form) means the user sees the normal Accept / Decline prompt, exactly as if
# this hook did not exist. The decision itself lives in elicitation-answer.py so
# the test suite can replay payloads through the real logic.

INPUT=$(cat)
[ -n "$INPUT" ] || exit 0

DIR="$(dirname "${BASH_SOURCE[0]}")"
RESOLVER="$DIR/_resolve-python.sh"
[ -f "$RESOLVER" ] || RESOLVER="$HOME/.claude/hooks/_resolve-python.sh"
[ -f "$RESOLVER" ] || exit 0
# shellcheck source=/dev/null
. "$RESOLVER"
resolve_hook_python || exit 0

ANSWER="$DIR/elicitation-answer.py"
[ -f "$ANSWER" ] || exit 0

printf '%s' "$INPUT" | "$HOOK_PY" $HOOK_PYARGS "$ANSWER" 2>/dev/null
exit 0
