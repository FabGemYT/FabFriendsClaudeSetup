"""Shared command analyser for the four PreToolUse command guards.

Usage:  <payload on stdin> | python command-guard.py {main-push|pr-merge|prod-deploy|pr-base}
Exit 2 + reason on stderr = block.  Exit 0 = no opinion.  Exit 3 = undecodable
(the calling hook decides; the four command guards fail CLOSED on that).

WHY THIS REPLACED THE BASH PATTERN-MATCHING
-------------------------------------------
The guards used to strip quoted spans from the command string and then grep the
remainder. An adversarial audit on 2026-07-29 broke that layer six independent
ways, every one confirmed by execution:

  1. QUOTE THE ARGUMENT   `git push origin "main"`  -> the stripper DELETED the
     very payload it was meant to inspect, so nothing matched.
  2. PREFIX THE BINARY    `npx vercel --prod`, `env git push origin main`,
     `VERCEL_ORG_ID=x vercel --prod`, `/usr/bin/git push origin main`,
     `git -C /repo push origin main` -> the checks anchored on the FIRST word.
  3. RESPELL THE FLAG     `vercel deploy --target production` is documented by
     Vercel as identical to `--prod`, and was not checked at all.
  4. USE ANOTHER TOOL     `gh api --method PUT repos/O/R/pulls/1/merge` and the
     curl equivalent merge a PR without ever typing `gh pr merge`.
  5. USE AN INTERPRETER   `bash -c "..."`, `sh -c '...'`, `eval "..."`.
  6. HIDE BEHIND `&`      `&` was not in the separator set, so a single `&`
     concealed the entire rest of the line.

So this module tokenises properly instead. It keeps token VALUES (quotes are
removed but the content survives, which is what defeats evasion 1), resolves the
real binary behind wrappers and env prefixes, recurses into interpreter strings,
and skips the values of message-carrying flags so that prose describing these
commands still cannot false-trigger.

It is deliberately conservative: when it cannot parse something it says so and
the caller fails closed.
"""
import json
import os
import posixpath
import re
import shlex
import subprocess
import sys

# Flags whose VALUE is free text, not a command. Their values are skipped so a
# commit message or PR body describing a forbidden command never false-triggers.
MESSAGE_FLAGS = {
    "-m", "--message", "-F", "--file", "--body", "--body-file", "-b",
    "--title", "-t", "--notes", "--subject", "-d", "--data", "--raw-field",
    "-f", "--field",
}

# Wrapper commands that run another command. The real binary is the next
# non-flag token after these.
WRAPPERS = {
    "env", "command", "time", "nice", "nohup", "sudo", "doas", "builtin",
    "exec", "npx", "bunx", "pnpx",
    # Added after `timeout 60 git push origin main` and friends were confirmed
    # to sail past every guard.
    "timeout", "stdbuf", "setsid", "ionice", "chrt", "unbuffer", "script",
    "strace", "ltrace", "watch", "xargs",
}
# Wrapper flags that consume the NEXT token, so the peel does not mistake a
# flag's value for the real binary.
# NOTE: `-i` is deliberately ABSENT. `env -i` means "ignore environment" and
# takes no value; listing it made the peel eat the real binary, so
# `env -i git push origin main` resolved to binary `git`... as its own value.
WRAPPER_VALUE_FLAGS = {
    "-u", "-g", "-n", "-o", "-I", "-s", "-k", "--signal", "--user",
    "--group", "--kill-after", "--output", "--max-procs", "-P", "-L",
    "--replace", "--max-args", "-e",
}
# Wrappers that take a leading positional argument of their own before the
# command (`timeout 60 cmd`, `watch 2 cmd`).
WRAPPER_POSITIONAL = {"timeout", "watch"}
DURATION_RE = re.compile(r"^\d+(\.\d+)?[smhd]?$")
# Shell grouping and control keywords. These are syntax, not commands, and
# returning one as "the binary" is how `(git push origin main)` slipped by.
SHELL_NOISE = {
    "(", ")", "{", "}", "then", "else", "elif", "fi", "do", "done", "esac",
    "if", "while", "until", "for", "case", "in", "!", "&&", "||", ";", "|",
    "select", "function",
}
# Two-word wrappers, matched on (tok0, tok1).
WRAPPER_PAIRS = {
    ("pnpm", "dlx"), ("pnpm", "exec"), ("npm", "exec"), ("yarn", "dlx"),
    ("bun", "x"), ("npm", "x"),
}

# `pnpm vercel --prod` / `yarn gh pr merge` run a project-local binary directly.
# Only the package manager is peeled -- the token after it IS the real binary,
# unless it is one of the manager's own subcommands.
PKG_MANAGERS = {"pnpm", "yarn", "npm", "bun"}
PKG_SUBCOMMANDS = {
    "run", "install", "i", "add", "remove", "rm", "uninstall", "test", "build",
    "dev", "lint", "exec", "dlx", "x", "start", "ci", "publish", "init",
    "create", "why", "list", "ls", "outdated", "update", "up", "audit", "link",
    "unlink", "pack", "version", "config", "cache", "store", "typecheck",
    "format", "prune", "rebuild", "root", "bin", "info", "login", "logout",
    "workspace", "workspaces", "dedupe", "fund", "doctor", "help",
}
# Commands whose string argument is itself a shell command to analyse.
INTERPRETERS = {"bash", "sh", "zsh", "dash", "ksh", "eval", "xargs", "fish"}

# Windows shells run arbitrary commands exactly like bash does, but with their
# own flag spelling, so they need a separate set. Leaving them out meant
# `powershell -c "Remove-Item -Recurse -Force $HOME/.claude/hooks"` resolved to
# binary `powershell` and sailed past every guard, deleting the guard layer.
WIN_SHELLS = {"powershell", "pwsh", "cmd"}
WIN_SHELL_CMD_FLAGS = {"-command", "-c", "/c", "/k", "-file", "/command"}

# Interpreters that run CODE, which can shell out. `node -e "...execSync('git
# push origin main')"` reached neither the deny list (prefix is `node`) nor any
# guard (binary resolved to `node`, and every guard returns early on a binary it
# does not own). settings.json auto-allows node/tsx/ts-node/find, so these were
# both unprompted AND unguarded -- the widest hole in the whole setup.
# The eval flag's VALUE is re-analysed as a shell command: crude, but a literal
# forbidden command inside a -e string is exactly the realistic case.
CODE_EVAL = {
    "node", "nodejs", "tsx", "ts-node", "bun", "deno", "esr",
    "python", "python3", "py", "perl", "ruby", "php", "Rscript",
}
CODE_EVAL_FLAGS = {"-e", "--eval", "-c", "--command", "-p", "--print", "-E"}

# `find ... -exec CMD ;` runs CMD. Same for -execdir / -ok / -okdir.
FIND_EXEC_FLAGS = {"-exec", "-execdir", "-ok", "-okdir"}
# Predicates that make `find` a writer rather than a reader. `-delete` is the
# dangerous one: `find ~/.claude/hooks -delete` wipes the guard layer, and
# settings.json auto-allows Bash(find:*) so it never even prompts.
FIND_DESTRUCTIVE = FIND_EXEC_FLAGS | {"-delete"}

# Inside a code payload the shell command sits in a STRING literal, e.g.
# `execSync('git push origin main')`. Shell-tokenising that whole expression
# strips the quotes and yields one opaque blob, so the command disappears.
# Pulling the quoted spans out and re-analysing each one is what actually
# surfaces it. Minimum length 4 skips noise like 'r' or 'utf8'.
CODE_STRING_RE = re.compile(r"""(['"])((?:(?!\1).){4,}?)\1""")

SEPARATOR = re.compile(r"&&|\|\||;|\||&|\n")

# Simple `VAR=value` assignments are collected so that indirection through a
# variable is not invisible to the refspec check: `B=main; git push origin $B`
# used to read as an unrecognised refspec and slip through.
ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")

# Populated per-invocation in main(); read by the guards.
ENV = {}


def fail(msg):
    sys.stderr.write(msg + "\n")
    sys.exit(3)


def block(msg):
    sys.stderr.write(msg + "\n")
    sys.exit(2)


