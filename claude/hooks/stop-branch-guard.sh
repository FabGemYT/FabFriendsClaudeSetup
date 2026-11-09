#!/bin/bash
# Stop hook: refuse to end a turn with work stranded where it can be lost.
#
# WHY THIS EXISTS: on 2026-07-14 a session ended with 61 uncommitted files
# sitting on an already-merged branch. Nothing was lost, but nothing was
# protecting it either. Law 4 says one task = one fresh branch, and work must
# end PR-ready. This makes that mechanical instead of aspirational.
#
# CONTRACT: reason on stderr + exit 2 = block the stop, Claude keeps working.
# Clean exit 0 = allow the stop.
#
# IT DELIBERATELY DOES NOT RUN BUILD OR TESTS. A Stop hook fires at the end of
# EVERY turn, so shelling out to `pnpm build` would add minutes of latency to
# every single exchange. Build/test gating already happens at the correct
# moment: the commit-push-pr skill runs them and stops on failure before
# anything reaches a PR. This hook only does cheap local git checks (~100ms).
#
# IT BLOCKS AT MOST ONCE. `stop_hook_active` is true when Claude is stopping
# after this hook already blocked. Without that guard a persistent condition
# (say, a file Claude cannot commit) would block forever and wedge the session
# in a loop. One nudge is the correct dose: it tells Claude to commit, and if
# Claude has a real reason not to, the session still ends.
#
# FAILS OPEN. Not a git repo, no git, no interpreter, any unexpected error:
# exit 0. This hook must never strand a session that is otherwise fine.

INPUT=$(cat)

# --- loop guard: never block twice in a row -------------------------------
ACTIVE=""
if command -v py >/dev/null 2>&1 && py -3 -c "" >/dev/null 2>&1; then
  ACTIVE=$(printf '%s' "$INPUT" | py -3 -c "
import sys,json
try:
    print('yes' if json.loads(sys.stdin.read()).get('stop_hook_active') else '')
except Exception:
    print('')
" 2>/dev/null)
else
  # Fallback: tolerate whitespace variations in the JSON.
  printf '%s' "$INPUT" | tr -d ' \n' | grep -q '"stop_hook_active":true' && ACTIVE="yes"
fi
[ -n "$ACTIVE" ] && exit 0

# --- locate the repo -------------------------------------------------------
CWD=$(printf '%s' "$INPUT" | tr -d '\n' \
  | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -n "$CWD" ] || CWD="$PWD"
CWD="${CWD//\\//}"
[ -d "$CWD" ] || exit 0

command -v git >/dev/null 2>&1 || exit 0
git -C "$CWD" rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# --- is there uncommitted work? -------------------------------------------
DIRTY=$(git -C "$CWD" status --porcelain 2>/dev/null | head -200)
[ -n "$DIRTY" ] || exit 0

COUNT=$(printf '%s\n' "$DIRTY" | grep -c .)
BRANCH=$(git -C "$CWD" rev-parse --abbrev-ref HEAD 2>/dev/null)

# --- case 1: uncommitted work directly on main ----------------------------
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  printf '%s\n' "Stop blocked: $COUNT uncommitted change(s) sitting on '$BRANCH' in $CWD.

Law 4: one task = one fresh branch, and work ends PR-ready. Committing to
'$BRANCH' is also blocked on push, so this work currently has nowhere to go.

Do this before finishing: create a fresh task branch off '$BRANCH', commit the
work there, push, and open a PR. If these changes are genuinely throwaway, say
so explicitly and stop again." >&2
  exit 2
fi

# --- case 2: uncommitted work on a branch already merged into main --------
# This is the exact 2026-07-14 failure: the branch tip is already an ancestor
# of origin/main, so the branch is spent and anything uncommitted on top of it
# belongs on a new branch.
#
# REQUIRES AN UPSTREAM. A branch that has never been pushed cannot be "spent" --
# it is a fresh branch someone just cut, which is the single most common state
# in this workflow (cut branch, start editing, turn ends). A fresh branch is
# also trivially an ancestor of origin/main, so the ancestor test alone fired on
# every new branch and told the user their brand-new branch was dead. That cried
# wolf constantly, and a guard people learn to ignore protects nothing. The
# branch in the real incident had been pushed and PR'd, so requiring an upstream
# keeps the case that mattered and drops the noise.
git -C "$CWD" rev-parse --abbrev-ref '@{upstream}' >/dev/null 2>&1 || exit 0

for BASE in origin/main origin/master main master; do
  git -C "$CWD" rev-parse --verify "$BASE" >/dev/null 2>&1 || continue
  if git -C "$CWD" merge-base --is-ancestor HEAD "$BASE" >/dev/null 2>&1; then
    printf '%s\n' "Stop blocked: $COUNT uncommitted change(s) on '$BRANCH', which is
already fully merged into $BASE.

This is the failure from 2026-07-14: a spent branch holding real work. Anything
committed here now would sit on a dead branch and never reach a PR.

Do this before finishing: cut a fresh branch off $BASE, move these changes onto
it (git stash push / checkout -b / stash pop), commit, push, open a PR." >&2
    exit 2
  fi
  break
done

exit 0
