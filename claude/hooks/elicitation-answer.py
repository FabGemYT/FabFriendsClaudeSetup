"""Answer one recurring MCP form on the user's behalf: Supabase's SQL confirmation.

WHY THIS FILE EXISTS
--------------------
Supabase's hosted MCP server (the "claude.ai Supabase" connector) asks for
confirmation before execute_sql / apply_migration whenever the SQL looks
destructive (DROP, DELETE, TRUNCATE, UPDATE without WHERE). It can only ask
when the client says it can show forms, and Claude Code started saying so with
the 2026-07-28 protocol revision (2.1.292 to 2.1.295). From then on every such
statement stopped the session with an Accept / Decline dialog (8 October 2026).

The owner settled how destructive SQL on the owner's own projects is handled on
2026-08-07/08 (FOUNDATION, "Supabase specifically"): it runs, and Claude names
it to the owner in chat in one line. block-mcp-danger.sh already posts that note on
the same call. So this hook answers the duplicate dialog and nothing else.

WHAT IT ANSWERS, AND WHAT IT LEAVES TO THE DIALOG
-------------------------------------------------
Accepts only when ALL of these hold:
  - the event is an Elicitation in form mode from a server whose name
    contains "supabase";
  - the message is the SQL confirmation (it talks about SQL, a query or a
    migration);
  - the message does not mention money (cost, charge, credits, billing, a
    paid plan). Supabase also uses forms for create_project / create_branch
    cost confirmations, and spending stays the owner's button;
  - every field in the requested form is a boolean, or the form has no
    fields. Anything else (free text, a choice we cannot read) is left to the
    dialog.

Everything else prints nothing, so the normal dialog appears. A crash prints
nothing too: the hook can only ever fail towards the dialog, never towards a
silent answer.

Each answer is appended to ~/.claude/state/elicitation-answers.log so the
harness review can count them.

Contract: stdin = hook JSON; stdout = hookSpecificOutput JSON or nothing;
exit 0 always (exit 2 would DECLINE the request, which is never wanted here).
"""
import json
import os
import re
import sys
import time

SQL_RE = re.compile(r"\b(sql|query|migration)\b", re.I)
MONEY_RE = re.compile(
    r"\b(cost|costs|charge|charged|charges|credit|credits|billing|billed|invoice|"
    r"price|pricing|paid plan|per month|per hour|usd)\b|/month|/hour|\$\s?\d", re.I)
LOG = os.environ.get("ELICITATION_ANSWERS_LOG") or os.path.join(
    os.path.expanduser("~"), ".claude", "state", "elicitation-answers.log")


def decide(payload):
    """Return the content dict to accept with, or None to leave it to the dialog."""
    if not isinstance(payload, dict):
        return None
    if payload.get("hook_event_name") != "Elicitation":
        return None
    server = str(payload.get("mcp_server_name") or "")
    if "supabase" not in server.lower():
        return None
    if (payload.get("mode") or "form") != "form":
        return None
    message = str(payload.get("message") or "")
    if not SQL_RE.search(message):
        return None
    if MONEY_RE.search(message):
        return None
    schema = payload.get("requested_schema") or {}
    props = schema.get("properties") if isinstance(schema, dict) else None
    if not props:
        return {}
    if not isinstance(props, dict):
        return None
    content = {}
    for name, spec in props.items():
        if not isinstance(spec, dict) or spec.get("type") != "boolean":
            return None
        content[name] = True
    return content


def log_answer(payload, content):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write("%s\t%s\t%s\t%s\n" % (
                time.strftime("%Y-%m-%dT%H:%M:%S"),
                payload.get("mcp_server_name", ""),
                json.dumps(content, sort_keys=True),
                re.sub(r"\s+", " ", str(payload.get("message", "")))[:160]))
    except Exception:
        pass


def main():
    try:
        payload = json.loads(sys.stdin.read() or "null")
    except Exception:
        return 0
    content = decide(payload)
    if content is None:
        return 0
    out = {"hookSpecificOutput": {"hookEventName": "Elicitation",
                                  "action": "accept", "content": content}}
    sys.stdout.write(json.dumps(out))
    log_answer(payload, content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