def _unquoted_heredoc(line):
    """Find a `<<MARKER` that is NOT inside quotes. Returns the marker or None.

    Quote-awareness is the whole point: the old version matched `<<EOF` even
    inside a string, so `echo "<<EOF"` on line 1 deleted the entire rest of the
    command -- a two-line universal kill switch for all four guards.

    A `$( ... )` command substitution re-opens an unquoted shell context even
    inside double quotes, so a marker there IS live. That is the extremely
    common `git commit -m "$(cat <<'EOF' ... EOF)"` idiom, and treating its
    marker as quoted text left the whole message body sitting in the command
    stream to be re-parsed as commands.
    """
    quote = None
    subst = []          # saved quote state per open $( level
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        # A command substitution resets quoting, even mid-quote.
        if line[i:i + 2] == "$(":
            subst.append(quote)
            quote = None
            i += 2
            continue
        if ch == ")" and subst:
            quote = subst.pop()
            i += 1
            continue
        if quote:
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            i += 1
            continue
        if line[i:i + 2] == "<<":
            m = re.match(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", line[i:])
            if m:
                return m.group(2)
            i += 2
            continue
        i += 1
    return None


def strip_heredocs(text):
    """Split a command into (command-text, [(declaring-line, body), ...]).

    Heredoc bodies are usually data (a commit message), which is why they are
    lifted out of the command text. But when the heredoc feeds an interpreter
    (`bash <<EOF`, `cat <<EOF | bash`) the body IS the command, so it is
    returned separately for the caller to analyse rather than silently dropped.
    An UNTERMINATED marker keeps its lines instead of swallowing them.

    EACH BODY IS PAIRED WITH THE LINE THAT DECLARED IT, and that pairing is the
    whole point. The caller used to decide "is this body code?" by asking
    whether ANY segment anywhere in the command was an interpreter, so a command
    that merely ran `sh something.sh` earlier caused an UNRELATED
    `gh pr create --body-file - <<BODY` to have its prose parsed as commands.
    Measured 2026-08-16: that blocked a PR body and a commit message whose text
    quoted a delete command as evidence. A heredoc's own line is the only thing
    that decides whether its body executes.

    Callers that want just the command text keep unpacking `body, _ = ...`; only
    the dispatcher reads the second element, so the pairing is additive.
    """
    lines = text.split("\n")
    kept, bodies = [], []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        kept.append(line)
        delim = _unquoted_heredoc(line)
        if delim:
            body, j = [], i + 1
            closed = False
            while j < n:
                if lines[j].strip() == delim:
                    closed = True
                    break
                body.append(lines[j])
                j += 1
            if closed:
                bodies.append((line, "\n".join(body)))
                i = j + 1
                continue
            # Never terminated: treat the remainder as ordinary command text
            # rather than letting a bogus marker erase it.
        i += 1
    return "\n".join(kept), bodies


def split_segments(text):
    """Split on shell separators that are NOT inside quotes.

    The old implementation was a bare regex split, which is quote-blind. Given
    `python -c "import os; os.system('git push origin main')"` it cut at the
    `;` INSIDE the double-quoted payload, producing two fragments with unbalanced
    quotes -- so the nested command was destroyed before any guard could see it,
    and every code-interpreter payload containing a separator was invisible.
    Tracking quote state fixes that at the root instead of special-casing it.
    """
    out, buf = [], []
    quote = None
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and i + 1 < n:      # escaped char inside quotes
                buf.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if text[i:i + 2] in ("&&", "||"):
            out.append("".join(buf))
            buf = []
            i += 2
            continue
        if ch in ";|&\n":
            out.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    out.append("".join(buf))
    return [s for s in out if s.strip()]


def _strip_grouping(tok):
    """Peel shell grouping punctuation clinging to a token.

    `(git push origin main)` tokenises to `(git` ... `main)`, and the trailing
    paren stopped `main)` from matching the main/master pattern.

    Two exclusions, both learned from breaking them: a token holding a `$`
    expansion must keep its braces (`${B}` clipped to `${B` stops resolving),
    and a FLAG must keep them too (`-I{}` reduced to `-I` looks like a
    value-taking flag and then eats the real binary). Tokens made entirely of
    punctuation are left for SHELL_NOISE.
    """
    if "$" in tok:
        return tok
    if tok.startswith("-"):
        # Parens and semicolons are never part of a flag, but braces can be
        # (`xargs -I{}`), so only the unambiguous syntax is peeled.
        stripped = tok.strip("();")
        return stripped if stripped else tok
    stripped = tok.strip("(){};")
    return stripped if stripped else tok


# A native Windows path (`~\.claude\hooks`) is pure escape sequences
# to a POSIX shlex, which silently ate every backslash and yielded
# `C:Usersyou.claudehooks`. That path then normalised to nothing recognisable,
# so `cmd /c del ~\.claude\hooks\block-main-push.sh` deleted a guard
# unchallenged, and the icacls/attrib entries in TAMPER_WRITERS were dead code.
# Only drive-letter and UNC runs are converted, so ordinary shell escaping
# (`\;`, `\"`, line continuations) keeps its meaning.
WIN_PATH_RE = re.compile(r"(?:[A-Za-z]:|\\\\[^\\\s]+)\\[^\s\"';|&]*")


def _normalize_win_paths(segment):
    return WIN_PATH_RE.sub(lambda m: m.group(0).replace("\\", "/"), segment)


def tokenize(segment):
    """Shell-tokenise, KEEPING values (unlike the old quote-stripper)."""
    segment = _normalize_win_paths(segment)
    try:
        toks = shlex.split(segment, posix=True)
    except ValueError:
        # Unbalanced quotes. Fall back to a whitespace split with quote chars
        # removed so we still see the words rather than giving up silently.
        toks = [t.strip("\"'") for t in segment.split() if t.strip("\"'")]
    return [_strip_grouping(t) for t in toks]


def resolve(tokens):
    """Return (binary, args) with env prefixes, wrappers, shell syntax and paths
    peeled off.

    Three fixes over the naive version, each a confirmed bypass:
      * A FLAG after a wrapper used to end the peel, so `env -i git push origin
        main` resolved to binary `env` and every guard returned early.
      * Shell grouping and keywords used to be returned as the binary, so
        `(git push origin main)` resolved to `(git` and matched nothing.
      * Wrappers like timeout/stdbuf/setsid were simply absent from the set.
    """
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        # Shell grouping / control keywords carry no binary of their own.
        stripped = tok.strip("(){}")
        if tok in SHELL_NOISE or stripped == "":
            i += 1
            continue
        if tok != stripped and stripped:
            tokens = tokens[:i] + [stripped] + tokens[i + 1:]
            n = len(tokens)
            continue
        # VAR=value prefixes
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tok):
            i += 1
            continue
        if i + 1 < n and (tok, tokens[i + 1]) in WRAPPER_PAIRS:
            i += 2
            continue
        base = os.path.basename(tok.replace("\\", "/"))
        base = re.sub(r"\.(exe|cmd|bat|ps1)$", "", base, flags=re.I)
        # An npm version suffix defeated every binary check: `npx vercel@latest
        # --prod` resolved to binary `vercel@latest`, which matched no guard, so
        # it shipped to production unchallenged. Same for `npx eas-cli@16 submit`
        # and `npx gh@2 pr merge`. Strip a trailing @version (but never a scope,
        # `@scope/pkg` has the @ at position 0).
        if "@" in base[1:]:
            base = re.sub(r"@[^@/]*$", "", base)
        # `pnpm vercel ...` -> peel only the manager, keep `vercel` as binary.
        if (base in PKG_MANAGERS and i + 1 < n
                and not tokens[i + 1].startswith("-")
                and tokens[i + 1] not in PKG_SUBCOMMANDS):
            i += 1
            continue
        if base in WRAPPERS:
            is_positional_wrapper = base in WRAPPER_POSITIONAL
            i += 1
            # Skip this wrapper's own flags, and the values of the ones that
            # take a value, so the real binary after them is still found.
            while i < n and tokens[i].startswith("-"):
                takes_value = tokens[i] in WRAPPER_VALUE_FLAGS
                i += 1
                if takes_value and i < n:
                    i += 1
            # `timeout 60 cmd` / `watch 2 cmd`: skip the duration positional.
            if is_positional_wrapper and i < n and DURATION_RE.match(tokens[i]):
                i += 1
            continue
        # Every guard compares the binary against lowercase literals, and both
        # Windows shells and PowerShell cmdlets are case-insensitive, so
        # `Remove-Item` / `GIT` / `Vercel` must normalise or they match nothing.
        return base.lower(), tokens[i + 1:]
    return "", []


def npm_script_body(script, cwd):
    """Resolve `npm run <script>` to its package.json body, or None.

    Reading the manifest is what makes this precise: blocking every `npm run`
    would be wrong (most scripts are harmless) and allowing every `npm run` let
    a `"deploy": "vercel --prod"` script route straight past the guard.

    Tries the Windows form of an msys cwd too, for the same reason
    current_branch does: Git Bash hands out `/c/Users/...`, os.path.isfile
    rejects it, and the lookup would silently return None -- fail-open inside a
    fail-closed guard.
    """
    if not script or not cwd:
        return None
    for cand in _candidate_cwds(cwd):
        try:
            path = os.path.join(cand, "package.json")
            if not os.path.isfile(path):
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
            body = (data.get("scripts") or {}).get(script)
            if isinstance(body, str):
                return body
        except Exception:
            continue
    return None


def pkg_script_names(toks):
    """Script names a package-manager invocation might be running.

    Deliberately reads the RAW tokens instead of resolve()'s output. resolve()
    peels a package manager whenever the next token is not one of its own
    subcommands -- correct for `pnpm vercel --prod`, where `vercel` really is
    the binary -- but that peel means `pnpm deploy` resolves to binary "deploy"
    and never reaches the npm branch at all. The old `elif binary == "yarn"`
    arm was dead code for exactly that reason: resolve() had already eaten the
    yarn. So `pnpm deploy` and `yarn ship` ran a package.json script that the
    guards never saw, while `npm run deploy` was caught (because `run` IS a
    subcommand, so no peel happened).

    Returns both candidates when the form is ambiguous; a name that is not a
    real script simply resolves to None later, so guessing wide is free.
    """
    if not toks:
        return []
    base = os.path.basename(toks[0].replace("\\", "/"))
    base = re.sub(r"\.(exe|cmd|bat|ps1)$", "", base, flags=re.I)
    if base not in PKG_MANAGERS:
        return []
    nonflag = [t for t in toks[1:] if not t.startswith("-")]
    if not nonflag:
        return []
    # `npm run deploy`, `pnpm run deploy`, `bun run deploy`
    if nonflag[0] == "run" and len(nonflag) > 1:
        return [nonflag[1]]
    # `pnpm deploy` / `yarn ship` / `bun ship`: the implicit run form, which
    # pnpm, yarn and bun all support. npm does not, but checking costs nothing.
    return [nonflag[0]]


def expand_interpreters(segments, cwd=None):
    """Recurse into anything that runs another command.

    Covers shell interpreters (`bash -c`), code interpreters that can shell out
    (`node -e`), `find -exec`, npm/pnpm script bodies, and git alias
    definitions. Each nested command is appended as its own segment so the
    guards analyse it exactly as if it had been typed directly.
    """
    out = []
    queue = list(segments)
    seen = set()
    depth = 0
    # Bounded so a self-referential script cannot spin forever.
    while queue and depth < 6:
        depth += 1
        nxt = []
        for seg in queue:
            if seg in seen:
                continue
            seen.add(seg)
            out.append(seg)
            toks = tokenize(seg)
            if not toks:
                continue
            binary, args = resolve(toks)

            # Windows shells were entirely outside the parser, so
            # `powershell -c "Remove-Item -Recurse -Force ~/.claude/hooks"`
            # resolved to binary `powershell`, matched no guard, and deleted the
            # guard layer. Their command flags are spelled differently from the
            # POSIX `-c` cluster, so they need their own arm.
            if binary in WIN_SHELLS:
                for j, a in enumerate(args):
                    low = a.lower()
                    if low in WIN_SHELL_CMD_FLAGS and j + 1 < len(args):
                        # Everything AFTER the flag is the command, not just the
                        # next token: `cmd /c del C:\...\hook.sh` puts the path
                        # in a separate arg, so taking args[j+1] alone saw only
                        # `del` and the target was never inspected. Quoted forms
                        # (`powershell -c "..."`) still arrive as one token and
                        # rejoin harmlessly.
                        body, _ = strip_heredocs(" ".join(args[j + 1:]))
                        nxt.extend(split_segments(body))
                        break
                    elif low in ("-encodedcommand", "-enc", "-e") and j + 1 < len(args):
                        # Base64 payloads are not decoded here; flag the intent
                        # so an encoded command cannot pass as innocuous.
                        block("An encoded PowerShell command cannot be inspected "
                              "by the guard layer, so it is refused. Run the "
                              "command in plain text instead.")

            if binary in INTERPRETERS:
                for j, a in enumerate(args):
                    # Any single-dash cluster containing `c` is a command flag:
                    # `-c`, `-lc`, `-ec`, `-xc`. Matching only the exact token
                    # `-c` let `bash -lc '...'` through.
                    is_cmd_flag = (a.startswith("-") and not a.startswith("--")
                                   and "c" in a[1:])
                    if is_cmd_flag and j + 1 < len(args):
                        body, _ = strip_heredocs(args[j + 1])
                        nxt.extend(split_segments(body))
                    elif binary in ("eval", "xargs") and not a.startswith("-"):
                        body, _ = strip_heredocs(a)
                        nxt.extend(split_segments(body))
                    # `bash <<< "cmd"` feeds the herestring to the shell as input.
                    elif a == "<<<" and j + 1 < len(args):
                        body, _ = strip_heredocs(args[j + 1])
                        nxt.extend(split_segments(body))

            # node -e "...", python -c "...", perl -e "..."
            if binary in CODE_EVAL:
                payloads = []
                for j, a in enumerate(args):
                    if a in CODE_EVAL_FLAGS and j + 1 < len(args):
                        payloads.append(args[j + 1])
                    elif a.startswith("--eval="):
                        payloads.append(a.split("=", 1)[1])
                for payload in payloads:
                    body, _ = strip_heredocs(payload)
                    nxt.extend(split_segments(body))
                    # The command usually lives in a quoted string inside the
                    # code, not at the top level of it.
                    for lit in CODE_STRING_RE.finditer(payload):
                        nxt.extend(split_segments(lit.group(2)))

            # find . -name x -exec <cmd> \;
            if binary == "find":
                for j, a in enumerate(args):
                    if a in FIND_EXEC_FLAGS and j + 1 < len(args):
                        tail = [t for t in args[j + 1:] if t not in (";", "+", "\\;")]
                        if tail:
                            nxt.append(" ".join(tail))

            # `npm run deploy`, `pnpm deploy`, `yarn ship`, `bun run x`.
            # Driven off the RAW tokens, not `binary` -- see pkg_script_names.
            for script in pkg_script_names(toks):
                body = npm_script_body(script, cwd)
                if body:
                    txt, _ = strip_heredocs(body)
                    nxt.extend(split_segments(txt))

            # git config alias.x '!git push origin main'
            if binary == "git":
                for a in args:
                    # ORDER MATTERS. The `alias.` skip used to come first, so a
                    # one-shot `git -c alias.x='!vercel --prod' x` arrived as the
                    # SINGLE token `alias.x=!vercel --prod`, hit the skip, and
                    # the payload behind the `=` was never analysed at all. Test
                    # for the shell-out marker first, wherever it sits.
                    if "=" in a and a.split("=", 1)[1].lstrip("'\"").startswith("!"):
                        nxt.extend(split_segments(
                            a.split("=", 1)[1].lstrip("'\"").lstrip("!")))
                        continue
                    if a.startswith("alias."):
                        continue
                    if a.startswith("!"):
                        nxt.extend(split_segments(a.lstrip("!")))
        queue = nxt
    return out


def args_without_message_values(args):
    """Drop free-text flag values so prose cannot look like a command."""
    out = []
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a in MESSAGE_FLAGS:
            skip = True
            continue
        if re.match(r"^--(message|body|title|notes|data|field|file)=", a):
            continue
        out.append(a)
    return out


