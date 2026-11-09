"""Supabase's SQL confirmation form is answered; everything else reaches the dialog.

WHY THIS FILE EXISTS
--------------------
On 2026-10-08 the owner had to press Accept on every destructive-looking
statement a live web game's session sent through the claude.ai Supabase connector:
Supabase's hosted MCP server started asking for confirmation (a form
elicitation) once Claude Code advertised form support. The owner had already decided
on 2026-08-07/08 that destructive SQL on the owner's own projects runs with a one-line
note in chat, which block-mcp-danger.sh posts on the same call. The hook under
test answers that one form and nothing else.

The cases replay payloads through the SHELL WRAPPER, not just the Python, so
the wiring (resolver, script path, stdout contract) is tested along with the
decision. ANSWER means the hook printed an accept with the expected content.
DIALOG means it printed nothing, so Claude Code shows the normal prompt.

Run:  py -3 test-elicitation-answer.py
Env:  HOOK_UNDER_TEST=/path/to/answer-supabase-sql-confirm.sh to test a staged copy.
"""
import json
import os
import subprocess
import sys

HOOKS = os.path.expanduser("~/.claude/hooks")
HOOK = os.environ.get("HOOK_UNDER_TEST") or os.path.join(HOOKS, "answer-supabase-sql-confirm.sh")

SQL_MSG = ("This SQL includes destructive operations (DROP, DELETE, TRUNCATE or UPDATE "
           "without WHERE). It may permanently remove data, tables, schemas or other objects.\n"
           "Apply the migration to project edsirhcunhlyjbljedpw?")
EXEC_MSG = ("This SQL includes destructive operations (DROP, DELETE, TRUNCATE or UPDATE "
            "without WHERE). Execute the query on project zjyayvokakaxzgxgjxma?")
COST_MSG = ("Creating this project will cost $10 per month and will be charged to your "
            "organization. Create project store-app?")
BRANCH_MSG = "Creating a branch costs $0.01344 per hour. Create the branch?"

ANSWER, DIALOG = "ANSWER", "DIALOG"


def payload(server="claude.ai Supabase", message=SQL_MSG, mode="form", schema=None,
            event="Elicitation", **extra):
    p = {"session_id": "t", "transcript_path": "/x.jsonl", "cwd": "/x",
         "hook_event_name": event, "mcp_server_name": server, "message": message}
    if mode is not None:
        p["mode"] = mode
    if schema is not None:
        p["requested_schema"] = schema
    p.update(extra)
    return json.dumps(p)


BOOL_SCHEMA = {"type": "object", "properties": {"confirm": {"type": "boolean", "title": "Confirm"}}}
TEXT_SCHEMA = {"type": "object", "properties": {"reason": {"type": "string", "title": "Reason"}}}
MIXED_SCHEMA = {"type": "object", "properties": {"confirm": {"type": "boolean"},
                                                  "note": {"type": "string"}}}

CASES = [
    (ANSWER, "the exact dialog from the photo, empty form", payload(), {}),
    (ANSWER, "same form with one boolean field", payload(schema=BOOL_SCHEMA), {"confirm": True}),
    (ANSWER, "execute_sql wording", payload(message=EXEC_MSG, schema=BOOL_SCHEMA), {"confirm": True}),
    (ANSWER, "mode missing defaults to form", payload(mode=None), {}),
    (ANSWER, "server name in a different case", payload(server="claude.ai SUPABASE"), {}),
    (DIALOG, "create_project cost confirmation stays the owner's", payload(message=COST_MSG, schema=BOOL_SCHEMA), None),
    (DIALOG, "create_branch cost confirmation stays the owner's", payload(message=BRANCH_MSG, schema=BOOL_SCHEMA), None),
    (DIALOG, "url-mode request (edge function secret sign-in)", payload(mode="url", url="https://supabase.com/x", message="Open the browser to set the secret"), None),
    (DIALOG, "a free-text field we cannot read", payload(schema=TEXT_SCHEMA), None),
    (DIALOG, "a form mixing boolean and text", payload(schema=MIXED_SCHEMA), None),
    (DIALOG, "another server with SQL in the message", payload(server="claude.ai Vercel"), None),
    (DIALOG, "a Supabase message that is not about SQL", payload(message="Please provide your username", schema=TEXT_SCHEMA), None),
    (DIALOG, "ElicitationResult event, not ours to answer", payload(event="ElicitationResult"), None),
    (DIALOG, "malformed payload", "{not json", None),
    (DIALOG, "empty stdin", "", None),
]


def run(stdin):
    # Replayed answers must not land in the real log the harness review counts.
    env = dict(os.environ, ELICITATION_ANSWERS_LOG=os.devnull)
    r = subprocess.run(["bash", HOOK], input=stdin, capture_output=True, text=True, timeout=60, env=env)
    return r.returncode, r.stdout.strip()


def main():
    if not os.path.exists(HOOK):
        print("SUMMARY: hook not found at %s" % HOOK)
        return 2
    good = 0
    for want, name, stdin, content in CASES:
        code, out = run(stdin)
        if code != 0:
            print("FAIL  %-48s exit %d (must always be 0)" % (name, code)); continue
        if want == DIALOG:
            ok = out == ""
            detail = "printed nothing" if ok else "printed %r" % out[:80]
        else:
            try:
                d = json.loads(out)["hookSpecificOutput"]
                ok = d["hookEventName"] == "Elicitation" and d["action"] == "accept" and d["content"] == content
            except Exception:
                ok = False
            detail = "accept %s" % json.dumps(content) if ok else "got %r" % out[:80]
        print("%s  %-48s %s" % ("ok  " if ok else "FAIL", name, detail))
        good += ok
    print("SUMMARY: %d/%d cases correct" % (good, len(CASES)))
    return 0 if good == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
