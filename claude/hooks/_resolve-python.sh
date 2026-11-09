# Shared Python resolver for the guardrail hooks. Sourced, not executed.
#
# WHY THIS EXISTS: `command -v python` trusts ambient PATH ordering, and a
# virtualenv earlier on PATH silently shadows the system interpreter. On this
# machine `python` resolved into an unrelated tool's venv, so deleting that
# tool would have changed guardrail behaviour. Hooks must never depend on
# which shell happened to launch them.
#
# Resolution order (first working interpreter wins):
#   1. $CLAUDE_HOOK_PYTHON   explicit override, absolute path
#   2. py -3                 Windows launcher, immune to venv PATH shadowing
#   3. python3               POSIX convention
#   4. python                last resort
#
# Sets HOOK_PY and HOOK_PYARGS. Returns 1 if nothing usable was found; the
# caller decides whether that means fail-closed (blockers) or fail-open
# (the best-effort secret scanner).

resolve_hook_python() {
  HOOK_PY=""
  HOOK_PYARGS=""

  if [ -n "${CLAUDE_HOOK_PYTHON:-}" ] && "$CLAUDE_HOOK_PYTHON" -c '' >/dev/null 2>&1; then
    HOOK_PY="$CLAUDE_HOOK_PYTHON"
    return 0
  fi

  if command -v py >/dev/null 2>&1 && py -3 -c '' >/dev/null 2>&1; then
    HOOK_PY="py"
    HOOK_PYARGS="-3"
    return 0
  fi

  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c '' >/dev/null 2>&1; then
      HOOK_PY="$candidate"
      return 0
    fi
  done

  return 1
}

# Decode the Bash tool's command string out of the hook payload on stdin.
# Echoes the command; exits non-zero if the payload cannot be decoded.
decode_hook_command() {
  printf '%s' "$1" | "$HOOK_PY" $HOOK_PYARGS -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    sys.stdout.write((d.get('tool_input') or {}).get('command') or d.get('command') or '')
except Exception:
    sys.exit(3)
" 2>/dev/null
}

# Remove every quoted span from a command string, then split it into one
# segment per command separator (; && || |) AND per newline.
#
# WHY THIS IS NOT sed: the guards used `sed "s/'[^']*'//g; s/\"[^\"]*\"//g"`,
# which processes ONE LINE AT A TIME and understands no escapes. A multi-line
# quoted argument therefore kept its inner lines intact, and any inner line that
# happened to start with a trigger command was then read as a real command. A
# commit message documenting `git push ... main` on its own line was blocked as
# if it were a push. This scanner tracks quote state across the whole string and
# honours backslash escapes, so quoted prose can never be mistaken for a command.
#
# It also removes HERE-DOCUMENT bodies. A heredoc body is data, not commands,
# but it is not quoted, so quote-stripping alone leaves it intact and any line
# inside it that starts with a trigger word reads as a real command. Writing a
# multi-line commit message with `git commit -F - <<'MSG'` is the normal way to
# do it, and describing these very commands inside one used to be blocked.
strip_quoted_and_split() {
  printf '%s' "$1" | "$HOOK_PY" $HOOK_PYARGS -c "
import sys, re
s = sys.stdin.read()

# --- drop heredoc bodies first (<<EOF, <<-EOF, <<'EOF', <<\"EOF\") ---
lines = s.split('\n')
kept, i, n = [], 0, len(lines)
while i < n:
    line = lines[i]
    kept.append(line)
    m = re.search(r'<<-?\s*([\'\"]?)([A-Za-z_][A-Za-z0-9_]*)\1', line)
    if m:
        delim = m.group(2)
        i += 1
        while i < n and lines[i].strip() != delim:
            i += 1
        if i < n:
            i += 1          # consume the terminator line itself
        continue
    i += 1
s = '\n'.join(kept)

out, i, n = [], 0, len(s)
quote = None
while i < n:
    c = s[i]
    if quote:
        if c == '\\\\' and quote == '\"' and i + 1 < n:
            i += 2; continue
        if c == quote:
            quote = None
        else:
            # Keep newlines so multi-line quoted text still splits into
            # segments that are inert rather than silently concatenating
            # the surrounding real commands together.
            if c == '\n':
                out.append('\n')
        i += 1; continue
    if c in ('\'', '\"'):
        quote = c; i += 1; continue
    out.append(c); i += 1
text = ''.join(out)
for seg in re.split(r'&&|\|\||;|\||\n', text):
    sys.stdout.write(seg + '\n')
" 2>/dev/null
}

# Decode the session cwd out of the hook payload. Echoes '' when absent.
# Needed by guards that must resolve real git state (e.g. which branch a bare
# `git push` would actually land on) rather than only pattern-matching text.
decode_hook_cwd() {
  printf '%s' "$1" | "$HOOK_PY" $HOOK_PYARGS -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    sys.stdout.write(d.get('cwd') or (d.get('tool_input') or {}).get('cwd') or '')
except Exception:
    sys.stdout.write('')
" 2>/dev/null
}
