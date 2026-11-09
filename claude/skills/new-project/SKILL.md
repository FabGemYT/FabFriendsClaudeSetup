---
name: new-project
description: Starts a brand-new project for a non-technical owner who has an idea but no plan yet. Interviews them in plain words (what it is, who it is for, what it must do first, how it makes money, how it should feel), researches the best competitors, writes docs/PRD.md, gets a yes, then hands over to the kickoff skill. Use when the owner says "make me a website / app / game for ...", "I have an idea", or "start a new project" and the project has no PRD yet.
---

# New project

The owner is not technical. They know what they want, not how it is built. Your job is to turn
an idea into a written plan they approve, then start it the way every project here starts.

## 1. Read first
- `~/.claude/about-me.md` (who they are, what they already run, their accounts).
- `~/.claude/rules/the-goal.md`: every project here aims at it from day one.

## 2. Interview (two short rounds, AskUserQuestion, plain words, offer choices)
Round one, the idea:
- **What is it, in one sentence?** Offer two or three phrasings of what they said.
- **Who is it for?** The first 100 people who would use or pay for it.
- **What must it do on day one?** Three to five things, no more.
- **How does it make money?** Free, one-time price, subscription, ads, not yet.

Round two, the shape:
- **How should it feel?** Offer three short style directions with a real example site each.
- **Web or phone app?** Default to a website that works perfectly on phones; a store app only
  if they need one (it costs them $99 a year for Apple and $25 once for Google).
- **What must it never do?** Their red lines.
- **Name and domain?** Offer names; check domain availability before suggesting one to buy (buying is theirs).

## 3. Research before writing
Find the three to five best products doing this today and what their customers praise and
complain about (reviews, Reddit). Note what to copy and what to do better, as the goal asks.

## 4. Write `docs/PRD.md`
Plain words, one page if possible: the one-line positioning, who it is for, day-one features,
what is NOT in version one, how it makes money (the offer, using the Hormozi playbook in
`rules/the-goal.md`), the look and feel, how we will know it works (one or two numbers), and
the stack (Next.js + Supabase + Vercel unless the PRD says otherwise).

## 5. Get a yes
Show a five-line summary of the PRD and ask: "Build this?" Change what they ask for; nothing is
built before the yes.

## 6. Start it
Hand over to the `kickoff` skill with the PRD. It sets up the repository, Supabase if needed,
Vercel, and the first preview link. Then teach the loop in two lines: "I send you a preview
link; you check it on your phone; if it's right, you merge, and it goes live."
