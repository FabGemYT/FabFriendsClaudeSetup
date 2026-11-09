#!/bin/bash
# Guard the MCP route, which every other blocking hook is blind to.
#
# CONTRACT: block = reason on stderr + exit 2. Clean exit 0 = no opinion.
#
# WHY THIS FILE EXISTS: the five command guards are all registered against the
# `Bash` matcher. Measured 2026-08-07 by replaying real payloads through every
# one of them:
#
#   mcp__claude_ai_Supabase__execute_sql  {"query":"DROP TABLE profiles;"}
#       -> passed all five untouched
#   the identical SQL through Bash
#       -> blocked
#
# `mcp__claude_ai_Supabase__*` is in settings.json `allow`, so the unguarded
# route was also the frictionless one. Same blind spot covered Vercel's
# deploy_to_vercel, and the publish/billing family (tiktok_publish,
# publish_website, confirm_billing_purchase) that any connected media or hosting
# service can expose.
#
# FAILS OPEN, unlike the four Bash guards. That difference is deliberate. A
# malformed Bash payload means a broken guard on a route that can do anything, so
# those fail closed. Here, failing closed would wedge every call from ten
# connected MCP servers on any single parse miss -- the "a guard that blocks daily
# work gets disabled" outcome the FOUNDATION names as the worst possible one. The
# analyser itself still fails closed internally on the dangerous tools it knows.

INPUT=$(cat)

# Nothing to inspect, or no way to inspect it: say nothing rather than wedge MCP.
[ -n "$INPUT" ] || exit 0

DIR="$(dirname "${BASH_SOURCE[0]}")"
RESOLVER="$DIR/_resolve-python.sh"
[ -f "$RESOLVER" ] || exit 0
# shellcheck source=/dev/null
. "$RESOLVER"

resolve_hook_python || exit 0

GUARD="$DIR/command-guard.py"
[ -f "$GUARD" ] || exit 0

ERR=$(mktemp 2>/dev/null || printf '%s' "${TMPDIR:-/tmp}/block-mcp-danger.$$")
printf '%s' "$INPUT" | "$HOOK_PY" $HOOK_PYARGS "$GUARD" mcp 2>"$ERR"
STATUS=$?
REASON=$(cat "$ERR" 2>/dev/null)
rm -f "$ERR"

if [ "$STATUS" -eq 2 ]; then
  printf '%s\n' "$REASON" >&2
  exit 2
fi
exit 0
