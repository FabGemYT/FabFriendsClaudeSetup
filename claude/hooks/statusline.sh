#!/bin/bash
# statusLine command: renders the one-line status bar.
#
# Prints model, project dir, git branch (with a red "!" if you are sitting on
# main, per Law 4), context usage, and session cost. Real logic is in
# statusline.py so there is no fragile bash/JSON handling here.
#
# CONTRACT: whatever this prints on stdout becomes the status line. It must
# ALWAYS exit 0 and must never print an error — a noisy statusline command
# pollutes every single turn. Any failure degrades to an empty status line.
#
# Interpreter resolution is inlined rather than sourced from
# _resolve-python.sh so this file carries no cross-branch dependency. Order
# matters: the Windows `py -3` launcher is tried before bare `python` because
# `python` on PATH can resolve to a project virtualenv that lacks the stdlib
# build we expect.

INPUT=$(cat)

DIR="$(dirname "${BASH_SOURCE[0]}")"
SCRIPT="$DIR/statusline.py"
[ -f "$SCRIPT" ] || exit 0

PY=""
PYARGS=""
if [ -n "$CLAUDE_HOOK_PYTHON" ] && command -v "$CLAUDE_HOOK_PYTHON" >/dev/null 2>&1; then
  PY="$CLAUDE_HOOK_PYTHON"
elif command -v py >/dev/null 2>&1 && py -3 -c "" >/dev/null 2>&1; then
  PY="py"; PYARGS="-3"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  PY="python"
else
  exit 0
fi

printf '%s' "$INPUT" | "$PY" $PYARGS "$SCRIPT" 2>/dev/null
exit 0
