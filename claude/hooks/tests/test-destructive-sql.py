"""Destructive-SQL: this gate WARNS, it never blocks.

REWRITTEN 2026-08-08. The previous version asserted BLOCKING, and the blocking
version was measured wrong in production.

WHY IT CHANGED
--------------
Across 283 transcripts and 19 projects there had been 24 real guard blocks ever.
Four touched an actual product, and THREE OF THOSE FOUR were this gate -- all
three false positives on a live web game (`drop policy`, `drop policy`,
`drop function`). It fired 8 times total and never once caught anything real. It
also blocked a command that was only READING a file, because the words appeared
inside a Python string literal.

The damage was not just interruption. A session stripped the idempotency guards
out of a real migration to get past it, then wrote this gate's own error text into
the codebase as a design rationale. A guard that makes the code worse has negative
value.

Three specific defects:
  1. The verb list was invented. `drop policy|index|trigger|function|type`
     destroy NO data. Atlas, Squawk and Prisma all flag exactly DROP TABLE /
     DROP COLUMN / RENAME COLUMN / TRUNCATE.
  2. No idempotency awareness. Postgres has no `CREATE POLICY IF NOT EXISTS`, so
     `drop policy if exists X; create policy X` is THE documented re-runnable
     idiom. The gate treated the standard idiom as an attack.
  3. It could not tell executing SQL from text about SQL.

And its message was false: it claimed "IRREVERSIBLE ... Supabase has no
down-migrations", while all five projects are on Supabase PRO with WAL-G daily
backups (verified against the Management API).

THE CONTRACT NOW
----------------
  WARN  -- real data loss. The command RUNS; Claude gets a note and can raise it
           in conversation, which is the only channel that reaches the owner anyway.
  QUIET -- everything else, including the entire replace-an-object family.

Nothing in this file may BLOCK. A block here is a regression.

Run:  py -3 test-destructive-sql.py
"""
import json
import os
import subprocess
import sys

HOOK = os.path.expanduser("~/.claude/hooks/block-prod-deploy.sh")
CWD = "~/projects/a live web game"

# Real data loss -> warn (and still run).
WARN = [
    ("drop-table", "psql -c 'DROP TABLE profiles'"),
    ("drop-column", "psql -c 'ALTER TABLE profiles DROP COLUMN nsfw_enabled'"),
    ("drop-schema", "psql -c 'DROP SCHEMA public CASCADE'"),
    ("drop-database", "psql -c 'DROP DATABASE app'"),
    ("truncate", "psql -c 'TRUNCATE TABLE sessions'"),
    ("truncate-bare", "psql -c 'TRUNCATE profiles'"),
    ("disable-rls", "psql -c 'ALTER TABLE profiles DISABLE ROW LEVEL SECURITY'"),
    # The false NEGATIVE the old pattern missed entirely while producing eight
    # false positives: this wipes every row.
    ("delete-no-where", "psql -c 'DELETE FROM profiles'"),
    ("delete-no-where-semicolon", "psql -c 'DELETE FROM profiles;'"),
    # The danger is the STATEMENT, not the tool carrying it.
    ("supabase-cli-drop", "supabase db execute --sql 'DROP TABLE profiles'"),
]

