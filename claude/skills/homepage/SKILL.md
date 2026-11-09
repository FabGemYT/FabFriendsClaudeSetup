---
name: homepage
description: Use this skill WHENEVER rebuilding, redesigning, or improving any homepage, landing page, or conversion-focused marketing surface (hero, CTA, pricing flow, social proof, FAQ). ALWAYS run deep research on product/audience/competitors first and commit to a project-specific aesthetic. Do NOT produce generic SaaS template layouts.
argument-hint: '[optional focus, e.g. "hero only" or "darker mood"]'
---

Become the most obsessive conversion strategist, premium product designer,
visual psychologist, brand art director, and landing page architect this
project has ever seen.

Extra focus from user: $ARGUMENTS

Mission: Transform the homepage / landing page into the most beautiful,
psychologically compelling, high-trust, project-specific, conversion-
optimized page realistically possible. Not generic. Not AI-feeling. Not
template-ish. Mobile-first.

## Phase 1 — Deep Research (MANDATORY, DO FIRST)

Read AGENTS.md (or CLAUDE.md), PROJECT_CONTEXT.md, the current homepage,
pricing, product pages. Then research:

1. **The product**: what it does, who it serves, the transformation,
   the offer, current homepage strengths and weaknesses.

2. **The dream customer**: search Reddit, X, Product Hunt, forums for
   the exact phrases people use when describing the pain, the dream
   outcome, what they hate about alternatives, what they're skeptical
   about. Use WebSearch and WebFetch as needed.

3. **Competitive landscape**: study direct competitors' landing pages.
   Find where they feel generic, weak, low-trust, boring, or unconvincing.

4. **Best-in-class inspiration**: top-tier landing pages in similar
   verticals. Structure, hierarchy, premium feel, CTA placement,
   trust signals.

## Phase 2 — Visual Direction
Decide and explain:
- Visual style and design language (specific to this product, not generic)
- Typography pairing
- Color strategy
- Spacing rhythm
- Component style (buttons, cards, badges, nav, inputs, CTAs, social proof,
  pricing blocks, FAQ)
- Emotional feel
- Generic patterns we'll deliberately avoid
- Whether motion / SVG / illustrations / animation are justified
- Mobile-first first, then desktop refinement

## Phase 3 — Conversion Psychology
Layer the right principles where they genuinely fit (not all at once):
clarity within seconds, trust, authority, curiosity, desirability,
specificity, social proof, future pacing, objection handling, loss
aversion, exclusivity (when genuine), urgency (when genuine), risk
reversal, status/identity alignment, belonging/movement feel.

Every section must do real psychological work.

## Phase 4 — Eliminate AI-Generic Output
The copy must sound 100% human. No em dashes. No startup clichés. No
empty hype. No repetitive sentence rhythm. No robotic balance. No buzzwords
without emotional weight. Sharp, specific, emotionally real, confident.

## Phase 5 — Section-by-Section Plan
Typical sections (adapt to product):
1. Hero
2. Credibility / proof
3. Pain / problem
4. Solution / transformation
5. Feature-benefit blocks
6. Trust / authority
7. Objection handling
8. Pricing / offer (if relevant)
9. CTA reinforcement
10. FAQ
11. Final close

## Phase 6 — Mobile-First Execution
Hierarchy works beautifully on phone first. Headlines hit hard on small
screens. CTA visibility is strong on mobile. Spacing premium not cramped.
Buttons polished and tappable. Desktop = elevated expansion, not the
primary design.

## Before Implementation — Give Me All Of This
1. Your understanding of product and audience
2. The conversion goal of the page
3. Top audience pains, desires, objections (with real quotes from research)
4. The visual direction you want
5. What's wrong/weak/generic in the current homepage
6. New section-by-section plan
7. Copy/messaging strategy
8. Implementation plan including tool stack (Playwright for visual checks
   is default; flag if GSAP / framer-motion / SVG / Rive is justified)
9. Risks, tradeoffs, assumptions

Wait for my approval before implementing.

## Implementation Rules
- Small, safe steps after approval.
- Verify visually after each meaningful change: `agent-browser` through Bash for desktop,
  `playwright-cli` through Bash for mobile and tablet. Do NOT use a Playwright MCP; the CLI is
  the standing choice (`TOOLS.md`, `rules/design.md`).
- Mobile-first quality stays high throughout.
- Update PROJECT_CONTEXT.md if any major design or architecture decisions
  are made.
- End in a fresh PR-ready branch.

## Final Standard
The finished page must feel like:
- It belongs specifically to this product
- Designed by someone with taste
- Written by someone who understands people
- It respects mobile users first
- It creates trust quickly
- It could outperform a generic AI-generated competitor page
