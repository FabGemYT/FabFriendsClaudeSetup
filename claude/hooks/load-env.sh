#!/bin/sh
# SessionStart hook: auto-load the wired account-level credentials so they are present
# in every Bash call, in every project, without the agent hunting the disk or re-asking.
# Reads ~/.claude/.env.local (gitignored) and exports each KEY=VALUE into the session
# environment via CLAUDE_ENV_FILE. No secret VALUES live in this script; they stay only
# in the gitignored .env.local.
#
# FAILS OPEN. If anything is missing or unreadable it exits 0 and changes nothing (the
# agent just falls back to asking, the old behaviour). This is the opposite of the
# block-*.sh guardrails, which fail closed. A credential loader that wedges a session is
# far worse than one that quietly does nothing -- which is exactly what happened on
# 2026-08-16 and is the reason for the rewrite below.
#
# ---------------------------------------------------------------------------
# WHY THIS IS IDEMPOTENT, ATOMIC AND SELF-HEALING (rewritten 2026-08-16)
# ---------------------------------------------------------------------------
# The previous version appended with `>>` and never truncated, one `printf` PER
# LINE. That is three separate defects, and together they killed a live session:
#
#   1. SessionStart fires REPEATEDLY in one session -- on startup, resume, clear
#      AND every compaction (all four source values confirmed in the 2.1.224
#      binary; hooks/reinject-on-compact.sh exists precisely because compaction
#      fires it). Every firing re-appended all 16 exports.
#   2. 16 exports x 7 firings = 112 lines. Measured, not estimated.
#   3. Sixteen separate open/write/close calls per firing, with five or more
#      concurrent sessions, eventually tore one line in half:
#
#          export GSC_GCP_PROJECT='fab
#
# Claude Code inlines this file into EVERY `bash -c` invocation, so an
# unterminated quote means every command in that session dies while bash is still
# PARSING -- `echo ok` fails exactly like `git status`. Reproduced verbatim:
#
#     bash: -c: line 112: unexpected EOF while looking for matching `''
#
# A restart did not help, because the file is on disk and gets reused. The line
# number never changed, because the file was static. `.env.local` looked
# blameless, because it was: the damage is entirely downstream of it.
#
# So this version:
#   * writes the whole block in ONE printf, so a torn line is not possible;
#   * wraps it in markers and returns early if it is already there, so seven
#     firings produce exactly what one firing produces;
#   * VALIDATES the file and rebuilds it if it no longer parses, so a session
#     that is already wedged heals itself at the next SessionStart instead of
#     needing a shell it no longer has.
# ---------------------------------------------------------------------------

[ -n "$CLAUDE_ENV_FILE" ] || exit 0
ENVFILE="$HOME/.claude/.env.local"
[ -f "$ENVFILE" ] || exit 0

BEGIN_MARK='# >>> claude-env begin (managed by hooks/load-env.sh -- do not edit inside)'
END_MARK='# <<< claude-env end'

# --- is our block already present AND is the file still parseable? -----------
# Both halves matter. Present-and-valid is the normal repeat-firing case and
# must be a no-op. Present-but-invalid is the wedged session, and must be fixed.
NEEDS_WRITE=1
if [ -f "$CLAUDE_ENV_FILE" ] && grep -qF "$BEGIN_MARK" "$CLAUDE_ENV_FILE" 2>/dev/null; then
  # `sh -n` parses without executing. If the shell cannot even validate, treat
  # that as "cannot prove it is broken" and leave the file alone: rewriting on a
  # false alarm is worse than skipping.
  if sh -n "$CLAUDE_ENV_FILE" 2>/dev/null; then
    exit 0
  fi
fi

