"""Secret-leak scanner for the block-secret-leak.sh PreToolUse hook.

Reads a Write/Edit/MultiEdit/NotebookEdit/Bash tool payload on stdin.

CONTRACT (matches the hook's exit-code convention):
  exit 2 + reason on stderr  -> block the write
  exit 0                     -> no opinion, let the edit proceed

Best-effort by design: it FAILS OPEN (exit 0) on any parse or lookup problem so
it can never block a legitimate edit. It blocks when a high-confidence
live-secret pattern appears in content being written, or in a Bash command.

SCOPE, stated precisely because it was previously documented wrong: this does
NOT test whether the target file is git-tracked -- there is no `git ls-files`
call anywhere here. It scans EVERY path except an explicit exemption list
(`.env*`, `*.pem`, `*.key`, `.credentials*`, `/.secrets/`, `~/.claude/secrets/`),
so the normal "Claude wires my secrets into .env.local and the key store"
workflow is never interrupted, and everything else is checked regardless of
tracked status. The matched value is redacted in the reason.
"""
import sys
import json
import re


def no_opinion():
    sys.exit(0)


def block(reason):
    sys.stderr.write(reason + "\n")
    sys.exit(2)


try:
    payload = json.loads(sys.stdin.read())
except Exception:
    no_opinion()

ti = payload.get("tool_input") or {}
path = (ti.get("file_path") or ti.get("path") or "").replace("\\", "/").lower()
base = path.rsplit("/", 1)[-1]

# Secrets belong in these files; do not scan them.
#
# These are matched PRECISELY, not as substrings. The old version used
# `".env" in path`, which exempted ordinary source files like
# `src/config/.environment.ts` and `app/config.env.ts`, and `"/secrets/" in path`
# exempted `src/secrets/keys.ts` -- a completely normal source directory name.
# A too-broad exemption is worse than no exemption: it is a silent hole in the
# one guard that stops a live credential entering tracked source.
if (base == ".env"                     # exactly .env
        or base.startswith(".env.")    # .env.local, .env.production
        or base.startswith(".env-")    # .env-local
        or base.endswith(".pem")
        or base.endswith(".key")
        or base.startswith(".credentials")
        or "/.secrets/" in path        # dot-prefixed only, not any src/secrets/
        # The documented key store is `~/.claude/secrets/` (no dot). Anchoring on
        # the full `.claude/secrets/` path keeps that exempt without re-opening
        # the broad `/secrets/` hole that would also exempt `src/secrets/`.
        or "/.claude/secrets/" in path):
    no_opinion()

parts = []
if ti.get("content"):
    parts.append(str(ti["content"]))
if ti.get("new_string"):
    parts.append(str(ti["new_string"]))
for edit in (ti.get("edits") or []):
    if isinstance(edit, dict) and edit.get("new_string"):
        parts.append(str(edit["new_string"]))
# Notebook cell writes carry their payload under a different key.
if ti.get("new_source"):
    parts.append(str(ti["new_source"]))
# Bash is scanned too. The Write/Edit tools were the only covered channel, so
# `printf '<key>' >> tracked.ts` or `curl -d '<key>' ...` wrote or exfiltrated a
# live secret with the scanner never invoked. A literal secret in a shell command
# also lands in the transcript, which is its own leak. Legitimate commands
# reference credentials as $VARS (load-env exports them), not as literals, so
# this costs nothing in practice.
if ti.get("command"):
    parts.append(str(ti["command"]))
text = "\n".join(parts)
if not text:
    no_opinion()

# Not preceded by a word character. Without this, a token pattern hiding in the
# middle of an ordinary identifier matches: many common snake_case prefixes end
# in the letters r-e, so the following underscore and a long camelCase run used
# to read as a Resend key. That fired on real source constantly.
NB = r"(?<![A-Za-z0-9_])"

