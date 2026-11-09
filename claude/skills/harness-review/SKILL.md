---
name: harness-review
description: Periodic check of this Claude Code harness against what shipped and what actually happened in recent sessions. Use when the owner asks to update, review, modernise or check the harness, asks what changed in Claude Code, or says prompts, denials or usage limits feel worse. Measures first (transcripts, health, audits), then lists no-brainers, optional changes and things to leave alone. Never changes anything by itself.
---

# Harness review

The owner decided on 10 October 2026 that the owner will not chase every new tool. Instead this
review runs every few weeks, or whenever something feels off, and the owner picks from a short
list. The review MEASURES before it suggests, and it never edits the harness on its own.

## Steps

1. **Measure the sessions.** Run the scanner. It reads every transcript touched since the
   last review and prints: classifier denials by reason, usage-limit stops, MCP forms this
   harness answered, the largest context each session reached, compactions, and which
   Claude Code build each session ran on.

       py -3 ~/.claude/skills/harness-review/scripts/review.py

   Add `--since YYYY-MM-DD` to override the window. Pass `--mark` at the very end, after
   the report is written, to record today's date and the installed version in
   `~/.claude/state/harness-review.json` so the next run knows where to start.

2. **Read what shipped.** Fetch the Claude Code changelog
   (https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md) for every
   version above the one recorded in the state file. Keep only bullets that touch: auto
   mode, permissions, hooks, CLAUDE.md or rules, skills, memory, compaction, models or
   effort, MCP and connectors, Windows. Ignore IDE, telemetry and enterprise bullets.

3. **Run the built-in audits in a session.** `/doctor prompt-audit` for stale or
   contradictory instruction files, `/skill-doctor` for skills that cost context and are
   never used, and `/health` for the guard suites. Headless (`claude -p`) runs of the
   first two need `MSYS_NO_PATHCONV=1` under Git Bash, which in turn breaks the Python
   hooks for that run; read their reports, ignore their hook complaints.

4. **Verify before claiming.** For every candidate change that depends on a Claude Code
   feature, confirm the key or flag exists in the installed binary (Law 5) and read the
   current docs page, not a memory of it.

5. **Write the list for the owner**, in plain words, three buckets:
   - **No-brainers**: documented, reversible, fixes something the scanner measured.
   - **Optional**: real but small; the owner's call.
   - **Leave alone**: things that look new but change nothing for how the owner works.
   End with numbered yes/no questions. The owner merges; nothing is applied before the owner answers.

## What this review is not

- Not a scheduled job. It never runs on its own, so it never spends usage unattended.
- Not a reason to add tools. Decision 8 of the harness plan still holds: measure before
  adding, measure again after shipping.
- Not an excuse to grow CLAUDE.md. A lesson goes to a path-scoped rule or a runbook.
