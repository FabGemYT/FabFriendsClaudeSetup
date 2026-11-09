---
description: The platform lies quietly. Supabase, Vercel and Next traps that fail silently, learned across a live web game 2026-05 to 2026-10 (PostgREST 1,000-row cap, env vars need a redeploy, CDN cache keys, noindex on rewrites, RLS deny-all, 1fr grids, crashing tests, first push goes to production). Loads when Supabase, SQL, API routes, config or scripts are touched.
paths:
  - "**/supabase/**"
  - "**/*.sql"
  - "**/app/api/**"
  - "**/pages/api/**"
  - "**/lib/**"
  - "**/scripts/**"
  - "**/middleware.*"
  - "**/next.config.*"
  - "**/vercel.json"
  - "**/robots.*"
---

# The platform lies quietly (Supabase, Vercel, Next; learned across a live web game 2026-05 to 09)

Every trap here fails SILENTLY. No error, no warning, no log line. That is what makes them worth
writing down: the code looks right, the number is simply wrong, and it stays wrong for months.

**1. THE TRANSPORT CAPS EVERY READ AT 1,000 ROWS AND SAYS NOTHING.** PostgREST answers with at
most a thousand rows, `error: null`, no truncation flag. A query asking for 277,573 rows and a
query asking for a thousand are indistinguishable from the calling code.

**NINE separate defects in one project.** Each looked like something else at the time:

| what it looked like | what it was |
| --- | --- |
| a save opened showing its OLDEST 500 turns, nothing recent | 2 rows a turn past the cap |
| a world forgetting a vow, a name, a parentage | the oldest canon dropped from memory |
| an email blast reporting 10 recipients | there were 116 |
| a weekly report saying "+$58.63 net" | the real week was **-$116.70** |

That last one told the operator the owner was profitable for as long as the report existed.

- **NEVER SUM OR COUNT IN APPLICATION CODE.** If you are adding up, counting, or taking a top ten,
  do it in SQL and return one row. Paging a quarter of a million rows into Node to total a column
  is a correct answer to the wrong question.
- Any read not scoped to a single owner needs `.limit()`, `.range()`, or an explicit paging loop.
- **A guard that names three queries is whack-a-mole.** Scan for the SHAPE: a select on a table
  that can grow, with no bound and no owner scope. Naming instances is how the tenth one gets in.

**2. AN ENV VAR IS NOT LIVE UNTIL YOU REDEPLOY** (already in FOUNDATION; it belongs here too).
Vercel bakes them in at BUILD time. `vercel redeploy <id> --target=production` rebuilds the same
commit and is not the merge gate.

**3. VERCEL KEYS ITS CDN CACHE ON THE RESOLVED PATH,** which the response reports as
`X-Matched-Path`. That is what makes a middleware rewrite safe: two visitors rewritten to
different pages get different cache entries. **Measure it with a header dump before relying on
it**, the whole geo-pricing design rests on this being true.

**4. A `noindex` ON A REWRITE TARGET APPLIES TO THE SOURCE URL.** If `/pricing` is rewritten to
`/pricing/c/INR`, then a noindex on the second is a noindex on `/pricing` for everyone the rewrite
applies to. Use **robots.txt**, which matches the requested URL and never sees an internal
rewrite.

**5. RLS ON WITH NO POLICIES MEANS DENY-ALL,** which is the safe direction, but a client read
returns an empty list rather than an error, so a feature reading a service-role-only table looks
like it has no data rather than no permission.

**6. `1fr` IN A CSS GRID WILL NOT SHRINK BELOW ITS CONTENT.** It is `minmax(auto, 1fr)`. One long
string in one cell widened every card and pushed the whole page sideways, 189px of horizontal
scroll, invisible in the language it was designed in. Use `minmax(0, 1fr)`.

**7. A CRASHING TEST PRINTS NO SUMMARY, AND A SWEEP GREPPING FOR "N failed" COUNTS IT AS A PASS.**
Two suites had stopped loading entirely and the sweep reported no failures. **Absent summary is a
failure.** The cause was an `@/`-aliased import added to a module that bare Node loads, anything
a test imports directly must stay dependency-free.

**8. `NEXT_RUNTIME` is set only inside a Next server; `VERCEL` only on a deployed one.** Both
together identify "a Next server on a laptop", which is the honest way to stop a local test run
sending real email to real people. Verified rather than assumed: `NEXT_RUNTIME` is absent in a
plain `node script.mjs`.

**9. A NEW VERCEL PROJECT BUILDS ITS FIRST GIT PUSH AS PRODUCTION, WHATEVER THE BRANCH.** Measured
6 Oct 2026 (a second online store): a project linked to GitHub with no production deployment yet took the
first push of a feature branch as `target: production` and aliased it to `<project>.vercel.app`;
every later push built as a preview. So on any new project, put `main` live first (create the
project, then deploy `main` or push to it) before any branch push, or unmerged code goes live.

**The general rule behind all of them: if a failure would be invisible, go and look.** Query the
live table, dump the header, replay the real function over real rows. Every number in this section
came from measuring, and several contradicted what the code's own comments claimed.