patterns = [
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private-key"),
    (NB + r"AKIA[0-9A-Z]{16}", "aws-access-key-id"),
    (NB + r"sk_live_[0-9a-zA-Z]{16,}", "stripe-live-secret"),
    (NB + r"rk_live_[0-9a-zA-Z]{16,}", "stripe-live-restricted"),
    (NB + r"ghp_[0-9A-Za-z]{36}", "github-pat"),
    (NB + r"gho_[0-9A-Za-z]{36}", "github-oauth-token"),
    (NB + r"github_pat_[0-9A-Za-z_]{60,}", "github-pat-fine-grained"),
    (NB + r"xox[baprs]-[0-9A-Za-z-]{12,}", "slack-token"),
    # Real Resend keys have TWO segments: the prefix, an id, then the secret.
    # The old single-segment pattern could never match a real key at all, while
    # matching ordinary identifiers. Requiring both segments fixes both halves.
    (NB + r"re_[A-Za-z0-9]{6,}_[A-Za-z0-9]{20,}", "resend-api-key"),
    (NB + r"sk-ant-[A-Za-z0-9_\-]{20,}", "anthropic-api-key"),
    (NB + r"sk-proj-[A-Za-z0-9_\-]{20,}", "openai-project-key"),
    (NB + r"sk-or-v1-[0-9a-f]{32,}", "openrouter-api-key"),
    (NB + r"sbp_[0-9a-f]{40}", "supabase-access-token"),
    (NB + r"AIza[0-9A-Za-z_\-]{35}", "google-api-key"),
    # Added after an audit confirmed these formats were all false negatives.
    (NB + r"ASIA[0-9A-Z]{16}", "aws-temp-access-key-id"),
    (NB + r"gh[sur]_[0-9A-Za-z]{36}", "github-server-user-refresh-token"),
    (NB + r"whsec_[0-9A-Za-z]{24,}", "stripe-webhook-secret"),
    (NB + r"sb_secret_[0-9A-Za-z_\-]{20,}", "supabase-secret-key"),
    (NB + r"glpat-[0-9A-Za-z_\-]{20,}", "gitlab-pat"),
    (NB + r"SG\.[0-9A-Za-z_\-]{20,}\.[0-9A-Za-z_\-]{20,}", "sendgrid-api-key"),
    (NB + r"npm_[0-9A-Za-z]{36}", "npm-access-token"),
    (NB + r"hf_[0-9A-Za-z]{30,}", "huggingface-token"),
    (NB + r"SK[0-9a-f]{32}", "twilio-api-key"),
    (NB + r"AC[0-9a-f]{32}", "twilio-account-sid"),
    (NB + r"dop_v1_[0-9a-f]{64}", "digitalocean-token"),
    (NB + r"shpat_[0-9a-f]{32}", "shopify-access-token"),
    (NB + r"sk-[A-Za-z0-9]{48}", "openai-legacy-key"),
    # A connection string with an inline password is a credential regardless of
    # scheme. The password group requires 6+ chars so `postgres://user@host`
    # and `redis://localhost` do not match.
    (r"(?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis|amqp)://"
     r"[^\s:/@]+:[^\s:/@]{6,}@", "connection-string-password"),
    # Added 2026-08-07: three of this user's OWN live credentials had trivially
    # matchable prefixes and were invisible to the scanner, which is the worst
    # kind of gap. Google OAuth client secrets sit in mobile-app, the Sentry
    # auth token in a live web game, and the RevenueCat v2 key is account-level.
    (NB + r"GOCSPX-[A-Za-z0-9_\-]{20,}", "google-oauth-client-secret"),
    (NB + r"sntry[su]_[A-Za-z0-9_=\-]{40,}", "sentry-auth-token"),
    (NB + r"sk_[A-Za-z0-9]{25,}", "revenuecat-or-generic-secret-key"),
]


def jwt_is_secret(token):
    """True only for a SERVICE-ROLE JWT.

    A Supabase anon/publishable key is also a JWT and is designed to be public;
    it belongs in docs and test fixtures. Blocking every JWT flagged those and
    advised hiding a key that is meant to be shared. Only the service-role key
    is actually dangerous, so decode the payload and check for that claim.
    """
    try:
        import base64
        seg = token.split(".")[1]
        seg += "=" * (-len(seg) % 4)
        body = base64.urlsafe_b64decode(seg).decode("utf-8", "replace")
        return "service_role" in body
    except Exception:
        return False


jwt_re = re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}")
for _m in jwt_re.finditer(text):
    if jwt_is_secret(_m.group(0)):
        patterns.insert(0, (re.escape(_m.group(0)), "supabase-service-role-jwt"))
        break

for pattern, name in patterns:
    match = re.search(pattern, text)
    if match:
        value = match.group(0)
        redacted = (value[:6] + "***") if len(value) > 9 else "***"
        block(
            "block-secret-leak: this write contains what looks like a live secret ("
            + name + ": " + redacted + "). Never write a secret value into a tracked "
            "file. Put it only in .env.local (gitignored) plus the encrypted remote "
            "store, and reference it by name. If this is a false positive (a redacted "
            "example or a public test key), move it to a .env file or tell the user."
        )

no_opinion()
