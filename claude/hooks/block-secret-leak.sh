#!/bin/bash
# PreToolUse (Write|Edit|MultiEdit|NotebookEdit|Bash): best-effort scan for a
# live secret VALUE being written into a file, or appearing literally in a shell
# command. The real logic lives in secret-scan.py so there is no fragile
# bash/JSON escaping here.
#
# CONTRACT: block = reason on stderr + exit 2. Clean exit 0 = no opinion.
#
# FAILS OPEN by design: no interpreter, a missing scanner, or any scanner error
# all exit 0 and let the edit proceed. This hook must never block a legitimate
# edit; only a positive high-confidence match blocks. That is the opposite of
# the five fail-closed command guards, and it is deliberate. Since 2026-07-30
# the fail-open path is LOUD: a systemMessage warning tells the user the
# scanner did not run, so silent loss of protection is no longer possible.
#
# SCOPE: the scanner exempts .env* paths, *.pem, *.key, .credentials*,
# /.secrets/ and ~/.claude/secrets/, so the normal "Claude wires my secrets into
# .env.local and Vercel" workflow is never touched. Everything else is scanned.
# It does NOT check git-tracked status -- earlier comments here and in CLAUDE.md
# claimed it did, and no such check has ever existed.

INPUT=$(cat)

# Fail-open stays, but never SILENTLY: when the scanner cannot run, say so.
# A fail-open credential control whose failure is invisible is the one
# component in the stack that can lose protection with no signal (2026 norms
# are fail-closed for credential controls; the warning is the compromise that
# keeps availability). systemMessage on exit 0 shows the warning without
# blocking -- verified present in the 2.1.220 binary.
warn_open() {
  printf '{"systemMessage":"block-secret-leak: %s -- the secret-leak scanner DID NOT RUN on this operation and it proceeded unscanned. Install Python 3 or set CLAUDE_HOOK_PYTHON to restore scanning."}' "$1"
  exit 0
}

RESOLVER="$(dirname "${BASH_SOURCE[0]}")/_resolve-python.sh"
[ -f "$RESOLVER" ] || warn_open "_resolve-python.sh is missing"
# shellcheck source=/dev/null
. "$RESOLVER"

resolve_hook_python || warn_open "no working Python 3 interpreter found"

SCANNER="$(dirname "${BASH_SOURCE[0]}")/secret-scan.py"
[ -f "$SCANNER" ] || warn_open "secret-scan.py is missing"

# secret-scan.py exits 2 with the reason on stderr when it finds a live secret;
# anything else (including a crash) is treated as "no opinion".
# mktemp, not /tmp/<pid>: a predictable name in a shared temp dir is a symlink
# target another local process could pre-create. The five fail-closed guards
# already use mktemp; this one was the odd file out.
ERRFILE=$(mktemp 2>/dev/null || printf '%s' "/tmp/secret-scan-err.$$")
printf '%s' "$INPUT" | "$HOOK_PY" $HOOK_PYARGS "$SCANNER" 2>"$ERRFILE"
STATUS=$?

if [ "$STATUS" -eq 2 ]; then
  cat "$ERRFILE" >&2
  rm -f "$ERRFILE"
  exit 2
fi

# Exit 0 is a genuine all-clear. ANY other status means the scanner crashed or
# could not run, and this hook fails OPEN by design -- but the header promises
# that never happens silently, and until now it did: only a missing interpreter
# warned, a scanner traceback did not. An invisible fail-open on the one
# credential control is exactly the thing the loud-warning rule exists for.
if [ "$STATUS" -ne 0 ]; then
  warn_open "the secret scanner exited $STATUS (it did not run to completion)"
fi

rm -f "$ERRFILE"
exit 0
