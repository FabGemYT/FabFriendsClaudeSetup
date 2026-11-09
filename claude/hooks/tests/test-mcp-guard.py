"""The MCP route, which every other blocking guard is blind to.

WHY THIS FILE EXISTS
--------------------
On 2026-08-07, hours after DESTRUCTIVE_SQL_RE shipped with a green 33/33 suite,
a probe replayed real payloads through all five blocking guards:

    mcp__claude_ai_Supabase__execute_sql  {"query": "DROP TABLE profiles;"}
        -> passed all five, untouched
    the identical SQL through Bash
        -> blocked by block-prod-deploy

Every guard was registered against `matcher: "Bash"` and nothing else. The SQL
gate only ever watched the route the user was LEAST likely to take, because
`mcp__claude_ai_Supabase__*` sits in settings.json `allow`, making MCP the
frictionless path. a live web game has real paying users.

The lesson is not "add MCP cases". It is that a guard's COVERAGE is a separate
question from its LOGIC, and the logic suite cannot see a coverage gap. This file
tests coverage.

ALSO MEASURED THAT DAY, and the reason this guard blocks instead of asking:
under a real bypassPermissions session on 2.1.224, settings.json `ask` rules AND
hook `permissionDecision: "ask"` are BOTH silently approved with no prompt. Only
`deny` rules and hook exit 2 actually stop anything. An ask tier here would
report protection while approving everything.

Run:  py -3 test-mcp-guard.py
"""
import json
import os
import subprocess
import sys

HOOKS = os.path.expanduser("~/.claude/hooks")
GUARD = os.path.join(HOOKS, "block-mcp-danger.sh")
APPROVAL = os.path.expanduser("~/.claude/.approved-action")

# Built at runtime so this file's own invocation command never carries the
# literal, which the Bash guard text-matches and would block.
DROP = " ".join(["DROP", "TABLE"]) + " profiles;"
TRUNC = " ".join(["TRUNCATE", "TABLE"]) + " events;"
DISABLE_RLS = "alter table profiles " + " ".join(["disable", "row", "level", "security"]) + ";"

BLOCK, FREE, WARN = "BLOCK", "FREE", "WARN"

# The idempotent replace idiom, which is what actually blocked the owner in production.
REPLACE = (" ".join(["drop", "policy"]) + " if exists fb_ins on public.feedback; "
           "create policy fb_ins on public.feedback for insert with check (true);")

