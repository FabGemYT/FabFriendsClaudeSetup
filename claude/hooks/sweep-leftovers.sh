#!/bin/bash
# Close what Claude Code sessions leave running (wired on SessionStart and Stop, async).
#
# On Windows, when Claude stops a background command, a command times out, or a
# session closes, the programs inside the shell keep running: Git Bash tools
# always, native ones whenever a launcher in between has already exited
# (measured 2026-10-29; TOOLS.md "Machine hygiene"). This runs
# bin/claude-cleanup.ps1 -Force, which closes only what it can prove is a
# leftover and leaves everything still in use alone. Its tests are
# hooks/tests/test-sweep-leftovers.py.
#
# Wired with "async": true, so a reply or a session start never waits for it.
# At most one sweep per event per minute across all sessions, so ten open
# sessions do not sweep ten times.
#
# FAILS QUIET. Any problem here means no sweep this time, never a blocked or
# slowed session: always exit 0.

INPUT=""
[ -t 0 ] || INPUT=$(cat)
EVENT=$(printf '%s' "$INPUT" | grep -o '"hook_event_name"[[:space:]]*:[[:space:]]*"[A-Za-z]*"' | head -1 | sed 's/.*"\([A-Za-z]*\)"$/\1/')
[ -n "$EVENT" ] || EVENT=manual

STATE="$HOME/.claude/state"
mkdir -p "$STATE" 2>/dev/null
STAMP="$STATE/last-sweep-$EVENT"
NOW=$(date +%s)
LAST=$(stat -c %Y "$STAMP" 2>/dev/null || echo 0)
[ $((NOW - LAST)) -lt 60 ] && exit 0
touch "$STAMP" 2>/dev/null

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SWEEP="$DIR/../bin/claude-cleanup.ps1"
[ -f "$SWEEP" ] || SWEEP="$HOME/.claude/bin/claude-cleanup.ps1"
[ -f "$SWEEP" ] || exit 0
command -v powershell.exe >/dev/null 2>&1 || exit 0

powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
  -File "$(cygpath -w "$SWEEP")" -Force -Quiet -Trigger "$EVENT" >/dev/null 2>&1
exit 0