def collect_assignments(segments):
    """Gather literal `VAR=value` assignments across the whole command line.

    Only literal values are recorded. A value that is itself an expansion is
    deliberately skipped rather than half-resolved, because a wrong expansion is
    worse than an unresolved one -- the unresolved case still gets caught by
    UNRESOLVED_MAIN_RE below.
    """
    env = {}
    for seg in segments:
        toks = tokenize(seg)
        # `export B=main && git push origin $B` recorded nothing, because the
        # scanner stopped dead on the leading `export` token and never saw the
        # assignment behind it. Same for declare/typeset/local.
        while toks and toks[0] in ("export", "declare", "typeset", "local"):
            toks = toks[1:]
        for tok in toks:
            m = ASSIGN_RE.match(tok)
            if not m:
                # Assignments only ever LEAD a segment; stop at the first
                # non-assignment token so `git commit -m "A=b"` is not mined.
                break
            name, val = m.group(1), m.group(2)
            if "$" not in val and "`" not in val:
                env[name] = val
    return env


def expand_vars(text):
    """Substitute known literal assignments; leave unknown expansions intact."""
    def sub(m):
        return ENV.get(m.group(1) or m.group(2), m.group(0))
    return VAR_RE.sub(sub, text)


def _candidate_cwds(cwd):
    """The given cwd plus a Windows form of an msys path.

    Git Bash hands out `/c/Users/...`, which `os.path.isdir` rejects on Windows.
    That made the branch lookup return None, and None reads as "no opinion",
    so a bare `git push` while sitting on main was ALLOWED. Fail-open inside a
    fail-closed guard.
    """
    out = []
    if cwd:
        out.append(cwd)
        m = re.match(r"^/([A-Za-z])/(.*)$", cwd)
        if m:
            out.append("%s:/%s" % (m.group(1).upper(), m.group(2)))
    return out


