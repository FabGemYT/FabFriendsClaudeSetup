#!/usr/bin/env bash
# SessionStart hook, source=="compact" only: remind Claude that path-scoped
# rules don't reliably survive compaction. Silent no-op on every other
# SessionStart source (startup/resume/clear/fork). Always exits 0.
INPUT=$(cat)
DIR="$(dirname "${BASH_SOURCE[0]}")"
RESOLVER="$DIR/_resolve-python.sh"
[ -f "$RESOLVER" ] || exit 0
. "$RESOLVER"
[ -n "$INPUT" ] || exit 0
resolve_hook_python || exit 0
SCRIPT="$DIR/reinject-on-compact.py"
[ -f "$SCRIPT" ] || exit 0
printf '%s' "$INPUT" | "$HOOK_PY" $HOOK_PYARGS "$SCRIPT"
exit 0
