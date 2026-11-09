# Guardrail regression tests

The four PreToolUse command guards are the only thing that actually stops an
agent pushing to main, merging a PR, or deploying to production. Prose rules can
be reasoned around; these cannot. That makes them worth testing like production
code, which is what lives here.

Every case in `test-command-guards.py` is either a command that performs a
forbidden action and was **confirmed to slip through** at some point, or a piece
of legitimate work that must never be blocked. The false-positive half matters as
much as the false-negative half: a guard that blocks ordinary commits gets
switched off, and then it protects nothing.

## Run them

```bash
py -3 hooks/tests/test-command-guards.py         # 93 bypass + 48 allow cases
py -3 hooks/tests/test-branch-aware-push.py      # bare-push behaviour on/off main
py -3 hooks/tests/test-interpreter-passthrough.py # nested-command detection
py -3 hooks/tests/test-sweep-leftovers.py        # leftover-process sweep + idle sleep, on real processes (~30 s)
py -3 hooks/tests/test-sync-harness.py           # session-start harness sync, on scratch repos (~20 s)
```

Exit code 0 means clean. `test-command-guards.py` prints a per-case table plus a
summary; anything under 93/93 and 48/48 is a regression.

These spawn a Python process per guard per case, so the full suite takes a couple
of minutes. Run it after ANY edit to `command-guard.py` or the four
`block-*.sh` wrappers.

## What the cases came from

An adversarial audit on 2026-07-30 executed 250+ payloads against the live hooks
and found 36 working bypasses. They clustered into a handful of root causes,
each now covered here:

| Family | The bug |
|---|---|
| `flag-swallow` | `-f`/`-d`/`-t`/`-b`/`--repo` sat in the message-flag list, so they consumed the *next* argument. `git push -f origin main` parsed as remote=`main` with no refspec, and a force-push to main was allowed. |
| `heredoc-fake` | Heredoc detection was quote-blind, so `echo "<<EOF"` on line 1 deleted the rest of the command. Two lines disabled all four guards. |
| `heredoc-real` | A heredoc body piped to a shell (`bash <<EOF`) is the command, not data, but bodies were always discarded. |
| `wrapper-flag` | The wrapper peel stopped at the first flag, so `env -i git push origin main` resolved to binary `env` and every guard returned early. |
| `wrapper-new` | `timeout`, `stdbuf`, `setsid`, `xargs` were absent from the wrapper set. |
| `shell-syntax` | `(cmd)`, `{ cmd; }`, `if..then` returned `(git` / `{` / `then` as the binary. |
| `interp-flags` | Only the exact token `-c` was recognised, so `bash -lc` and `sh -ec` passed. |
| `code-eval` | `node -e`, `python -c`, `perl -e` were never recursed into, and `settings.json` auto-allows `Bash(node:*)` — unprompted *and* unguarded. |
| `gh-graphql` | A GraphQL `mergePullRequest` mutation travels as the value of `-f`, exactly what the message-flag filter dropped, making the check dead code. |
| `gh-globalflag` | `gh -R o/r pr merge` broke the positional `args[0]=="pr"` assumption. |
| `base-var` | Any `$` in `--base` hit a bare `return` — a fail-open path inside a fail-closed guard. |
| `refspec-var` | `B=main; git push origin $B` and `$(echo main)` were invisible to a literal pattern match. |

## Design notes worth keeping

- **The guards are the real security boundary, not the `deny` list.** Deny rules
  are leading-prefix matches, so `Bash(git push -f:*)` never matches
  `git push origin -f main`. Several allow rules (`Bash(node:*)`, `Bash(find:*)`)
  can run arbitrary code, which is precisely why the analyser recurses into
  interpreters instead of trusting the permission layer.
- **Fail closed.** Empty stdin, non-JSON, a missing analyser, a missing Python,
  or an unparseable payload all block. `test-command-guards.py` does not cover
  these; the wrappers' own contract does, and the malformed-input block in
  `hooks/tests/../..` history covers it.
- **These stop accidents and recognisable commands, not determined obfuscation.**
  A base64-encoded payload decoded at runtime will get through, and that is an
  accepted limit — the threat model is a capable agent making a mistake, not an
  adversary with shell access deliberately evading its own guardrails.