CASES = [
    # --- SQL now WARNS, never blocks (rewritten 2026-08-08) ----------------
    # These were BLOCK until the measurements came in: 3 of the 4 guard blocks
    # that ever touched a real product were this check, all false positives.
    # execute_sql/apply_migration genuinely do execute SQL, so a note is accurate
    # here -- but a note, not a wall.
    (WARN, "supabase execute_sql drop table",
     "mcp__claude_ai_Supabase__execute_sql", {"query": DROP}),
    (WARN, "supabase execute_sql truncate",
     "mcp__claude_ai_Supabase__execute_sql", {"query": TRUNC}),
    (WARN, "supabase execute_sql disable RLS",
     "mcp__claude_ai_Supabase__execute_sql", {"query": DISABLE_RLS}),
    (WARN, "supabase apply_migration drop table",
     "mcp__claude_ai_Supabase__apply_migration",
     {"name": "cleanup", "query": DROP}),
    # nested / differently-named SQL field: servers spell it three ways
    (WARN, "sql nested under a list",
     "mcp__claude_ai_Supabase__execute_sql",
     {"statements": [{"sql": DROP}]}),
    # THE REGRESSION CASE. This exact shape blocked a real a live web game
    # migration and cost it its idempotency guards. It must be completely silent.
    (FREE, "the idempotent RLS migration that got blocked",
     "mcp__claude_ai_Supabase__execute_sql", {"query": REPLACE}),

    # --- production without a merge ----------------------------------------
    (BLOCK, "vercel deploy_to_vercel",
     "mcp__claude_ai_Vercel__deploy_to_vercel", {"target": "production"}),
    # The connector's promote and alias were free until 12 Oct 2026 while the
    # CLI and REST routes to the same outcome stopped.
    (BLOCK, "vercel request_promote",
     "mcp__claude_ai_Vercel__request_promote", {"deploymentId": "dpl_x"}),
    (BLOCK, "vercel assign_alias",
     "mcp__claude_ai_Vercel__assign_alias", {"alias": "example.com"}),
    (FREE, "vercel request_rollback stays Claude's (it restores a known build)",
     "mcp__claude_ai_Vercel__request_rollback", {"deploymentId": "dpl_x"}),

    # --- money -------------------------------------------------------------
    (BLOCK, "vercel buy_domain", "mcp__claude_ai_Vercel__buy_domain",
     {"name": "example.com"}),
    (BLOCK, "vercel buy_pro", "mcp__claude_ai_Vercel__buy_pro", {}),
    (BLOCK, "vercel buy_credits", "mcp__claude_ai_Vercel__buy_credits", {}),
    (BLOCK, "supabase create_project (the '$10?' case)",
     "mcp__claude_ai_Supabase__create_project", {"name": "newproj"}),
    # The publish/billing family is matched by TOOL NAME, not by vendor, so these
    # fixtures deliberately use a server that is not connected. The gate has to
    # hold for whatever media or hosting service is wired up next, and testing it
    # against a live connector would silently start passing for the wrong reason
    # the day that connector is removed. (Higgsfield was removed on 2026-08-14;
    # these cases must keep passing regardless.)
    (BLOCK, "any server: confirm_billing_purchase",
     "mcp__claude_ai_SomeMediaService__confirm_billing_purchase", {}),

    # --- public publishing under the owner's name ----------------------------------
    (BLOCK, "any server: tiktok_publish",
     "mcp__claude_ai_SomeMediaService__tiktok_publish", {"id": "x"}),
    (BLOCK, "any server: publish_website",
     "mcp__claude_ai_SomeMediaService__publish_website", {}),
    (BLOCK, "any server: publish_game",
     "mcp__claude_ai_SomeMediaService__publish_game", {}),
    (BLOCK, "any server: deploy_website",
     "mcp__claude_ai_SomeMediaService__deploy_website", {}),

    # --- availability of a live project ------------------------------------
    (BLOCK, "supabase pause_project",
     "mcp__claude_ai_Supabase__pause_project", {}),

    # =======================================================================
    # ROUTINE MCP WORK -- every one of these MUST stay free. This half is the
    # point: the guard that blocks daily work gets disabled.
    # =======================================================================
    (FREE, "additive DDL via execute_sql",
     "mcp__claude_ai_Supabase__execute_sql",
     {"query": "create table if not exists foo (id uuid primary key)"}),
    (FREE, "add column via execute_sql",
     "mcp__claude_ai_Supabase__execute_sql",
     {"query": "alter table profiles add column bar text"}),
    (FREE, "bulk UPDATE (The owner's other sessions do this)",
     "mcp__claude_ai_Supabase__execute_sql",
     {"query": "update profiles set nsfw_enabled = true"}),
    (FREE, "plain select",
     "mcp__claude_ai_Supabase__execute_sql",
     {"query": "select count(*) from profiles"}),
    (FREE, "create policy is additive",
     "mcp__claude_ai_Supabase__execute_sql",
     {"query": "create policy p on profiles for select using (true)"}),
    (FREE, "false positive: a column named truncated_at",
     "mcp__claude_ai_Supabase__execute_sql",
     {"query": "select truncated_at from logs"}),
    (FREE, "ordinary migration",
     "mcp__claude_ai_Supabase__apply_migration",
     {"name": "add_bar", "query": "alter table profiles add column bar text"}),
    (FREE, "edge function deploy", "mcp__claude_ai_Supabase__deploy_edge_function",
     {"name": "api"}),
    (FREE, "list tables", "mcp__claude_ai_Supabase__list_tables", {}),
    (FREE, "get advisors", "mcp__claude_ai_Supabase__get_advisors", {}),
    (FREE, "generate types", "mcp__claude_ai_Supabase__generate_typescript_types", {}),
    (FREE, "reading a price is not paying it",
     "mcp__claude_ai_Supabase__get_cost", {"type": "project"}),
    (FREE, "vercel list deployments", "mcp__claude_ai_Vercel__list_deployments", {}),
    (FREE, "vercel runtime logs", "mcp__claude_ai_Vercel__get_runtime_logs", {}),
    (FREE, "vercel check domain price (read-only)",
     "mcp__claude_ai_Vercel__check_domain_availability_and_price", {"name": "x.com"}),
    (FREE, "any server: generate_image",
     "mcp__claude_ai_SomeMediaService__generate_image", {}),
    (FREE, "any server: generate_video",
     "mcp__claude_ai_SomeMediaService__generate_video", {}),
    (FREE, "sentry search issues", "mcp__sentry__search_issues", {}),
    (FREE, "posthog exec", "mcp__posthog__exec", {"query": "select 1"}),
    (FREE, "shadcn add", "mcp__shadcn__get_add_command_for_items", {}),
    (FREE, "context7 docs", "mcp__context7__query-docs", {}),
    (FREE, "gmail create_draft is not sending",
     "mcp__claude_ai_Gmail__create_draft", {"to": "a@b.com"}),
    (FREE, "chrome screenshot", "mcp__chrome-devtools__take_screenshot", {}),
]