def current_branch(cwd):
    for cand in _candidate_cwds(cwd):
        if not os.path.isdir(cand):
            continue
        try:
            r = subprocess.run(
                ["git", "-C", cand, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            pass
    return None


# --------------------------------------------------------------------------
# guards
# --------------------------------------------------------------------------
MAIN_RE = re.compile(r"^\+?([^:]*:)?(refs/heads/)?(main|master)$")
PUSH_MSG = ("Direct push to main/master is blocked. Push a feature branch and open a PR "
            "via gh pr create --base main. The user merges PRs in the GitHub UI; "
            "production auto-deploys on merge to main.")


def guard_main_push(binary, args, cwd):
    if binary != "git":
        return
    # `git -C <dir> push`, `git --no-pager push`, etc.
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-C", "--git-dir", "--work-tree", "--namespace", "-c"):
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        break
    if i >= len(args) or args[i] != "push":
        return
    # NOT args_without_message_values() here. Under `git push`, `-f` means
    # --force and takes NO value, but it sits in MESSAGE_FLAGS for `gh api -f
    # k=v`. Stripping its "value" swallowed the remote, so
    # `git push -f origin main` parsed as remote="main" with zero refspecs and
    # was allowed -- a force-push to main, the worst case this guard exists to
    # stop. `git push` takes no free-text flags at all, and the value-carrying
    # ones it does take (-o, --receive-pack, --exec, --repo) are handled in the
    # positional scan below, so no stripping is needed.
    rest = args[i + 1:]

    if any(a in ("--all", "--mirror") for a in rest):
        block("git push --all / --mirror would include main/master. Push specific "
              "feature branches and open a PR; the user merges via the GitHub UI.")
    if any(a in ("--dry-run", "-n") for a in rest):
        return  # pushes nothing; blocking it is a pure trust tax

    positionals, skip = [], False
    for a in rest:
        if skip:
            skip = False
            continue
        if a in ("-o", "--push-option", "--receive-pack", "--exec", "--repo"):
            skip = True
            continue
        if a.startswith("-"):
            continue
        positionals.append(a)

    # A command substitution is checked against the WHOLE argument span, not
    # per-token: shlex splits `$(echo main)` into `$(echo` + `main)`, so no
    # single refspec ever contains the substitution intact. Requiring a
    # substitution marker AND a whole-word main/master keeps `$BRANCH` and
    # `$(git branch --show-current)` allowed while refusing `$(echo main)`.
    joined = " ".join(rest)
    if any(mark in joined for mark in ("$(", "`", "${")) and \
            re.search(r"\b(main|master)\b", joined):
        block("Blocked: this push builds its target at runtime and mentions "
              "main/master, so it cannot be shown to be safe.\n\n%s" % PUSH_MSG)

    refspecs = positionals[1:] if positionals else []
    for r in refspecs:
        if MAIN_RE.match(expand_vars(r)):
            block(PUSH_MSG)
    # A value-taking flag can consume the remote and leave main/master sitting
    # in the remote slot (`git push --repo origin main`). Any positional that IS
    # literally main/master is treated as a branch reference regardless of
    # position -- no legitimate remote is named `main`.
    for p in positionals:
        if MAIN_RE.match(expand_vars(p)):
            block(PUSH_MSG)
    if not refspecs or any(r in ("HEAD", "+HEAD", "HEAD:HEAD") for r in refspecs):
        br = current_branch(cwd)
        if br in ("main", "master"):
            block("Blocked: you are on '%s', so this push lands directly on %s even "
                  "though the command does not name it.\n\n'git push', 'git push origin' "
                  "and 'git push origin HEAD' all target the checked-out branch.\n\n%s"
                  % (br, br, PUSH_MSG))


GH_GLOBAL_VALUE_FLAGS = {"-R", "--repo", "--hostname", "--template", "-t"}


def gh_subcommand_path(args):
    """Positional gh subcommands, with global flags and their values removed.

    `gh -R owner/repo pr merge 5` and `gh pr --repo owner/repo merge 5` are both
    valid gh, and both defeated the old `a[0]=="pr" and a[1]=="merge"` test.
    """
    out = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in GH_GLOBAL_VALUE_FLAGS:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        out.append(a)
        i += 1
    return out


# Two confirmed holes in the old `pulls/\d+/merge`:
#   * The PR number is routinely a shell variable or a substitution, so
#     `gh api repos/O/R/pulls/$PR/merge` never matched the digit class.
#   * `repos/{owner}/{repo}/merges` merges a head branch straight into a base
#     with no pull request at all, which the PR-shaped pattern could not see.
MERGE_API_RE = re.compile(r"pulls/[^/\s'\"]+/merge|repos/[^\s'\"]+/merges")


def guard_pr_merge(binary, args, cwd):
    if binary == "gh":
        path = gh_subcommand_path(args)
        if len(path) >= 2 and path[0] == "pr" and path[1] == "merge":
            block("Merging PRs is blocked. The user merges in the GitHub UI; "
                  "production auto-deploys on merge to main.")
        if path and path[0] == "api":
            # RAW args here, not the message-filtered ones: a GraphQL mutation
            # travels as the VALUE of -f/--field, exactly what the filter drops,
            # which made the mergePullRequest check dead code.
            raw = " ".join(args)
            if MERGE_API_RE.search(raw) or "mergePullRequest" in raw:
                block("This gh api call merges a pull request, which is blocked. "
                      "The user merges in the GitHub UI.")
    a = args_without_message_values(args)
    joined = " ".join(a)
    # curl was the only HTTP client covered, so wget/http/httpie walked straight
    # past. guard_prod_deploy already covers all four; match it here.
    if binary in ("curl", "wget", "http", "httpie"):
        if MERGE_API_RE.search(joined) and re.search(r"api\.github\.com|:\s*PUT|-X\s*PUT|--request\s+PUT|--method\s+PUT", joined):
            block("This call merges a pull request via the GitHub API, which is "
                  "blocked. The user merges in the GitHub UI.")


PROD_MSG = ("Deploying NEW code to production is blocked. Deploy a PREVIEW and "
            "share the URL; production ships when the user merges to main and "
            "Vercel auto-deploys.\n"
            "NOT blocked, and probably what you want: `vercel redeploy <url> "
            "--target=production` rebuilds the SAME commit, which is how an env "
            "var change takes effect. `vercel rollback` is free too, as is every "
            "read-only command.")

# Vercel subcommands that only READ. Verified against `vercel --help` on CLI
# 54.6.1, not assumed. None of these can deploy anything, whatever flags follow,
# so `--prod` on them is a filter, not an action.
VERCEL_READ_ONLY = frozenset({
    "ls", "list", "inspect", "logs", "activity", "alerts", "metrics",
    "httpstat", "contract", "usage", "whoami", "teams", "projects", "project",
    "bisect", "open", "help", "pull", "switch", "skills", "deployments",
    "telemetry", "git", "link", "target",
})

# Subcommands that write, but never make new code live. Rebuilds, config, and
# local work. `env` is here because managing env vars is explicitly Claude's job.
VERCEL_SAFE_WRITE = frozenset({
    "redeploy", "rollback", "build", "dev", "env", "cache", "blob", "cron",
    "crons", "deploy-hooks", "firewall", "redirects", "routes", "rr",
    "rolling-release", "webhooks", "integration", "init", "install", "i",
    "microfrontends", "dns", "domains", "certs", "api", "curl", "connect",
    "integration-resource", "ir", "mcp", "agent",
})

# ---------------------------------------------------------------------------
# REWRITTEN 2026-08-08. The previous version BLOCKED, and it was measured wrong.
# ---------------------------------------------------------------------------
# Across 283 transcripts and 19 projects there have been 24 real guard blocks
# ever. Four touched an actual product. THREE OF THOSE FOUR were this gate, and
# all three were false positives: `drop policy`, `drop policy`, `drop function`,
# on a live web game. It has fired 8 times in total and never once caught anything
# real. It also blocked a command that was only READING a file, because the words
# appeared in a Python string literal.
#
# Worse than the interruptions: a session stripped the idempotency guards out of a
# real migration to get past it, and wrote this gate's own error text into the
# codebase as a design rationale. A guard that makes the code worse has negative
# value.
#
# THREE THINGS WERE WRONG.
#
#   1. THE VERB LIST. `drop policy|index|trigger|function|type` destroy NO DATA.
#      An index rebuilds; a policy in a migration is recreated on the next line.
#      Atlas, Squawk and Prisma -- the mature migration linters -- flag exactly
#      DROP TABLE / DROP COLUMN / RENAME COLUMN / TRUNCATE. This list was invented.
#   2. NO IDEMPOTENCY AWARENESS. Postgres has no `CREATE POLICY IF NOT EXISTS`, so
#      `drop policy if exists X; create policy X` is THE documented way to write a
#      re-runnable RLS migration. The gate treated the standard idiom as an attack.
#   3. IT COULD NOT TELL EXECUTING SQL FROM TEXT ABOUT SQL. Any command whose text
#      contained the words tripped it, including scripts that only rewrite a file.
#
# And its message was factually wrong. It asserted "IRREVERSIBLE ... Supabase has
# no down-migrations". All five projects are on Supabase PRO with WAL-G daily
# physical backups, 6-8 days retained (verified against the Management API). A
# dropped table restores to yesterday. That claim was used to justify blocking the owner.
#
# SO IT NOW WARNS AND NEVER BLOCKS. `permissionDecision: "allow"` plus
# `additionalContext` was probed live on 2026-08-08: the tool runs AND the text
# reaches the model. The owner gets zero friction; Claude still learns the statement is
# destructive and can raise it in conversation, which is the only channel that
# actually reaches the owner anyway.

# What actually destroys data, per the industry consensus above, plus the one
# security case backups cannot help with.
DATA_LOSS_SQL_RE = re.compile(
    r"\bdrop\s+(table|column|schema|database)\b"
    r"|\btruncate\s+(table\s+)?\w"
    # DELETE with no WHERE wipes every row and the old pattern MISSED it entirely,
    # which is the false NEGATIVE that sat beside eight false positives. Requiring
    # the statement to end right after the table keeps `delete from t where ...`
    # free; no re.M, so a WHERE on the next line still counts as present.
    r"|\bdelete\s+from\s+[\w.\"`]+\s*(?:;|\Z)"
    # Backups restore rows. They do NOT tell you an auth boundary was opened, and
    # the failure mode is a silent leak rather than an error. This one stays.
    r"|\bdisable\s+row\s+level\s+security\b",
    re.I)

# Removing an object and immediately recreating it is a REPLACE, not a destroy --
# and for policies it is the only idempotent form Postgres offers. Never warn on it.
SQL_REPLACE_RE = re.compile(
    r"\bdrop\s+(\w+)\s+if\s+exists\s+([\w.\"`]+)[^;]*;\s*create\s+\1\b", re.I)

DATA_LOSS_SQL_MSG = (
    "Heads up: this statement destroys data (%s). Not blocking you -- it is "
    "running. But these five projects have daily backups, NOT point-in-time "
    "recovery, so the worst case is losing up to ~24h, and a `disable row level "
    "security` is not covered by a backup at all.\n"
    "If this touches live user data, say so to the owner in conversation before or "
    "immediately after, in one line. Do not hand the owner a command to run.")


# Binaries that actually SEND SQL to a database. The old gate inspected every
# command, which is why a Python script that merely rewrote a migration file was
# blocked -- the words were in a string literal. Scoping to real SQL clients means
# a false positive on prose or on file-editing is now impossible rather than
# merely unlikely.
SQL_CLIENTS = {"psql", "pgcli", "mysql", "supabase", "pg_dump", "pg_restore"}


def sql_warning(text):
    """The destructive-SQL note, or None. Never blocks; see DATA_LOSS_SQL_MSG."""
    # A drop immediately followed by a matching create is a REPLACE. Strip those
    # spans before looking, so the standard idempotent migration idiom is silent.
    cleaned = SQL_REPLACE_RE.sub(" ", text)
    m = DATA_LOSS_SQL_RE.search(cleaned)
    return m.group(0).strip() if m else None


# Flags that give curl or wget a request BODY, which makes the request a POST
# (or a PUT for curl -T) unless a method or -G says otherwise.
CURL_BODY_FLAGS = ("-d", "--data", "--data-raw", "--data-binary", "--data-ascii",
                   "--data-urlencode", "--json", "-F", "--form", "--form-string",
                   "-T", "--upload-file")
WGET_BODY_FLAGS = ("--post-data", "--post-file", "--body-data", "--body-file")


def http_writes(binary, args):
    """True unless this HTTP client call is plainly a GET or HEAD.

    Match the OPERATION, not a substring: `GET /v6/deployments?target=production`
    lists what is live (read-only), while `POST /v13/deployments` with
    "target":"production" creates a production deployment. The substring check
    blocked the read on 2026-10-16 (a second online store, checking the live build after
    a merge). Anything this cannot read plainly counts as a write, so the guard
    still fails towards blocking.
    """
    if binary == "curl":
        method, body, get = None, False, False
        i = 0
        while i < len(args):
            a = args[i]
            if a in ("-X", "--request"):
                method = (args[i + 1] if i + 1 < len(args) else "").upper()
                i += 2
                continue
            if a.startswith("--request="):
                method = a.split("=", 1)[1].upper()
            elif a in ("-G", "--get"):
                get = True
            elif a in ("-I", "--head"):
                method = method or "HEAD"
            elif a in CURL_BODY_FLAGS or any(
                    a.startswith(f + "=") for f in CURL_BODY_FLAGS if f.startswith("--")):
                body = True
            elif re.match(r"^-[A-Za-z]", a):
                # a cluster of short flags: -sSX POST, -XPOST, -sd @file, -sG
                letters = a[1:]
                if "X" in letters:
                    rest = letters.split("X", 1)[1]
                    if rest:
                        method = rest.upper()
                    else:
                        method = (args[i + 1] if i + 1 < len(args) else "").upper()
                        i += 2
                        continue
                if any(c in letters for c in "dFT"):
                    body = True
                if "G" in letters:
                    get = True
                if "I" in letters:
                    method = method or "HEAD"
            i += 1
        if method:
            return method not in ("GET", "HEAD")
        return body and not get
    if binary == "wget":
        for a in args:
            if a.startswith("--method="):
                return a.split("=", 1)[1].upper() not in ("GET", "HEAD")
            if a in WGET_BODY_FLAGS or any(a.startswith(f + "=") for f in WGET_BODY_FLAGS):
                return True
        return False
    return True  # httpie and anything else: judged as a write, as before


def guard_prod_deploy(binary, args, cwd):
    # Destructive SQL WARNS, it does not block. See the rewrite note above
    # DATA_LOSS_SQL_RE for the measurements behind that: 3 of the 4 guard blocks
    # that ever touched a real product were this check, and all 3 were wrong.
    if binary in SQL_CLIENTS:
        hit = sql_warning(" ".join(args))
        if hit:
            emit_warn(DATA_LOSS_SQL_MSG % hit)

    # The Vercel REST API reaches production without ever typing `vercel`.
    # guard_pr_merge has covered the GitHub REST equivalent since the 2026-07-29
    # audit; this guard never got the same treatment, so `curl -X POST
    # api.vercel.com/v10/projects/X/promote/Y` re-aliased production with no
    # guard firing at all. Worse, the CLI's `vercel env add` has two open
    # upstream bugs (#16160 saves empty for sensitive vars, #15763 hangs on
    # preview), so the REST API is the RECOMMENDED path for env work: the route
    # a careful session is most likely to take was the one route left unwatched.
    joined_raw = " ".join(args)
    if binary in ("curl", "wget", "http", "httpie") and "api.vercel.com" in joined_raw:
        # Only PROMOTE. rollback was un-gated with the CLI on 2026-08-07 (it
        # restores a known-good build, which is the reversible direction and the
        # emergency tool), so blocking its REST twin would be an inconsistency
        # that only shows up mid-incident, which is the worst possible time.
        if re.search(r"/promote/", joined_raw):
            block("This call promotes a NEW deployment to production via the "
                  "REST API, which is blocked exactly like the CLI equivalent. "
                  "Production ships when the user merges to main. Rollback and "
                  "redeploy are not blocked.")
        # Creating a deployment with target=production, in a flag or a body. A plain
        # GET only reads: listing the deployments filtered to production is how a
        # session checks what is live, so only a request that writes is judged.
        if "/deployments" in joined_raw and http_writes(binary, args) and re.search(
                r'"?target"?\s*[:=]\s*"?production', joined_raw):
            block(PROD_MSG + "\n(Creating a production deployment through the "
                  "Vercel REST API is the same action as 'vercel --prod'.)")
    # Store submission is a production publish too. settings.json also denies
    # these, but a deny rule is editable config while this hook is the layer
    # that is supposed to hold regardless -- so it is checked in both places.
    # STORE SUBMISSION IS CLAUDE'S JOB. The owner's decision, 2026-08-07: "i loved
    # that it handled my resend store submissions and everything". The block here
    # dated from the 2026-05-30 initial backup, BEFORE the owner clarified in Session 5
    # (2026-06-19) that the real goal was "automate the boring store-listing work
    # and builds". It was legacy conservatism, never a decision the owner made.
    #
    # Submitting is not the same as publishing, and the tool docs draw the line
    # in exactly the place the owner drew it the owner ("the last submit button on
    # stuffs like play store app store submissions ... I'll do"):
    #
    #   eas submit / eas build --auto-submit
    #       Expo docs: uploads the binary to App Store Connect where it lands in
    #       TestFlight, or to the Play internal track. It does NOT submit for
    #       review. --auto-submit is internal testing only. -> CLAUDE'S JOB.
    #   fastlane deliver --submit_for_review
    #       This IS the submit button. It puts the build in front of Apple's
    #       reviewers, and approval publishes to every user. -> CONFIRM IN CHAT.
    #   fastlane supply --track production / --track_promote_to production
    #       Same on Android: promotes off the test tracks to the public one.
    #
    # Uploading is Claude's. Pressing submit is the owner's. Everything else stays free.
    if binary in ("eas", "eas-cli"):
        return
    if binary in ("fastlane", "bundle"):
        low = " ".join(args).lower()
        if "--submit_for_review" in low or "submit_for_review:true" in low:
            action = "fastlane submit_for_review"
            if not consume_approval(action):
                block(CONFIRM_MSG % (
                    "`--submit_for_review` presses the App Store submit button. "
                    "Once Apple approves, it publishes to every user, and that "
                    "step is the owner's, not Claude's. Uploading the build (eas submit, "
                    "plain fastlane deliver) needs no permission at all.",
                    _shq(action), action))
        if re.search(r"--(track|track_promote_to)[= ]+production\b", low):
            action = "fastlane track production"
            if not consume_approval(action):
                block(CONFIRM_MSG % (
                    "Promoting to the Play `production` track publishes to every "
                    "user. Internal, alpha and beta tracks are Claude's job and "
                    "need no permission. Turning on Managed Publishing in the Play "
                    "Console makes this gate native instead of a guard rule.",
                    _shq(action), action))
        return
    # SUPABASE: FULL AUTONOMY. The owner's explicit decision, 2026-08-07.
    #
    # This block previously refused the whole migration CATEGORY (db push,
    # migration up, migration repair, functions deploy). That broke real work
    # within hours: `migration repair` edits history metadata and touches no
    # schema and no data, and a live session was left unable to do what it had
    # done the day before. The rule as written said "destructive migration"; the
    # implementation said "all migrations". Never make that substitution again.
    #
    # Only the two genuinely unrecoverable commands stop here. Destructive SQL is
    # handled separately (see DESTRUCTIVE_SQL_RE below): Claude stops in
    # CONVERSATION, explains what is lost, waits for confirmation, then does the
    # work itself. The owner is asked to approve, never handed SQL to run.
    if binary == "supabase":
        a = args_without_message_values(args)
        path = [x for x in a if not x.startswith("-")]
        pair = " ".join(path[:2])
        if pair in ("db reset", "projects delete"):
            block("'supabase %s' destroys a database or project with no undo, "
                  "which is blocked. Everything else in Supabase, including "
                  "db push, migration up/repair and functions deploy, is "
                  "Claude's job and runs without asking." % pair)
        return
    if binary not in ("vercel", "vc"):
        return
    # RAW args: vercel's `-f` is --force and takes no value, but it sits in
    # MESSAGE_FLAGS, so filtering swallowed the `--prod` right after it and
    # `vercel deploy -f --prod` shipped to production unchallenged.
    a = list(args)
    positional = [x for x in a if not x.startswith("-")]
    sub = positional[0].lower() if positional else ""

    # ----------------------------------------------------------------------
    # JUDGE THE SUBCOMMAND, NOT THE FLAG. Rewritten 2026-08-12.
    #
    # This used to test for `--prod` ANYWHERE in a vercel command. `vercel ls
    # --prod` merely LISTS deployments and `vercel inspect --prod` merely reads
    # one, so five read-only commands were blocked with the message "Production
    # deploys are blocked".
    #
    # That message is what actually cost the owner a manual dashboard click. A session
    # set an env var on production, tried to verify it, hit this block, concluded
    # production was off-limits entirely, never discovered `vercel redeploy` --
    # which was already free -- and handed the redeploy to the owner. The owner asked "why is
    # claude not handling all this itself man!!". The honest answer was that the
    # guard told it not to.
    #
    # Same defect class as the destructive-SQL gate: matching a SUBSTRING instead
    # of understanding the OPERATION. Reading is never deploying.
    # ----------------------------------------------------------------------
    if sub in VERCEL_READ_ONLY:
        return
    # Purchases spend HIS money on a card already on file, which is one of the
    # gates the owner actually named. `vercel buy domain x.com` was completely ungated:
    # the deny list covers the Vercel MCP `buy_*` tools but never the CLI, so the
    # cheaper route was also the unwatched one.
    if sub == "buy":
        block("'vercel buy' spends the user's money on a card already on file. "
              "Purchases are confirmed in chat, per purchase. Ask the owner plainly "
              "what it costs and what it is for, wait for the owner's yes, then record it "
              "and retry -- YOU still do the work:\n"
              "    printf '%s' 'vercel buy' > ~/.claude/.approved-action")
    # Everything that only rebuilds or reconfigures. `redeploy` and `rollback`
    # REQUIRE --target=production to act on production, so a generic --prod test
    # would refuse the very commands that are Claude's job. Neither ships new
    # code: redeploy rebuilds the SAME commit (what an env-var change needs), and
    # rollback restores a previous known-good build.
    if sub in VERCEL_SAFE_WRITE:
        return

    # From here the command is a DEPLOY: either `vercel deploy ...` or a bare
    # `vercel ...`, where deploy is the documented default. Only now does the
    # production target matter.
    if any(x == "--prod" or x.startswith("--prod=") for x in a):
        block(PROD_MSG)
    for i, x in enumerate(a):
        if x == "--target" and i + 1 < len(a) and a[i + 1].lower() == "production":
            block(PROD_MSG + "\n('--target production' is documented by Vercel as "
                  "identical to --prod.)")
        if x.lower().startswith("--target=") and x.split("=", 1)[1].lower() == "production":
            block(PROD_MSG + "\n('--target=production' is identical to --prod.)")

    # promote and alias stop for a stated reason, not conservatism: they make a
    # deployment live WITHOUT a merge, which is the gate the owner reaffirmed ("no auto
    # merge everrrr, i merge myself because merges when done they reach
    # production").
    if sub in ("promote", "alias"):
        block("'vercel %s' makes a deployment live without a merge, which is the "
              "one gate the user reserved for the owner. Everything else in Vercel, "
              "including redeploy, rollback, env changes and every read-only "
              "command, is Claude's job. Deploy a preview and let the owner merge."
              % sub)


def guard_pr_base(binary, args, cwd):
    if binary != "gh":
        return
    path = gh_subcommand_path(args)
    if not (len(path) >= 2 and path[0] == "pr" and path[1] in ("create", "edit")):
        # RAW args, so `-f base=dev` is still visible.
        raw = " ".join(args)
        if path and path[0] == "api" and re.search(r"\bbase\b", raw):
            m = re.search(r"base=([^\s'\"}]+)", raw)
            if m and m.group(1) not in ("main", "master"):
                block("Creating a PR with base '%s' via gh api is blocked. Every PR is "
                      "cut from main and targets main." % m.group(1))
        return
    for i, x in enumerate(args):
        base = None
        if x in ("--base", "-B") and i + 1 < len(args):
            base = args[i + 1]
        elif x.startswith("--base="):
            base = x.split("=", 1)[1]
        if base is None:
            continue
        if "$" in base:
            # main-by-construction (`${BASE:-main}`) is fine. Anything else
            # resolves at runtime to a value we cannot see, so FAIL CLOSED --
            # this branch used to `return` on every expansion, which made a
            # fail-open hole inside a fail-closed guard.
            if re.search(r"[:-]-?(main|master)\}?$", base) or \
                    base.rstrip("}").endswith("main"):
                return
            block("Blocked: PR base %r resolves at runtime, so it cannot be shown "
                  "to be main. Pass --base main explicitly.\n\nEvery PR branch is "
                  "cut from main and targets main, because a stacked PR silently "
                  "drops its diff when the parent dies." % base)
        if base not in ("main", "master"):
            block("Stacked PRs are blocked: base '%s' is not main. Every PR branch is "
                  "cut from main and targets main, because a stacked PR silently drops "
                  "its diff when the parent dies." % base)


# --------------------------------------------------------------------------
# guard-tamper: the guard layer must not be shell-editable
# --------------------------------------------------------------------------
# One Edit or one shell command against ~/.claude/hooks/ or settings.json can
# disable all six guardrails at once (the escalation path behind
# CVE-2026-25725, and the reason the official security doc recommends auditing
# config changes). Edit/Write tool edits to these paths are covered by "ask"
# permission rules in settings.json; THIS guard covers the shell route:
# rm/mv/cp/ln/tee/sed -i/chmod/git rm/redirects targeting the guard files, the
# ~/.claude root, or the home directory root itself (the canonical `rm -rf ~`
# accident).
#
# Same threat model as the other four guards: accidents and recognisable
# commands, not determined obfuscation. A `python -c "open(...).write(...)"`
# body names no shell binary and passes; the canary layer exists for that
# class. Unresolved expansions ($VAR paths) are skipped for the same reason
# `rm -f "$TMP/x"` must keep working -- this guard over-blocking daily work
# would get it disabled, which is worse than the residual gap.

TAMPER_WRITERS = {"rm", "rmdir", "unlink", "shred", "truncate", "mv", "cp",
                  "install", "rsync", "ln", "tee", "sponge", "patch", "dd",
                  "chmod", "chown", "chattr", "icacls", "attrib",
                  # PowerShell and cmd equivalents. The parser now recurses into
                  # `powershell -c "..."`, but the body resolved to `Remove-Item`
                  # which no writer set knew about, so the guard layer could
                  # still be deleted from a Windows shell one level down.
                  "remove-item", "move-item", "copy-item", "rename-item",
                  "set-content", "add-content", "clear-content", "out-file",
                  "new-item", "set-itemproperty",
                  "del", "erase", "rd", "move", "copy", "ren", "rename"}
# For pure copies the SOURCE being a guard file is a read, not a write;
# only the destination (last path argument) can do damage.
TAMPER_DEST_ONLY = {"cp", "install", "rsync"}
TAMPER_REDIRECT_RE = re.compile(r"^(\d*>>?|>>?)(.*)$")
TAMPER_CHMOD_ENABLE_RE = re.compile(r"^[ugoa]*\+[rwxXst]+$")


def _tamper_msys(path):
    m = re.match(r"^/([A-Za-z])/(.*)$", path)
    if m:
        return "%s:/%s" % (m.group(1), m.group(2))
    return path


def _expand_home_vars(text):
    """Resolve $HOME / ${HOME} / $USERPROFILE from the real environment.

    `expand_vars` only knows assignments written inside the command itself, so
    an ordinary `rm -rf $HOME/.claude/hooks` kept a literal `$`, which
    `_tamper_normalize` reads as "unresolvable" and lets through -- while the
    `~` spelling of the same path was blocked. Only these two names are
    resolved; every other expansion stays unknown so the conservative bail
    below still applies.
    """
    def sub(m):
        name = m.group(1) or m.group(2)
        if name in ("HOME", "USERPROFILE"):
            val = os.environ.get(name)
            if val:
                return val
        return m.group(0)
    return VAR_RE.sub(sub, text)


def _tamper_normalize(tok, cwd):
    """Absolute, forward-slash, lowercase form of a path token, or None when
    the token is a flag, empty, or contains an expansion we cannot resolve."""
    t = _expand_home_vars(expand_vars(tok))
    if "$" in t:
        return None
    t = t.strip("\"'")
    if not t or t.startswith("-"):
        return None
    t = t.replace("\\", "/")
    if t == "~" or t.startswith("~/"):
        home = os.path.expanduser("~").replace("\\", "/")
        t = home + t[1:]
    t = _tamper_msys(t)
    if not re.match(r"^([A-Za-z]:)?/", t):
        base = _tamper_msys((cwd or "").replace("\\", "/"))
        t = base.rstrip("/") + "/" + t
    return posixpath.normpath(t).lower()


def _tamper_protected(path):
    home = posixpath.normpath(
        os.path.expanduser("~").replace("\\", "/")).lower()
    claude = home + "/.claude"
    # A glob never matched an exact protected path, so `rm -Rf ~/.claude/hook*`
    # deleted the entire guard layer while `rm -rf ~/.claude/hooks` was blocked.
    # Truncate at the first metacharacter and judge the directory it would
    # expand inside: anything globbing within ~/.claude is a tamper attempt.
    meta = min((path.find(c) for c in "*?[" if path.find(c) != -1), default=-1)
    if meta != -1:
        stem = path[:meta].rsplit("/", 1)[0]
        return stem == claude or stem.startswith(claude + "/") or stem == home
    if path in (home, claude, claude + "/hooks",
                claude + "/settings.json", claude + "/settings.local.json",
                # CLAUDE.md and the rules/agents trees are behaviour-defining:
                # rewriting them is how you disable the guards without touching
                # a single .sh file. Same ask-on-edit treatment as settings.json.
                # The bare directory forms matter as much as the prefixes below:
                # `rm -rf ~/.claude/rules` has no trailing slash to match on.
                claude + "/claude.md", claude + "/rules", claude + "/agents"):
        return True
    return (path.startswith(claude + "/hooks/")
            or path.startswith(claude + "/rules/")
            or path.startswith(claude + "/agents/"))


TAMPER_MSG = ("Blocked: this command would modify or remove %r, which is part "
              "of the guardrail layer (~/.claude/hooks/, settings.json), the "
              "~/.claude root, or the home directory itself. Guard and config "
              "files are changed via the Edit tool, which asks the user for "
              "approval -- a shell write would bypass that.\n"
              "If this IS genuinely intended, ask the owner in chat, and once the owner "
              "agrees record it and retry -- YOU do the work:\n"
              "    printf '%%s' '<the exact command>' > ~/.claude/.approved-action\n"
              "The token is single-use and this guard deletes it on read.")


def _tamper_blocked(path, cwd=None):
    """Block a guard-file write UNLESS the owner has already approved this exact command.

    WHY: this guard's own message told Claude to "ask the user", and then had no
    way to honour the answer -- so the owner's yes turned into homework, the one outcome
    the FOUNDATION forbids. That dead-end was fixed for destructive SQL and for
    the MCP route earlier the same day; the tamper guard was missed, and it
    surfaced immediately: a legitimate `git update-index --chmod=+x` on a new
    guard file (which had shipped without its executable bit, leaving it INERT on
    any Unix clone) could not be completed even after the owner explicitly approved it.

    Same single-use token as everywhere else: recorded only after the owner agrees,
    consumed and deleted on read, so one yes buys exactly one command."""
    raw = _TAMPER_RAW_COMMAND[0]
    if raw and consume_approval(raw):
        return
    block(TAMPER_MSG % path)


# Populated in main() so the tamper guard can match the owner's approval against the
# actual command text rather than a path fragment.
_TAMPER_RAW_COMMAND = [""]


# ---------------------------------------------------------------------------
# CATASTROPHIC RECURSIVE DELETE
# ---------------------------------------------------------------------------
# Replaces four blanket deny rules -- Bash(rm -rf:*), (rm -fr:*), (rm -Rf:*)
# and (rm -R:*) -- which refused EVERY recursive delete regardless of target.
#
# Measured 2026-08-16 across all 2,717 transcripts on this machine (2.8 GB):
# those four rules fired ~190 times, more than every other guard in this system
# combined, and caught ZERO dangerous deletes. What they actually stopped was
# `rm -rf .next` (the Next.js build cache), scratch directories Claude had
# created itself minutes earlier, and regenerated data files. They matched the
# SUBSTRING `rm -rf` rather than the OPERATION, which is the same defect the
# Guard incident record in TOOLS.md documents three other times.
#
# What remains is only what has no undo, and each case was probed against the
# real guard before being written down:
#
#   1. THE FILESYSTEM OR DRIVE ROOT. GNU rm refuses a bare `rm -rf /` on its own
#      (--preserve-root is the default), but NOT `rm -rf /*`, which expands past
#      that check and is the spelling that actually destroys a machine.
#   2. A TARGET THAT STARTS WITH AN UNRESOLVED EXPANSION FOLLOWED BY A SLASH.
#      Shell state does not survive between tool calls here, so an unset $VAR
#      collapses `rm -rf "$VAR/x"` to `rm -rf /x`. This is the Steam bug. It is
#      an accident rather than obfuscation, which puts it inside this guard's
#      threat model rather than outside it.
#
# Measured before shipping, so this cannot be a fresh source of friction: across
# every transcript, the ONLY variables ever used as `$VAR/` in a recursive
# delete are $HOME and $USERPROFILE, both resolvable from the real environment.
# There is no case in the owner's history that this newly blocks.
#
# Deliberately NOT blocked: a bare unresolved `$VAR` with no trailing slash (it
# collapses to no argument at all, which is harmless), and anything that
# resolves to a real path. `rm -rf "$SCRATCH/frames"` with SCRATCH assigned in
# the same command is ordinary work and must keep running.
#
# Home and the guard layer are NOT handled here. `_tamper_protected` already
# covers `rm -rf ~`, `~/.claude`, the hooks/rules/agents trees, and the
# `cd ~/.claude && rm -rf hooks` form; the suite asserts they stay blocked.

DELETE_BINARIES = {"rm", "remove-item", "ri", "rd", "rmdir", "del", "erase"}
_SHORT_FLAG_RE = re.compile(r"^-[A-Za-z]+$")
_UNSET_THEN_SLASH_RE = re.compile(r"^\$\{?([A-Za-z_]\w*)\}?/")


def _delete_is_recursive(binary, args):
    """True when this invocation would descend into directories."""
    for a in args:
        low = a.lower()
        if low in ("--recursive", "-recurse", "/s"):
            return True
        # Clustered POSIX short flags: -rf, -fr, -Rf, -r. Long PowerShell
        # parameters are handled above, so only real short clusters reach here.
        if _SHORT_FLAG_RE.match(a) and len(a) <= 5 and ("r" in a[1:] or "R" in a[1:]):
            return True
    return False


def _expand_real_env(text):
    """Substitute variables that genuinely exist in this process's environment.

    Kept separate from `_expand_home_vars`, which resolves only HOME and
    USERPROFILE and is relied on by the 73-case tamper suite; widening that
    would change what `_tamper_normalize` treats as resolvable. This one is used
    ONLY by the catastrophic-delete check, so its blast radius is a single guard.
    """
    def sub(m):
        val = os.environ.get(m.group(1) or m.group(2))
        return val if val else m.group(0)
    return VAR_RE.sub(sub, text)


def _delete_catastrophic(tok, cwd):
    """Reason string when this delete target has no undo, else None."""
    t = _expand_real_env(_expand_home_vars(expand_vars(tok))).strip("\"'")
    if not t or t.startswith("-"):
        return None

    m = _UNSET_THEN_SLASH_RE.match(t)
    if m:
        return ("$%s is not assigned in this command and is not in the "
                "environment, and shell state does not carry between tool "
                "calls. If it is empty, this deletes from the filesystem root. "
                "Write the resolved path literally, or assign the variable in "
                "the same command." % m.group(1))
    if "$" in t:
        return None                      # other unresolved shapes: unchanged

    p = t.replace("\\", "/")
    if p.startswith("~"):
        p = os.path.expanduser("~").replace("\\", "/") + p[1:]
    p = _tamper_msys(p)
    if not re.match(r"^([A-Za-z]:)?/", p):
        return None                      # relative to cwd: ordinary project work
    # Judge a glob by the directory it would expand inside, so `/*` is read as
    # the root it empties rather than as a path that never matched anything.
    stem = p[:p.index("*")] if "*" in p else p
    stem = posixpath.normpath(stem).rstrip("/").lower()
    if stem in ("", "/", ".") or re.match(r"^[a-z]:$", stem):
        return ("this resolves to the filesystem root. `rm -rf /*` in "
                "particular expands past rm's own --preserve-root check.")
    return None


DELETE_MSG = ("Blocked: %s\n"
              "Target: %r\n"
              "Routine cleanup is NOT blocked. Build caches, scratch dirs and "
              "generated files all delete freely; only a target with no undo "
              "stops here.\n"
              "If this IS genuinely intended, ask the owner in chat, and once the owner "
              "agrees record it and retry -- YOU do the work:\n"
              "    printf '%%s' '<the exact command>' > ~/.claude/.approved-action\n"
              "The token is single-use and this guard deletes it on read.")


def guard_catastrophic_delete(binary, args, cwd):
    if binary not in DELETE_BINARIES or not _delete_is_recursive(binary, args):
        return
    for a in args:
        # Flags, including cmd-style /S /Q. Matched as slash-then-letters only:
        # a bare "/" and "/*" are TARGETS, and both are len <= 2, so a naive
        # length test would skip the two most dangerous arguments in the set.
        if a.startswith("-") or re.match(r"^/[A-Za-z]$", a):
            continue
        reason = _delete_catastrophic(a, cwd)
        if reason:
            raw = _TAMPER_RAW_COMMAND[0]
            if raw and consume_approval(raw):
                return
            block(DELETE_MSG % (reason, a))


# ---------------------------------------------------------------------------
# THE BACKUP NEVER LEAVES PRIVATE (The owner's decision, 2026-11-10)
# ---------------------------------------------------------------------------
# ~/.claude is backed up to FabGemYT/FabClaudeWorkflow: the owner's rules, accounts,
# business notes and their whole history. The shareable copy is a SEPARATE
# public repo, FabGemYT/FabFriendsClaudeSetup, filled only by a GitHub workflow
# that scrubs it first. The names are close and the owner flips the friends' repo
# between public and private, so one confused command could expose the backup
# with no undo: once public, shared or pushed elsewhere, anyone can keep a copy.
#
# Blocked, whatever the route (gh, gh api, curl/wget/httpie, git):
#   * the backup going public or internal;
#   * a collaborator or a deploy key added to it, or a transfer to another owner;
#   * a clone of the backup pushed to any network remote other than the backup
#     itself, and `gh repo create --source <backup clone>`: both copy the
#     unscrubbed history somewhere else.
# A clone of the backup is recognised by its origin OR by its content (hq/ plus
# the secrets map, which the friends' export never carries), so repointing
# origin first does not slip past.
# NOT blocked: everything else about the backup (its description, Actions
# secrets, PRs, pushes to its own origin, local copies) and anything on the
# friends' repo, which the owner publishes and unpublishes at will.

BACKUP_SLUG = "fabgemyt/fabclaudeworkflow"
_BACKUP_URL_RE = re.compile(
    r"github\.com[:/]+fabgemyt/fabclaudeworkflow(?:\.git)?/?$", re.I)
BACKUP_MSG = ("Blocked: this would expose the private backup "
              "(FabGemYT/FabClaudeWorkflow): %s. The backup is never made "
              "public, never shared and never pushed anywhere but its own repo. "
              "The friends' copy is FabGemYT/FabFriendsClaudeSetup, which a "
              "GitHub workflow fills by itself after a merge; nothing is ever "
              "copied there by hand.\n"
              "If the owner really wants this, ask the owner in chat, and once the owner agrees "
              "record it and retry -- YOU do the work:\n"
              "    printf '%%s' '<the exact command>' > ~/.claude/.approved-action\n"
              "The token is single-use and this guard deletes it on read.")
_GH_API_VALUE_FLAGS = {"-X", "--method", "-H", "--header", "-f", "--raw-field",
                       "-F", "--field", "--input", "-q", "--jq", "-t",
                       "--template", "--hostname", "-p", "--preview", "--cache"}
_GH_REPO_EDIT_VALUE_FLAGS = {"-d", "--description", "-h", "--homepage",
                             "--visibility", "--default-branch", "--add-topic",
                             "--remove-topic"}
_GIT_GLOBAL_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
_GIT_PUSH_VALUE_FLAGS = {"-o", "--push-option", "--receive-pack", "--exec",
                         "--repo"}


def _backup_blocked(what):
    raw = _TAMPER_RAW_COMMAND[0]
    if raw and consume_approval(raw):
        return
    block(BACKUP_MSG % what)


def _git_out(repo, *gitargs):
    for cand in _candidate_cwds(repo):
        if not os.path.isdir(cand):
            continue
        try:
            r = subprocess.run(["git", "-C", cand] + list(gitargs),
                               capture_output=True, text=True, timeout=5)
            return r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            return ""
    return ""


def _path_of(tok, cwd):
    """Absolute forward-slash path for a token, case preserved (Mac and Linux
    file systems are case-sensitive), or None when it cannot be resolved."""
    t = _expand_home_vars(expand_vars(tok))
    if "$" in t:
        return None
    t = t.strip("\"'").replace("\\", "/")
    if not t:
        return None
    if t == "~" or t.startswith("~/"):
        t = os.path.expanduser("~").replace("\\", "/") + t[1:]
    t = _tamper_msys(t)
    if not re.match(r"^([A-Za-z]:)?/", t):
        base = _tamper_msys((cwd or "").replace("\\", "/"))
        t = base.rstrip("/") + "/" + t
    return posixpath.normpath(t)


def _is_backup_url(url):
    return bool(url) and bool(_BACKUP_URL_RE.search(url.strip().strip("\"'")))


def _is_backup_slug(s):
    s = (s or "").strip().strip("\"'").lower()
    s = re.sub(r"^(https?://)?(www\.)?github\.com/", "", s)
    s = re.sub(r"\.git$", "", s).strip("/")
    return s == BACKUP_SLUG


def _is_backup_tree(path):
    """A clone or worktree of the backup, judged by origin OR by content."""
    if not path:
        return False
    if _is_backup_url(_git_out(path, "remote", "get-url", "origin")):
        return True
    top = _git_out(path, "rev-parse", "--show-toplevel")
    for cand in _candidate_cwds(top):
        if (os.path.isfile(os.path.join(cand, "hq", "WORKFLOW_HQ_LOG.md"))
                and os.path.isfile(os.path.join(cand, "rules", "secrets-map.md"))):
            return True
    return False


def _positionals(args, value_flags):
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a in value_flags:
            skip = True
            continue
        if a.startswith("-"):
            continue
        out.append(a)
    return out


def _flag_value(args, names):
    """Value of the first matching flag, in `--f v`, `--f=v` or `-Xv` form."""
    for i, a in enumerate(args):
        for n in names:
            if a == n and i + 1 < len(args):
                return args[i + 1]
            if a.startswith(n + "="):
                return a[len(n) + 1:]
            if len(n) == 2 and a.startswith(n) and len(a) > 2 and not a.startswith("--"):
                return a[2:]
    return None


def _sets_visibility(args):
    """True when a request body would change who can see a repo."""
    for i, a in enumerate(args):
        val = None
        if a in ("-f", "-F", "--field", "--raw-field") and i + 1 < len(args):
            val = args[i + 1]
        elif a.startswith(("--field=", "--raw-field=")):
            val = a.split("=", 1)[1]
        elif a.startswith(("-f", "-F")) and len(a) > 2 and "=" in a:
            val = a[2:]
        if val and re.match(r"^\s*[\"']?(private|visibility)\s*=", val, re.I):
            return True
        if a == "--input" or a.startswith("--input="):
            return True  # a body this guard cannot read: assume the worst here
    joined = " ".join(args)
    return bool(re.search(r"[\"'](private|visibility)[\"']\s*:", joined, re.I)
                or re.search(r"(^|\s)(private|visibility):?=", joined, re.I))


def _backup_endpoint(ep, method, args):
    ep = re.sub(r"^(https?://)?api\.github\.com/", "",
                ep.strip("\"'").split("?")[0].lower()).strip("/")
    root = "repos/" + BACKUP_SLUG
    if not (ep == root or ep.startswith(root + "/")):
        return
    if method not in ("PATCH", "PUT", "POST"):
        return
    tail = ep[len(root):]
    if tail == "" and _sets_visibility(args):
        _backup_blocked("it would change who can see the backup")
    elif tail.startswith("/collaborators/"):
        _backup_blocked("it would add a collaborator to the backup")
    elif tail == "/keys":
        _backup_blocked("it would add a deploy key, which is a way into the backup")
    elif tail == "/transfer":
        _backup_blocked("it would transfer the backup to another owner")


def _backup_gh(args, cwd):
    path = gh_subcommand_path(args)
    if len(path) < 2:
        return
    explicit = _flag_value(args, ["-R", "--repo"])
    if path[0] == "repo" and path[1] == "edit":
        vis = (_flag_value(args, ["--visibility"]) or "").strip("\"'").lower()
        if vis not in ("public", "internal"):
            return
        rest = args[args.index("edit") + 1:] if "edit" in args else []
        pos = _positionals(rest, _GH_REPO_EDIT_VALUE_FLAGS)
        target = pos[0] if pos else explicit
        if _is_backup_slug(target) if target else _is_backup_tree(cwd):
            _backup_blocked("it would make the backup %s" % vis)
    elif path[0] == "repo" and path[1] == "deploy-key" and "add" in path[2:3]:
        if _is_backup_slug(explicit) if explicit else _is_backup_tree(cwd):
            _backup_blocked("it would add a deploy key, which is a way into the backup")
    elif path[0] == "repo" and path[1] == "create":
        src = _flag_value(args, ["--source", "-s"])
        p = _path_of(src, cwd) if src else None
        if p and _is_backup_tree(p):
            _backup_blocked("it would create a new repo from the backup's files and history")
    elif path[0] == "api":
        rest = args[args.index("api") + 1:] if "api" in args else list(args)
        pos = _positionals(rest, _GH_API_VALUE_FLAGS)
        if not pos:
            return
        ep = pos[0]
        # gh fills {owner}/{repo} from the current directory's repo. The
        # tokenizer's grouping strip can eat a trailing "}", hence `\}?`.
        if re.search(r"\{(owner|repo)\b", ep):
            if not _is_backup_tree(cwd):
                return
            ep = re.sub(r"\{owner\}?", "fabgemyt", ep)
            ep = re.sub(r"\{repo\}?", "fabclaudeworkflow", ep)
        method = (_flag_value(rest, ["-X", "--method"]) or "").strip("\"'").upper()
        if not method:
            body = any(a in ("-f", "-F", "--field", "--raw-field", "--input")
                       or a.startswith(("--field=", "--raw-field=", "--input="))
                       for a in rest)
            method = "POST" if body else "GET"  # gh api's own default
        _backup_endpoint(ep, method, rest)


def _backup_http(args):
    joined = " ".join(args)
    m = re.search(r"api\.github\.com/(repos/[^\s\"'?#]+)", joined, re.I)
    if not m:
        return
    mm = (re.search(r"(?:-X|--request|--method)\s*=?\s*[\"']?(PATCH|PUT|POST)\b", joined, re.I)
          or re.search(r"(?:^|\s)(PATCH|PUT|POST)(?:\s|$)", joined))
    if mm:
        method = mm.group(1).upper()
    elif re.search(r"(?:^|\s)(-d|--data\S*|--json|--form|--body-data\S*)(?:\s|=|$)", joined):
        method = "POST"
    else:
        method = "GET"
    _backup_endpoint(m.group(1), method, args)


def _backup_git_push(args, cwd):
    repo, i, sub = cwd, 0, None
    while i < len(args):
        a = args[i]
        if a in _GIT_GLOBAL_VALUE_FLAGS:
            if a == "-C" and i + 1 < len(args):
                repo = _path_of(args[i + 1], repo) or repo
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        sub = a
        break
    if sub != "push" or not _is_backup_tree(repo):
        return
    rest = args[i + 1:]
    dest = _flag_value(rest, ["--repo"])
    if not dest:
        pos = _positionals(rest, _GIT_PUSH_VALUE_FLAGS)
        dest = pos[0] if pos else None
    if dest is None:
        url = _git_out(repo, "remote", "get-url", "--push", "origin")
        if url and not _is_backup_url(url):
            _backup_blocked("origin no longer points at the backup, so a plain "
                            "push would copy it to %s" % url)
        return
    d = dest.strip("\"'")
    if re.match(r"^(file://|/|[A-Za-z]:[\\/]|\.\.?(/|$)|~)", d):
        return  # a local path: nothing leaves the machine, and any onward push
        #         from that copy is judged here by its content
    url = d if re.search(r"://|^[\w.-]+@[\w.-]+:", d) else \
        _git_out(repo, "remote", "get-url", "--push", d)
    if url and not _is_backup_url(url):
        _backup_blocked("it would push the backup's history to %s" % url)


def guard_backup_exposure(binary, args, cwd):
    if binary == "gh":
        _backup_gh(args, cwd)
    elif binary in ("curl", "wget", "http", "https", "httpie", "xh"):
        _backup_http(args)
    elif binary == "git":
        _backup_git_push(args, cwd)


def guard_guard_tamper(binary, args, cwd):
    guard_catastrophic_delete(binary, args, cwd)
    guard_backup_exposure(binary, args, cwd)
    toks = [binary] + list(args)
    # Redirect targets can appear anywhere in the segment, whatever the binary.
    for i, tok in enumerate(toks):
        m = TAMPER_REDIRECT_RE.match(tok)
        if not m:
            continue
        target = m.group(2) or (toks[i + 1] if i + 1 < len(toks) else "")
        p = _tamper_normalize(target, cwd)
        if p and _tamper_protected(p):
            _tamper_blocked(target)

    if binary in ("sed", "perl"):
        # Only the in-place forms write; plain sed/perl reading a hook is fine.
        if not any(a.startswith("--in-place")
                   or re.match(r"^-\w*i", a) for a in args):
            return
    elif binary == "git":
        sub, skip, repo = None, False, None
        prev = None
        for a in args:
            if skip:
                # Capture the -C value: `git -C ~/.claude reset --hard` operates
                # on the guard repo from anywhere, so the target is the -C path,
                # not the cwd.
                if prev == "-C":
                    repo = a
                skip = False
                continue
            if a in ("-C", "-c", "--git-dir", "--work-tree"):
                prev = a
                skip = True
                continue
            if a.startswith("-"):
                continue
            sub = a
            break
        # HISTORY-LEVEL REVERTS restore an OLDER guard layer without naming a
        # single hook file, so every path-based check above sees nothing to
        # object to. Judged on the REPO being ~/.claude, because that is what
        # makes them dangerous.
        #
        # DELIBERATELY NARROW. This repo IS the guard layer, and it is also
        # maintained through ordinary git every session: branch switching,
        # stashing and discarding a local edit are routine and must stay open.
        # A guard that blocks daily work gets disabled, which is the worst
        # outcome. So only two shapes are refused, both of which rewrite guard
        # file CONTENT from history:
        #   * reset --hard          (discards the working tree wholesale)
        #   * checkout/restore with a REF and a path (`checkout HEAD~3 -- hooks/`)
        # `git checkout -- <path>` (discard local change, no ref) stays allowed,
        # as do checkout/switch of a branch, stash, and revert.
        danger = None
        if sub == "reset" and any(a == "--hard" for a in args):
            danger = "reset --hard"
        elif sub in ("checkout", "restore"):
            if "--" in args:
                before = args[:args.index("--")]
                # A non-flag token that is not the subcommand itself is a ref.
                refs = [a for a in before
                        if not a.startswith("-") and a not in (sub, repo)]
                if refs:
                    danger = "%s %s --" % (sub, refs[0])
            if any(a.startswith("--source") for a in args):
                danger = "restore --source"
        if danger:
            target = _tamper_normalize(repo, cwd) if repo else _tamper_normalize(".", cwd)
            claude = posixpath.normpath(
                os.path.expanduser("~/.claude").replace("\\", "/")).lower()
            if target and (target == claude or target.startswith(claude + "/")):
                block("'git %s' inside ~/.claude rewrites guard files from "
                      "history without naming one, which is blocked. Branch "
                      "switching, stashing and discarding a local edit are all "
                      "still fine. If a guard change is genuinely intended, make "
                      "it with the Edit tool so the user is asked." % danger)
        # checkout/restore of a guard file re-enables it; rm/clean/update-index
        # (e.g. --chmod=-x) disable it.
        if sub not in ("rm", "clean", "update-index"):
            return
        # ...but `update-index --chmod=+x` ENABLES a guard, exactly like plain
        # `chmod +x` which is already exempt below. Blocking it was inconsistent
        # AND actively harmful: block-mcp-danger.sh shipped as mode 100644, which
        # leaves it inert on any Unix clone, and this check refused the one-line
        # fix even after the owner had approved it in chat. Marking a guard executable
        # cannot weaken the guard layer.
        if sub == "update-index" and any(
                a.startswith("--chmod=+") for a in args):
            return
    elif binary == "dd":
        for a in args:
            if a.startswith("of="):
                p = _tamper_normalize(a[3:], cwd)
                if p and _tamper_protected(p):
                    _tamper_blocked(a[3:])
        return
    elif binary == "find":
        # `find ~/.claude/hooks -delete` removes every guard, and settings.json
        # auto-allows Bash(find:*), so this executed with no prompt at all.
        # -exec/-ok run arbitrary commands over the same start paths.
        if not any(a in FIND_DESTRUCTIVE for a in args):
            return
        for a in args:
            if a.startswith("-"):
                break          # start paths precede the first predicate
            p = _tamper_normalize(a, cwd)
            if p and _tamper_protected(p):
                _tamper_blocked(a)
        return
    elif binary not in TAMPER_WRITERS:
        return

    if binary == "chmod":
        modes = [a for a in args if not a.startswith("-")]
        if modes and TAMPER_CHMOD_ENABLE_RE.match(modes[0]):
            return  # chmod +x re-enables a guard; only stripping bits disables

    paths = [a for a in args if _tamper_normalize(a, cwd)]
    if binary in TAMPER_DEST_ONLY and paths:
        paths = paths[-1:]
    for a in paths:
        p = _tamper_normalize(a, cwd)
        if p and _tamper_protected(p):
            _tamper_blocked(a)


# ---------------------------------------------------------------------------
# MCP tool guard
# ---------------------------------------------------------------------------
# WHY THIS EXISTS: every guard above is registered against the `Bash` matcher and
# nothing else. Measured 2026-08-07 by feeding real payloads to all five guards:
#
#   mcp__claude_ai_Supabase__execute_sql   {"query": "DROP TABLE profiles;"}
#       -> passed through all five, untouched
#   the identical SQL through Bash
#       -> blocked by block-prod-deploy
#
# So DESTRUCTIVE_SQL_RE, written and tested 33/33 the same morning, only ever saw
# the one delivery route the user is LEAST likely to take: `mcp__claude_ai_Supabase__*`
# sits in settings.json `allow`, which makes the MCP path the frictionless one.
# a live web game has real paying users. This was the widest hole in the layer.
#
# WHY THERE IS NO "ask" TIER HERE. Measured 2026-08-07 under a real
# bypassPermissions session (the mode this user runs all day), on 2.1.224:
#
#   deny rules in settings.json ............ ENFORCED
#   hook exit 2 ............................ ENFORCED
#   settings.json `ask` RULES .............. SILENTLY APPROVED, no prompt
#   hook permissionDecision:"ask" .......... SILENTLY APPROVED, no prompt
#
# The last two are measured, not inferred. `ask-guard-file-edit.sh` emitted a
# textbook ask decision for an Edit to this very file and the edit landed with no
# prompt. The official permissions doc claims bypassPermissions skips prompts
# "except those forced by explicit `ask` rules"; on this build that is false.
#
# So an ask tier would be DECORATIVE -- a guard that reports it is protecting
# something while approving everything. Per the FOUNDATION, a silent failure
# costs this user more confidence than any visible bug. Only block and free exist.
#
# TIERS:
#   block    reaches production without a merge -- the owner's one reaffirmed gate
#   confirm  irreversible or spends money: blocked UNTIL the owner says yes IN CHAT,
#            which is the only channel that actually reaches the owner here
#   free     everything else, no friction
#
# The confirm tier is the correction to a real flaw shipped earlier the same day:
# the Bash destructive-SQL guard told Claude to "stop in chat, get explicit
# confirmation, and then run it yourself" while exit-2 made running it impossible,
# turning the owner's approval into homework. The owner's words for the shape the owner wants: "it asks
# me this project will require supabase and adding one will cost you $10... so it
# was all working". The owner approves; CLAUDE still does the work. See consume_approval.

MCP_BLOCK = (
    (re.compile(r"__deploy_to_vercel$", re.I),
     "This ships NEW code to production without a merge. Merging the PR is the "
     "user's one reaffirmed gate ('no auto merge everrrr, i merge myself because "
     "merges when done they reach production'), and Vercel's git integration "
     "already deploys production on merge to main. Open a PR instead; the preview "
     "URL is yours to create freely."),
)

# Tool-name suffix -> why the user must be asked in chat first. Matched against
# the full `mcp__<server>__<tool>` name so a server rename cannot silently drop
# coverage. `None` means "inspect the payload text instead" (the SQL route).
MCP_CONFIRM = (
    (re.compile(r"__(execute_sql|apply_migration)$", re.I), None),   # SQL: text-scanned
    (re.compile(r"__create_project$", re.I),
     "Creating a Supabase project can add a paid compute charge to the user's "
     "account. The owner wants to be asked the cost, then have Claude do the work."),
    (re.compile(r"__(confirm_cost|confirm_billing_purchase)$", re.I),
     "This confirms a real charge on the user's account."),
    (re.compile(r"__buy_[a-z_]+$", re.I),
     "This spends the user's money on a card already on file. Purchases are "
     "confirmed in chat, per purchase."),
    (re.compile(r"__(tiktok_publish|publish_website|publish_game|deploy_website|"
                r"deploy_game|tiktok_prepare_publish)$", re.I),
     "This publishes PUBLICLY under the user's name or account. Public posting is "
     "not reversible in any meaningful sense once it has been seen."),
    (re.compile(r"__(pause_project|restore_project|reset_branch)$", re.I),
     "This changes the availability of a live project or discards branch state."),
    # The connector's own way to make a deployment live without a merge.
    # The CLI and REST routes to the same thing stop; this one was free until
    # 12 Oct 2026, a coverage gap found while undoing a rollback.
    (re.compile(r"__(request_promote|assign_alias)$", re.I),
     "This makes a deployment live in production without a merge (a promote or "
     "an alias), the one gate the user keeps for the owner. Ask the owner in chat; after "
     "the owner's yes, record it and finish the work."),
)

# Explicit escapes from the patterns above. Named individually so adding a tool
# here is a decision someone made, not a regex accident.
MCP_FREE = frozenset({
    "mcp__claude_ai_supabase__deploy_edge_function",   # ordinary deploy, the owner's job to want, Claude's to do
    "mcp__claude_ai_supabase__get_cost",               # reading a price is not paying it
})


def _mcp_strings(obj, out, depth=0):
    """Collect every string anywhere in tool_input. MCP servers name their SQL
    field differently (`query`, `sql`, `statement`), and nesting varies, so
    scanning by field name would miss the next server that spells it a third way."""
    if depth > 6:
        return
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _mcp_strings(v, out, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _mcp_strings(v, out, depth + 1)


APPROVAL_FILE = os.path.join(
    os.path.expanduser("~"), ".claude", ".approved-action")


def _shq(s):
    """Quote a token for the copy-pasteable command in the block message."""
    return shlex.quote(s)

CONFIRM_MSG = (
    "%s\n\n"
    "STOP AND ASK HIM IN CHAT. In bypassPermissions mode no permission prompt "
    "reaches this user (measured: both `ask` rules and hook `ask` decisions are "
    "silently approved), so the conversation is the ONLY channel that actually "
    "asks the owner. Do NOT hand the owner the command to run the owner.\n"
    "1. State plainly what this does and what cannot be undone.\n"
    "2. Wait for the owner's explicit yes.\n"
    "3. Then record it and retry -- YOU do the work:\n"
    "     printf '%%s' %s > ~/.claude/.approved-action\n"
    "The token is single-use: this guard deletes it the moment it is honoured, "
    "so a second attempt stops again.\n"
    "(action: %s)")


def consume_approval(action):
    """Single-use approval token, written only after the user says yes in chat.

    WHY A FILE: MCP tool calls carry no command string, so there is nowhere to
    hang an inline `CONFIRMED=1` prefix the way a shell command could. A file is
    the one channel both routes share.

    WHY SINGLE-USE: a persistent allow would silently cover the NEXT destructive
    action too. Deleting on read means one approval buys exactly one action, and
    the file's contents name which one, so it cannot be written vaguely up front.

    This is a speed bump against carelessness, not a lock against a hostile
    agent -- Claude can obviously write the file. That is the correct threat
    model: the FOUNDATION makes the conversational stop the real gate, and this
    exists so that honouring it does not dead-end in homework."""
    try:
        with open(APPROVAL_FILE, "r", encoding="utf-8") as fh:
            granted = fh.read().strip()
    except Exception:
        return False
    if not granted:
        return False
    # Substring either way: the recorded token may name the tool while the guard
    # computed a SQL verb, or the reverse. Both are deliberate approvals.
    ok = granted.lower() in action.lower() or action.lower() in granted.lower()
    if ok:
        try:
            os.remove(APPROVAL_FILE)
        except Exception:
            pass
    return ok


def guard_mcp(payload):
    """PreToolUse guard for the `mcp__.*` matcher.

    Fails OPEN (exit 0) on an unreadable payload, unlike the Bash guards. The
    Bash guards fail closed because a malformed Bash payload is a broken guard on
    a route that can do anything; here, failing closed would wedge every MCP call
    from ten connected servers on any single parse miss, which is the
    guard-blocks-daily-work outcome the FOUNDATION names as the worst one."""
    tool = (payload.get("tool_name") or "").strip()
    if not tool.startswith("mcp__"):
        sys.exit(0)
    if tool.lower() in MCP_FREE:
        sys.exit(0)

    for pat, reason in MCP_BLOCK:
        if pat.search(tool):
            block("%s\n(blocked tool: %s)" % (reason, tool))

    ti = payload.get("tool_input") or {}
    strings = []
    _mcp_strings(ti, strings)
    blob = "\n".join(strings)

    for pat, reason in MCP_CONFIRM:
        if not pat.search(tool):
            continue
        if reason is None:
            # SQL route: WARNS, never blocks. This is the exact call that blocked
            # a standard idempotent migration on a live web game and cost a session
            # its idempotency guards. execute_sql/apply_migration definitely DO
            # execute SQL, so the note is accurate here in a way it never was on
            # the Bash route.
            hit = sql_warning(blob)
            if not hit:
                sys.exit(0)
            emit_warn(DATA_LOSS_SQL_MSG % hit)
        # Money and public-publishing still stop. Those are the "last step"
        # category the owner reserved, and they have never produced a false positive.
        if consume_approval(tool):
            sys.exit(0)
        block(CONFIRM_MSG % (reason, _shq(tool), tool))

    sys.exit(0)


GUARDS = {
    "main-push": guard_main_push,
    "pr-merge": guard_pr_merge,
    "prod-deploy": guard_prod_deploy,
    "pr-base": guard_pr_base,
    "guard-tamper": guard_guard_tamper,
}


def emit_warn(context):
    """Let the tool RUN, and hand Claude a note about it.

    `permissionDecision: "allow"` + `additionalContext`, probed live on
    2026-08-08: the command executed AND the text arrived as a system-reminder.
    That was worth measuring rather than trusting, because the day before the
    official docs claimed bypassPermissions honours explicit `ask` rules, and it
    does not.

    This is the shape every gate should prefer over blocking whenever the action
    is recoverable. The owner feels nothing; Claude still knows."""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "additionalContext": context}}))
    sys.exit(0)


