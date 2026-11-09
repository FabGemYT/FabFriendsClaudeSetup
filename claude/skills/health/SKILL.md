---
name: health
description: Runs the ~4-minute system health check that catches silent failures in the ~/.claude setup - wrong or alias model ids, dead or missing guard hooks, a 200k window masquerading as 1M, missing python or poppler, a dirty backup repo, broken gh auth. Use when the user runs /health, asks "is everything working", "is my system healthy", "what's secretly broken", or after any session that behaved strangely. Report-only; changes nothing.
---

# health

One command, about four minutes, every silent-failure point this system has actually
been bitten by. Report-only: it never fixes, never gates, never writes.

## Run

```bash
bash ~/.claude/skills/health/scripts/health.sh
```

## Present the result

Show the OK/WARN/FAIL lines as-is (they are already one line per check with
the blast radius named), then:

- For every **FAIL**: give the one-line fix, and offer to apply it. The fix for
  a missing hook is `git -C ~/.claude checkout -- hooks/`; for missing poppler
  it is `scoop install poppler`; for a broken settings.json it is comparing
  against `git -C ~/.claude show origin/main:settings.json`.
- For every **WARN**: one sentence on whether it is expected right now (e.g. a
  Fable model warning during a deliberate Fable session is fine; the same
  warning on a fresh daily session is not).
- If everything is OK: say so in one line and stop. No elaboration.

## What the checks mean (context for interpreting, not for reciting)

- **model**: the saved default in settings.json. The expected daily driver is
  `claude-opus-5-5[1m]`. Bare aliases (`opus`, `sonnet`) have resolved to OLDER
  models on this machine before (opus[1m] -> Opus 4.8); Fable as the saved
  default burns Max usage roughly 5x faster than Opus. NOTE: the running
  session's model can differ from the file (the statusline is the truth for
  the current session; the file is the truth for tomorrow's sessions).
- **session window**: the harness exports `CLAUDE_CODE_AUTO_COMPACT_WINDOW`
  while a 1M window is live. Absent + no "(1M context)" in the statusline
  means this session is running a 200k window.
- **guards**: runs the live guard-tamper suite (74 cases), not just a
  file-exists check. A guard that exists but answers wrongly is a FAIL here
  and nowhere else.
- **backup lock**: proves the private backup (FabGemYT/FabClaudeWorkflow)
  cannot be made public, shared, or pushed to another repo, while work on the
  public friends' copy (FabGemYT/FabFriendsClaudeSetup) still runs.
- **friends' copy**: whether the last automatic update of the friends' copy
  (the share-to-friends workflow, after a harness merge) passed its privacy
  scan and tests. A FAIL means friends did not get that change, and nothing
  personal went out either: the workflow publishes only when every check is
  green.
- **pdf**: poppler went missing for two months once and no session on the
  machine could read PDFs; everyone blamed their own session.
- **secrets map**: cross-checks `rules/secrets-map.md` against disk in both
  directions (documented-but-missing = FAIL, present-but-undocumented = WARN).
  Existence only; no value is ever read. A drifted map is worse than no map: it
  sends sessions to the wrong location, they find nothing, and they ask the user
  for a credential already provided. That exact drift (the RevenueCat key
  documented in `.env.local` while it actually sat in `secrets/`) is why the
  check exists.
- **python**: WARN while the interpreter lives under a Downloads folder. It does today
  (TOOLS.md, Machine hygiene); the warning exists so nobody cleans that folder up.