def run(tool, ti):
    payload = json.dumps({"tool_name": tool, "tool_input": ti,
                          "cwd": "~/projects/a live web game",
                          "permission_mode": "bypassPermissions"})
    p = subprocess.run(["bash", GUARD], input=payload,
                       capture_output=True, text=True)
    return p.returncode, (p.stderr or "").strip()


def outcome(tool, ti):
    """BLOCK / WARN / FREE. WARN is allow + additionalContext: the tool RUNS and
    Claude gets a note. Distinguishing it from FREE is the point of the rewrite --
    a warn that silently became a block would be the exact regression."""
    rc, _ = run(tool, ti)
    if rc == 2:
        return BLOCK
    payload = json.dumps({"tool_name": tool, "tool_input": ti,
                          "cwd": "~/projects/a live web game",
                          "permission_mode": "bypassPermissions"})
    p = subprocess.run(["bash", GUARD], input=payload,
                       capture_output=True, text=True)
    out = (p.stdout or "").strip()
    if out:
        try:
            hso = json.loads(out).get("hookSpecificOutput", {})
            if hso.get("permissionDecision") == "allow" and hso.get("additionalContext"):
                return WARN
        except Exception:
            return WARN
    return FREE


def main():
    if os.path.exists(APPROVAL):
        os.remove(APPROVAL)

    print("=" * 78)
    print("MCP GUARD COVERAGE")
    print("=" * 78)
    fails = []
    for want, label, tool, ti in CASES:
        got = outcome(tool, ti)
        ok = got == want
        if not ok:
            fails.append((label, want, got, tool))
        print("   %-4s %-5s %-46s" % ("ok" if ok else "FAIL", want, label))

    # --- the approval token: single-use, and it must actually work ----------
    # SQL no longer participates: it warns rather than blocks, so there is
    # nothing to approve. The token now covers only the categories that DO stop,
    # which are money and public publishing -- the "last step" work the owner reserved.
    print("\n" + "-" * 78)
    print("APPROVAL TOKEN (The owner's yes must let CLAUDE do the work, not become homework)")
    print("-" * 78)
    tok_fails = []
    BUY = "mcp__claude_ai_Vercel__buy_pro"

    rc, _ = run(BUY, {})
    if rc != 2:
        tok_fails.append("a purchase was not blocked before approval")
    print("   %-4s blocked before approval" % ("ok" if rc == 2 else "FAIL"))

    with open(APPROVAL, "w", encoding="utf-8") as fh:
        fh.write(BUY)
    rc, _ = run(BUY, {})
    if rc != 0:
        tok_fails.append("approval token did not unblock the work")
    print("   %-4s allowed after the owner's approval" % ("ok" if rc == 0 else "FAIL"))

    rc, _ = run(BUY, {})
    if rc != 2:
        tok_fails.append("token was NOT single-use -- it covered a second action")
    print("   %-4s single-use: second attempt blocked again" % ("ok" if rc == 2 else "FAIL"))

    if os.path.exists(APPROVAL):
        os.remove(APPROVAL)

    # a token for one action must not unlock a different one
    with open(APPROVAL, "w", encoding="utf-8") as fh:
        fh.write(BUY)
    rc, _ = run("mcp__claude_ai_SomeMediaService__tiktok_publish", {"id": "x"})
    if rc != 2:
        tok_fails.append("a buy_pro token unlocked a public post")
    print("   %-4s a token for one action does not unlock another"
          % ("ok" if rc == 2 else "FAIL"))
    if os.path.exists(APPROVAL):
        os.remove(APPROVAL)

    # --- the SAME token must work on the guard-tamper route ----------------
    # It did not, at first. That guard's message said "ask the user" and then had
    # no way to honour the answer, so an approved `git update-index --chmod=+x` on
    # a guard file could not be completed even after the owner said yes. The new guard
    # had shipped without its executable bit, which leaves it INERT on any Unix
    # clone, so this was blocking a real fix to a real silent failure.
    print("\n" + "-" * 78)
    print("APPROVAL TOKEN, guard-tamper route")
    print("-" * 78)
    tamper = os.path.join(HOOKS, "block-guard-tamper.sh")
    # DELETING a guard file is the destructive shape, and the one the token is
    # for. `git update-index --chmod=+x` is deliberately NOT used here any more:
    # marking a guard executable ENABLES it, exactly like plain `chmod +x` which
    # was always exempt, so it is now free and needs no approval. Blocking it was
    # inconsistent and had actively refused the fix for a guard that shipped
    # non-executable (and therefore inert on every Unix clone).
    cmd = "rm -f ~/.claude/hooks/block-mcp-danger.sh"

    def tamper_rc(command):
        payload = json.dumps({"tool_name": "Bash",
                              "tool_input": {"command": command},
                              "cwd": os.path.expanduser("~/.claude").replace("\\", "/"),
                              "permission_mode": "bypassPermissions"})
        return subprocess.run(["bash", tamper], input=payload,
                              capture_output=True, text=True).returncode

    if os.path.exists(APPROVAL):
        os.remove(APPROVAL)
    rc = tamper_rc(cmd)
    if rc != 2:
        tok_fails.append("guard-file write was NOT blocked without approval")
    print("   %-4s blocked without approval" % ("ok" if rc == 2 else "FAIL"))

    with open(APPROVAL, "w", encoding="utf-8") as fh:
        fh.write(cmd)
    rc = tamper_rc(cmd)
    if rc != 0:
        tok_fails.append("approved guard-file write was still blocked")
    print("   %-4s allowed after the owner's approval" % ("ok" if rc == 0 else "FAIL"))

    rc = tamper_rc(cmd)
    if rc != 2:
        tok_fails.append("guard-tamper token was not single-use")
    print("   %-4s single-use: second attempt blocked again" % ("ok" if rc == 2 else "FAIL"))

    # A token for one command must not unlock a DIFFERENT guard-file write.
    with open(APPROVAL, "w", encoding="utf-8") as fh:
        fh.write(cmd)
    rc = tamper_rc("rm -f ~/.claude/hooks/block-main-push.sh")
    if rc != 2:
        tok_fails.append("one delete token unlocked deleting a different guard file")
    print("   %-4s a token for one command does not unlock another"
          % ("ok" if rc == 2 else "FAIL"))
    if os.path.exists(APPROVAL):
        os.remove(APPROVAL)

    # Marking a guard executable must need NO approval: it enables the guard.
    # This is the case that could not be fixed even after the owner approved it.
    rc = tamper_rc("git update-index --chmod=+x hooks/block-mcp-danger.sh")
    if rc != 0:
        tok_fails.append("`update-index --chmod=+x` still blocked; it ENABLES a guard")
    print("   %-4s chmod +x on a guard is free (it enables it)"
          % ("ok" if rc == 0 else "FAIL"))

    print("\n" + "=" * 78)
    total = len(CASES)
    print("SUMMARY: %d/%d coverage cases, %d/9 token cases"
          % (total - len(fails), total, 9 - len(tok_fails)))
    if fails or tok_fails:
        for label, want, got, tool in fails:
            print("  [%s] wanted %s, got %s  (%s)" % (label, want, got, tool))
        for t in tok_fails:
            print("  [token] %s" % t)
        sys.exit(1)
    print("\nALL CLEAN")


main()