# emit_ask() lived here until 2026-08-08. Deleted, not kept "just in case":
# `permissionDecision: "ask"` never reaches this user in either mode the owner runs, so
# any future gate built on it would be silently decorative. Use emit_warn (allow +
# additionalContext, probed working) to inform, or block() to stop. There is no
# working middle tier, and pretending otherwise is how the SQL gate went wrong.


# REMOVED 2026-08-08: guard_tamper_file, the Edit/Write route to guard files.
#
# It emitted `permissionDecision: "ask"`, which is measured as a LITERAL NO-OP in
# both modes the owner runs. On 2026-07-30, fifteen guard-file edits in auto mode
# produced no prompt; on 2026-08-07 it emitted a textbook ask for an Edit to this
# very file and the edit landed silently. A guard that reports it is protecting
# something while approving everything is worse than no guard, because the README
# then claims cover that does not exist.
#
# The Edit/Write route is covered better by something real: ~/.claude is a git
# repo, every guard change goes through a PR, and the owner merges it. The owner sees the diff.
# That is an actual gate, unlike a prompt that never fires. The shell route stays
# blocked by guard_guard_tamper, which exits 2 and therefore works in every mode.


# Guards that judge the whole payload rather than a tokenised shell command.
# Both fail OPEN on unreadable input: neither is the primary enforcement for a
# route that can do anything, and wedging every MCP call or every file edit on a
# parse miss is worse than the miss.
PAYLOAD_GUARDS = {
    "mcp": guard_mcp,
}