# --- build the whole block in memory first -----------------------------------
#
# Each VALUE is single-quoted before being written. An earlier version wrote the
# raw line through as `export KEY=VALUE`, so a value containing $(...) or
# backticks was EXECUTED when the env file was sourced, and any value with a
# space was silently truncated at the space. A single line appended to
# .env.local was therefore code execution on every SessionStart.
#
# `~/` is expanded here rather than left to the shell, because quoting the value
# (which is what stops the execution) also stops tilde expansion, and several of
# the wired variables are `~/`-relative key paths.
#
# `export KEY=VALUE` is accepted as well as bare `KEY=VALUE`: the export form is
# what people paste from provider docs, and anchoring only on the key meant such
# a credential sat in the file looking wired while every session came up without it.
BLOCK=$(
  grep -E '^(export[[:space:]]+)?[A-Za-z_][A-Za-z0-9_]*=' "$ENVFILE" 2>/dev/null |
  while IFS= read -r line; do
    # Strip a trailing CR so a CRLF-saved .env.local cannot smuggle one into an
    # exported value. .env.local is edited by tools on Windows and really does
    # carry CRLF (34 CRLF endings when this was written). A trailing CR inside a
    # quoted value is invisible in every diff and breaks path comparisons.
    line=$(printf '%s' "$line" | tr -d '\r')
    line=${line#export }
    line=${line#"${line%%[![:space:]]*}"}
    key=${line%%=*}
    val=${line#*=}
    # An empty value carries no information, and exporting it is actively
    # confusing: a placeholder slot (KIMI_API_KEY= before the key arrives) then
    # reads as "set" to anything testing with -n. Skip it entirely.
    [ -n "$val" ] || continue
    # Drop one layer of surrounding quotes if the file already has them.
    case "$val" in
      \"*\") val=${val#\"}; val=${val%\"} ;;
      \'*\') val=${val#\'}; val=${val%\'} ;;
    esac
    case "$val" in
      "~/"*) val="$HOME/${val#\~/}" ;;
    esac
    # Escape embedded single quotes: ' becomes '\''
    esc=$(printf '%s' "$val" | sed "s/'/'\\\\''/g")
    printf "export %s='%s'\n" "$key" "$esc"
  done
)

# Nothing usable in .env.local: leave the env file untouched rather than writing
# an empty marked block that later runs would have to reason about.
[ -n "$BLOCK" ] || exit 0

# --- clean out anything we previously wrote, marked OR unmarked ---------------
#
# Three cases, and missing any one of them leaves a session wedged:
#
#   MARKED, INTACT   delete BEGIN..END.
#   MARKED, TORN     BEGIN with no END, because the tear happened mid-block.
#                    "delete BEGIN..END" matches nothing, so delete BEGIN..EOF.
#   UNMARKED         the file was written by the PRE-FIX hook, which had no
#                    markers at all. This is the case that actually stranded a
#                    live session, and the first version of this fix missed it:
#                    with no marker to find, cleanup did nothing and the fresh
#                    block was simply appended after 112 poisoned lines. Caught
#                    by testing the real recovery path rather than assuming it.
#                    Handled by deleting `export KEY=` for every key we manage,
#                    which is precisely the set we are about to rewrite.
#
# Then, whatever remains, drop trailing lines until the file parses. The file is
# append-only, so a tear is always at the end; this is bounded and never touches
# earlier content the harness may own.
if [ -f "$CLAUDE_ENV_FILE" ]; then
  TMP="$CLAUDE_ENV_FILE.claude-env.$$"
  if grep -qF "$BEGIN_MARK" "$CLAUDE_ENV_FILE" 2>/dev/null; then
    if grep -qF "$END_MARK" "$CLAUDE_ENV_FILE" 2>/dev/null; then
      awk -v b="$BEGIN_MARK" -v e="$END_MARK" \
        'index($0,b)==1{skip=1} skip==0{print} index($0,e)==1{skip=0}' \
        "$CLAUDE_ENV_FILE" > "$TMP" 2>/dev/null
    else
      awk -v b="$BEGIN_MARK" 'index($0,b)==1{exit} {print}' \
        "$CLAUDE_ENV_FILE" > "$TMP" 2>/dev/null
    fi
    [ -f "$TMP" ] && mv -f "$TMP" "$CLAUDE_ENV_FILE" 2>/dev/null
  fi

  # Unmarked legacy copies: strip `export KEY=` for every key .env.local names.
  # Derived from .env.local rather than from BLOCK on purpose: a key whose value
  # is currently EMPTY is skipped when building BLOCK, so keying off BLOCK would
  # leave that key's stale export behind forever once it was blanked.
  KEYLIST=$(grep -E '^(export[[:space:]]+)?[A-Za-z_][A-Za-z0-9_]*=' "$ENVFILE" 2>/dev/null |
            sed -e 's/^export[[:space:]]*//' -e 's/=.*//' -e 's/[[:space:]]*$//' |
            tr -d '\r')
  if [ -n "$KEYLIST" ]; then
    printf '%s\n' "$KEYLIST" > "$TMP.keys" 2>/dev/null
    awk 'NR==FNR{k[$0]=1;next}
         {line=$0
          if (match(line,/^export [A-Za-z_][A-Za-z0-9_]*=/)) {
            n=substr(line,8); sub(/=.*/,"",n)
            if (n in k) next
          }
          print}' "$TMP.keys" "$CLAUDE_ENV_FILE" > "$TMP" 2>/dev/null
    [ -f "$TMP" ] && mv -f "$TMP" "$CLAUDE_ENV_FILE" 2>/dev/null
    rm -f "$TMP.keys" 2>/dev/null
  fi

  # Whatever is left must parse. Drop trailing lines until it does, bounded so a
  # pathological file can never spin. Anything genuinely unparseable and NOT ours
  # would be emptied here, which is still strictly better than a session that
  # cannot run a single command.
  N=0
  while [ "$N" -lt 300 ] && [ -s "$CLAUDE_ENV_FILE" ] && ! sh -n "$CLAUDE_ENV_FILE" 2>/dev/null; do
    sed '$d' "$CLAUDE_ENV_FILE" > "$TMP" 2>/dev/null && mv -f "$TMP" "$CLAUDE_ENV_FILE" 2>/dev/null
    N=$((N + 1))
  done
  rm -f "$TMP" 2>/dev/null
fi

# --- ONE write. A torn line is impossible because there is only one append. ---
printf '%s\n%s\n%s\n' "$BEGIN_MARK" "$BLOCK" "$END_MARK" >> "$CLAUDE_ENV_FILE" 2>/dev/null

exit 0
