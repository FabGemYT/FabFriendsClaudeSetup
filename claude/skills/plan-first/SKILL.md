---
name: plan-first
description: Runs before writing any code for a feature-sized task — interviews the user on requirements with AskUserQuestion, writes a plan for approval, and covers phased execution and design-task handling. Use for anything with 3+ steps or real ambiguity. Skip for a one-sentence diff or a routine fix.
---

# Plan before coding

## Interview, then plan (BEFORE any code changes)
For anything feature-sized, use the AskUserQuestion tool to interrogate the user on requirements
BEFORE writing the plan. They direct rather than code, so the requirements live in their head and
you are better at extracting them than they are at volunteering them. Cover the hard parts and the
things they have not thought about. For larger work, write the agreed shape to a SPEC.md or plan
file in the repo before implementing, because a file survives compaction and a conversation does
not.

Then surface this plan inline and wait for approval:
1. Understanding: what the task means in this codebase.
2. Files affected.
3. Risks or better approaches. For costly, hard-to-reverse decisions (architecture, auth, data
   model, key libraries, core UX): options + tradeoffs + a recommendation, not just one path.
4. Plan, step by step.
5. Trusted skills to fire, explicitly named (skill auto-fire is description-matched and
   unreliable, so pick deliberately). Built-in tools don't need enumerating.
6. New third-party skill/plugin/MCP needed? If yes, ask and wait.
7. Doc updates, if the change affects architecture, rules, important logic, or major UX.

End with: "Plan ready. Say go or fire to execute. Push back to revise."

After approval, execute autonomously within the approved plan. No micro-confirmations between
steps. If reality diverges (file missing, dependency conflict, API behaves differently, planned
tool fails), stop and surface it rather than improvising.

## Phased execution
Estimate up front whether the work fits one response. If risky, split BEFORE starting (by file,
component, or feature slice), not mid-stream, and commit each completed step before the next. For
architecture-scale or redesign work, treat each phase as its own plan-approve cycle.

## Design tasks
For any UI or design task, read `~/.claude/rules/design.md` first (premium standards, anti-slop
bans, the component stack, and the mandatory generate-screenshot-review loop). Name the design
skills in your plan: `frontend-design-official`, `ui-ux-pro-max`, `impeccable`,
`web-design-guidelines`. The screenshot/test feedback loop is the highest-leverage workflow
available; give the work a way to check itself and let it iterate two or three rounds. `design.md`
is a path-scoped rule that reloads only when Claude next reads a matching file, so re-read it
explicitly if you're still doing UI work a long way into a session.