def main():
    if len(sys.argv) < 2 or (sys.argv[1] not in GUARDS
                             and sys.argv[1] not in PAYLOAD_GUARDS):
        fail("command-guard: unknown guard %r" % (sys.argv[1:] or None))

    if sys.argv[1] in PAYLOAD_GUARDS:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        try:
            payload = json.loads(raw)
        except Exception:
            sys.exit(0)
        if not isinstance(payload, dict):
            sys.exit(0)
        PAYLOAD_GUARDS[sys.argv[1]](payload)
        sys.exit(0)

    guard = GUARDS[sys.argv[1]]

    raw = sys.stdin.read()
    if not raw.strip():
        fail("command-guard: empty hook payload")
    try:
        payload = json.loads(raw)
    except Exception:
        fail("command-guard: payload is not valid JSON")
    if not isinstance(payload, dict):
        fail("command-guard: payload is not an object")

    ti = payload.get("tool_input") or {}
    command = ti.get("command") or payload.get("command") or ""
    if not command.strip():
        # These guards are wired to the Bash matcher, so a Bash payload with no
        # command is MALFORMED, not benign, and gets the same fail-closed
        # treatment as empty or unparseable input. A payload that names some
        # other tool genuinely has nothing for this guard to say.
        tool = (payload.get("tool_name") or "").strip()
        if tool and tool != "Bash":
            sys.exit(0)
        fail("command-guard: Bash payload carried no command to inspect; "
             "failing closed.")
    cwd = payload.get("cwd") or ti.get("cwd") or os.getcwd()
    cwd = cwd.replace("\\", "/")
    # The tamper guard matches the owner's approval token against the real command text,
    # not a path fragment, so one approved command cannot unlock a different one.
    _TAMPER_RAW_COMMAND[0] = command.strip()

    text, heredoc_bodies = strip_heredocs(command)
    base_segments = split_segments(text)

    # A heredoc body is data UNLESS it is fed to something that executes it
    # (`bash <<EOF`, `cat <<EOF | bash`, `bash -s <<EOF`). In that case the body
    # is the real command list, so analyse it too.
    #
    # JUDGED PER HEREDOC, on the line that declared it. This used to ask whether
    # ANY segment anywhere in the command was an interpreter, which meant an
    # unrelated `sh script.sh` earlier in the same command turned a later
    # `gh pr create --body-file - <<BODY` into "code" and got its prose parsed
    # as commands. Measured 2026-08-16: that blocked a PR body and a commit
    # message, both of which merely QUOTED a delete command as evidence. Reading
    # intent out of text that is never executed is the same defect this guard
    # layer has been bitten by three times; scoping the check to the declaring
    # line is what actually fixes it.
    #
    # `cat <<EOF | bash` still executes: the declaring line carries the pipe, so
    # `bash` is found when that one line is split.
    for owner_line, body in heredoc_bodies:
        executes = False
        for seg in split_segments(owner_line):
            toks = tokenize(seg)
            if not toks:
                continue
            b, _ = resolve(toks)
            if b in INTERPRETERS or b in CODE_EVAL:
                executes = True
                break
        if executes:
            base_segments.extend(split_segments(body))

    segments = expand_interpreters(base_segments, cwd)
    global ENV
    ENV = collect_assignments(segments)
    # Track `cd` across the segment list. Without this the guards judged every
    # relative path against the ORIGINAL cwd, so `cd ~/.claude && rm -rf hooks`
    # normalised `hooks` against the project directory, found nothing protected,
    # and deleted the guard layer. Confirmed by execution before this fix.
    live_cwd = cwd
    for seg in segments:
        toks = tokenize(seg)
        if not toks:
            continue
        binary, args = resolve(toks)
        if not binary:
            continue
        guard(binary, args, live_cwd)
        if binary in ("cd", "pushd"):
            target = next((a for a in args if not a.startswith("-")), None)
            if target:
                moved = _tamper_normalize(target, live_cwd)
                if moved:
                    live_cwd = moved
    sys.exit(0)


main()