# Ordinary work. Every one of these MUST be silent -- no warn, no block.
QUIET = [
    # --- the exact family that caused all three production false positives ---
    ("drop-policy", 'psql -c \'DROP POLICY "users read own" ON profiles\''),
    ("drop-function", "psql -c 'DROP FUNCTION increment_turn_count'"),
    ("drop-trigger", "psql -c 'DROP TRIGGER t ON profiles'"),
    ("drop-index", "psql -c 'DROP INDEX idx_foo'"),
    ("drop-type", "psql -c 'DROP TYPE mood'"),
    ("drop-constraint", "psql -c 'ALTER TABLE t DROP CONSTRAINT fk'"),
    ("alter-policy", "psql -c 'ALTER POLICY p ON profiles USING (true)'"),
    # --- the idempotent replace idiom: the only re-runnable form Postgres has ---
    ("replace-policy",
     "psql -c 'DROP POLICY IF EXISTS p ON t; CREATE POLICY p ON t FOR SELECT USING (true)'"),
    ("replace-index",
     "psql -c 'DROP INDEX IF EXISTS i; CREATE INDEX i ON t(a)'"),
    ("replace-table-temp",
     "psql -c 'DROP TABLE IF EXISTS tmp_x; CREATE TABLE tmp_x (id int)'"),
    # --- ordinary DDL and DML ---
    ("create-table", "psql -c 'CREATE TABLE IF NOT EXISTS foo (id uuid)'"),
    ("add-column", "psql -c 'ALTER TABLE profiles ADD COLUMN bar text'"),
    ("create-policy", "psql -c 'CREATE POLICY p ON t FOR SELECT USING (true)'"),
    ("enable-rls", "psql -c 'ALTER TABLE t ENABLE ROW LEVEL SECURITY'"),
    ("update-rows", "psql -c 'UPDATE profiles SET nsfw_enabled = true'"),
    ("delete-with-where", "psql -c 'DELETE FROM profiles WHERE id = 1'"),
    ("select", "psql -c 'SELECT count(*) FROM profiles'"),
    # --- false positives on TEXT, not SQL. Defect 3, which blocked a script
    #     whose only job was rewriting a migration file. ---
    ("python-rewrites-a-file",
     "python -c \"s=s.replace('drop policy if exists x','create policy x')\""),
    ("grep-for-the-words", "grep -c 'drop table' supabase/migrations/x.sql"),
    ("commit-message-mentions-it",
     "git commit -m 'refactor: stop using DROP TABLE in the seed script'"),
    ("column-named-truncated-at", "psql -c 'SELECT truncated_at FROM logs'"),
    ("prose-about-dropped-rows", "echo 'we dropped connections during the outage'"),
    # --- routine Supabase, which must never warn ---
    ("supabase-db-push", "supabase db push --linked"),
    ("supabase-migration-up", "supabase migration up"),
    ("supabase-functions-deploy", "supabase functions deploy api"),
]


def run(cmd):
    """Return ('block'|'warn'|'quiet', detail)."""
    payload = json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": cmd},
                          "cwd": CWD,
                          "permission_mode": "bypassPermissions"})
    p = subprocess.run(["bash", HOOK], input=payload,
                       capture_output=True, text=True)
    if p.returncode == 2:
        return "block", (p.stderr or "").strip().splitlines()[0][:70]
    out = (p.stdout or "").strip()
    if out:
        try:
            d = json.loads(out)
            hso = d.get("hookSpecificOutput", {})
            if hso.get("permissionDecision") == "allow" and hso.get("additionalContext"):
                return "warn", hso["additionalContext"][:60]
        except Exception:
            return "warn", out[:60]
    return "quiet", ""


def main():
    fails = []
    print("=" * 80)
    print("MUST WARN (real data loss) -- and must still RUN")
    print("=" * 80)
    for label, cmd in WARN:
        got, detail = run(cmd)
        ok = got == "warn"
        if not ok:
            fails.append((label, "warn", got))
        print("   %-5s %-28s %s" % ("ok" if ok else "FAIL", label, got))

    print()
    print("=" * 80)
    print("MUST BE SILENT (ordinary work; friction here is the whole bug)")
    print("=" * 80)
    for label, cmd in QUIET:
        got, detail = run(cmd)
        ok = got == "quiet"
        if not ok:
            fails.append((label, "quiet", got))
        print("   %-5s %-28s %s%s"
              % ("ok" if ok else "FAIL", label, got,
                 ("  <- " + detail) if not ok else ""))

    # Nothing in this file may block. Stated separately because it is the
    # single property the rewrite exists to guarantee.
    blocks = [f for f in fails if f[2] == "block"]

    print()
    print("=" * 80)
    total = len(WARN) + len(QUIET)
    print("SUMMARY: %d/%d correct (%d warn, %d silent)"
          % (total - len(fails), total, len(WARN), len(QUIET)))
    if blocks:
        print("\nREGRESSION: this gate BLOCKED %d case(s). It must never block."
              % len(blocks))
    if fails:
        for label, want, got in fails:
            print("   [%s] wanted %s, got %s" % (label, want, got))
        sys.exit(1)
    print("\nALL CLEAN")


main()
