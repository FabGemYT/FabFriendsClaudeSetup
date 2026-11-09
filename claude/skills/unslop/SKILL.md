---
name: unslop
description: 'Cleans up, de-slops, humanizes, and polishes finished TEXT or COPY so it stops reading as AI-generated. Detects the platform first, then runs one universal slop engine and applies that surface''s native fix. Runs as the final pass after a draft exists, never a generator. Triggers include "make this sound less AI", "de-slop this", "humanize this", "does this read as ChatGPT", "remove the AI tells", "punch this up", "clean this up before posting", or pasting any copy for a sloppiness check or a rewrite. Works on any surface: X/Twitter, Instagram, TikTok, YouTube descriptions, Reddit posts and comments, cold and warm email, blog intros, ad copy, product descriptions, or unlabeled prose. The text twin of impeccable. Not for UI labels, errors, or empty states (that is the impeccable skill) or for drafting net-new long-form from scratch (that is blogs / homepage).'
---

# unslop

The text twin of `impeccable`. A single-pass, detect-then-fix editor that strips AI-slop from
any short-to-medium copy and re-registers it into the target platform's native voice. Polish,
not generation. It runs after a draft exists.

North star: genuinely human writing, not gaming a detector. Burstiness, specificity, and a real
position beat any single word swap. Make the copy read like one sharp person wrote it for that
exact surface.

## What this is, and is NOT

IS: a post-draft polish pass for standalone published copy (posts, captions, descriptions,
emails, blog/ad copy). It enforces the CLAUDE.md rails (no em dashes, no AI-slop phrasing,
concise, direct) as hard defaults on every format, then layers the per-platform fix on top.

IS NOT:
- Not a generator. If the text is being written fresh, stay out; come back once a draft exists.
- Not for UI microcopy (labels, errors, empty states, button text). That is `impeccable`.
- Not for drafting long-form from scratch. That is `blogs` / `homepage`. Those WRITE; unslop POLISHES their output.

Relationship to the rest of the system: CLAUDE.md rails are inherited as non-negotiable defaults
(the em-dash rule is verbatim). `impeccable` owns UI and visual slop; `unslop` owns published text.
The two never overlap: UI strings go to impeccable, copy goes here.

## The flow (single shot)

Run all of this in one pass. Detect, fix, audit, deliver. No back-and-forth unless step 1 is genuinely ambiguous.

1. GATE. Fire only on de-slop / polish / "does this read as AI" intent over an existing draft. Not on drafting.
2. DETECT THE FORMAT FIRST. This is the whole point: the same sentence is slop on Reddit and native on a product page, so you cannot rewrite blindly. Order of evidence:
   - An explicit label wins ("this is for X" / "Reddit" / "a cold email").
   - Else infer from signals: @handles plus ~280 chars to X; "link in bio" plus emoji to Instagram; timestamps and "subscribe" to YouTube; "Subject:" or a greeting and sign-off to email; subreddit refs, markdown, first-person problem framing to Reddit; price, spec, and benefit lines to product/ad; a 3-to-5 sentence hook paragraph to a blog intro.
   - If genuinely ambiguous AND the platform changes the fix, ask one short question ("what surface is this for?"). Otherwise, for plain prose with no platform stakes, run the universal pass only.
3. PASS 1, UNIVERSAL DETECT (one engine, every format). Scan the four tell-families below, STRUCTURE FIRST. In 2026 the single-word lists have leaked and are partly suppressed, so weight structural and clustered evidence above any one banned word.
4. CLUSTER GATE (false-positive safeguard). No lone formal word is a verdict. Flag a rewrite when 3 or more lexical tells, OR 2 or more structural tells, co-occur in a short passage. Keep edits surgical (minimal-change law). The always-fix items in family C and D are the exception: those get removed regardless of clustering.
5. PASS 2, FORMAT-AWARE FIX. Apply the universal fixes, then re-register into the detected platform's norms (the table below). Fix THE FOLD first on every surface.
6. PASS 3, AUDIT. Re-scan the rewrite for surviving tells, with the em-dash check last. If the rewrite reintroduced a tell, fix it in place before returning.
7. RETURN the output contract.

## Pass 1: the universal engine (structure first)

### A. Structural tells (highest leverage, fix these first)

- Contrastive-negation antithesis. The #1 tell of 2026. "It's not just X, it's Y" / "It's not about X, it's about Y" / "More than just X, it's Y" / "isn't X, it's Y". Kill it first. Lead with the substance and drop the defensive negation. Keep at most one antithesis in a whole piece, as a deliberate effect.
  - Slop: "It's not just a tool, it's a revolution." Human: "It changes how you work."
- Rule of three / tricolon / anaphora. Stacked parallel sentences or clauses sharing one opening or shape. "Higher X. Higher Y. Higher Z." / "More A. More B. More C." Break the pattern; vary the rhythm; cut one of the three.
- Low burstiness. Every sentence the same medium length. Humans vary hard: a long one, then three words. Force the variation deliberately.
- Over-signposting. "Firstly... Secondly... In conclusion..." / "Let me break this down." Cut the scaffolding or use a natural transition tied to the content.
- Balanced hedging. "On one hand... on the other hand", endless "can", "may", "often", "generally". Take a position. One real opinion beats two safe ones.
- The "-ing" significance tail. "..., highlighting the importance of...", "..., underscoring the need for...", "..., showcasing the value of...". Cut the tail or state the point as its own short sentence.
- Tidy-bow ending. "In summary...", "At the end of the day...", "Despite the challenges, the future is bright." End on the strongest concrete point and just stop.
- Rhetorical-question pivots. "The reality?" / "Why does this matter?" / "So what does this mean?" State the thing instead of asking it for effect.
- Vague observational authority. "I've seen this play out", "I see this constantly", "Time and again". Replace with a specific instance or cut.

### B. Lexical tells (flag in clusters of 3 or more; each has a plain replacement)

Inflated verbs: leverage to use, foster to build or encourage, cultivate to grow, empower to let or help, unlock to open or enable, unleash to release, harness to use, elevate to improve or raise, amplify to boost, streamline to simplify, supercharge to speed up, garner to get or win, boast to have, showcase to show, underscore to show or highlight, delve into to look at or dig into or explore (often just delete).

Inflated adjectives: robust to reliable (or give the number), seamless to works without setup, cutting-edge to say what it does, bespoke to custom, pivotal / crucial / vital / paramount / essential to important (used sparingly) or show why, multifaceted / nuanced / intricate / comprehensive / holistic to cut or be specific, vibrant / bustling to usually delete, nestled to in.

Stock metaphors and nouns: tapestry (delete, name the thing), testament ("a testament to" to cut and state the evidence), realm / landscape to area or field or just name it ("in the realm of marketing" to "in marketing"), navigate to deal with or handle.

Connective crutches: Moreover / Furthermore / Additionally to And, Also, Plus, or nothing. Consequently / Thus to So. Subsequently to Then or Later. Nonetheless to Still or But.

Throat-clearing openers and phrases (delete and state the point): "It's worth noting that", "It's important to note", "One might argue", "In today's fast-paced world", "In the ever-evolving landscape of", "In today's digital age", "Let's dive in", "Let's unpack this", "Let's explore", "Here's the thing", "But here's the thing", "What if I told you", any sentence starting with "Most".

Note: this list drifts per model and is partly suppressed in current models. Treat it as updatable and weight it below structure. A single formal word in otherwise human writing is fine; it is the cluster that convicts.

### C. Punctuation and formatting (always fix, regardless of clustering)

- Em dashes: remove every one. Hard rule, inherited from CLAUDE.md. Replace with a comma, a period, parentheses, or a rewrite. This is checked first and last.
- Emoji used as bullets or a per-line ladder (the rocket / check / bulb stack). Remove the ladder; keep at most a few emoji only where the platform's native (see the table).
- Hashtag walls. Trim to the platform's policy below.
- Over-bolding, Title Case Headings In Body Copy, and unnecessary numbered lists where prose reads better.
- Curly quotes and unusual unicode where straight characters are expected.

### D. AI leakage (always strip)

"As an AI language model", "I hope this helps", "I cannot browse the internet", knowledge-cutoff disclaimers, "Certainly!", "Of course!", and any meta-commentary about being an assistant. Remove unconditionally.

## Pass 2: the format overlay (fix the fold first)

For every surface, fix THE FOLD first: the first line, subject, or first ~125 characters are the only guaranteed-read real estate, and that is exactly where AI preambles do the most damage. Then apply the row.

| Surface | The fold | Hashtags | Emoji | Native voice and CTA |
| --- | --- | --- | --- | --- |
| X / Twitter | First line ~70 to 100 chars, one sharp claim or hook | 0 to 2, often zero | A few for color, never the leading character | Terse, plain first person. Put the link in a reply, not the post. Formality and hashtag spam are punished hardest. |
| Instagram | First ~125 chars before "more" | 3 to 5, at the end | Native in the body, never the first character | Punchy, personal. A light CTA ("save this", "which one") is fine. |
| TikTok caption | Short, hook in the first line | Keyword-matched, a few | Native, sparing | Casual, spoken, trend-aware. |
| YouTube description | First 2 to 3 lines (~125 chars), doubles as the search snippet | A few at the end if any | Sparing | Real keywords woven in naturally, then chapters/timestamps and links. Slop in the first lines hurts ranking and clicks most. |
| Reddit | First sentence states the actual point or problem | Zero (hashtags read as spam) | Out of place, drop them | Plain first person, problem-led, no marketing voice. Disclose any affiliation. Self-promo and corporate tone get killed hardest. |
| Email | Subject 7 words or fewer, lowercase is fine; preview ~55 chars | Zero | Rare | Colleague-simple, direct, skimmable. No corporate slop. One clear ask. |
| Ad / product copy | Lead with the benefit and a concrete number | n/a | n/a | Trade adjectives for specifics (real dollars, percentages, specs). Benefit over feature. |
| Blog intro | First sentence a specific hook, never a "world is changing" truism | n/a | n/a | One concrete detail or stakes in the first 3 to 5 sentences, then the thesis. |
| LinkedIn | Hook in the first line before "see more", strong curiosity gap | 3 to 5 at the end | A few, never the per-line ladder | Tolerates light structure, never the emoji ladder or em dashes. Conversational, one idea, a clear takeaway, a CTA only if natural. |

Intensity ladder: X and Reddit punish formality and hashtags hardest, go terse and near-tagless. Email and Reddit reward plain first-person directness. Product and ad trade adjectives for numbers. LinkedIn and Instagram tolerate light structure but never the emoji ladder.

## Voice preservation (editor, not lobotomizer)

1. De-slop is SUBTRACTIVE by default: delete throat-clearing, swap inflated words for plain ones, break mechanical symmetry, kill em dashes. Do not inject a generic "casual" voice or fake personality. Fix the tells and leave the author's wording alone where it is already human (minimal-change).
2. If the user supplies or points to a writing sample, or there is prior copy in the thread, match its sentence-length pattern, register, punctuation habits, and paragraph openings. Matching a real voice beats imposing a default one.
3. Absent a sample, default to "one thoughtful person talking", not a brand: contractions on, a real position over balanced hedging, one concrete specific over coverage-language.

## Modes

- Rewrite (default): return the cleaned copy plus the receipt.
- Detect-only: when the user asks "does this read as AI" or "what are the tells", list the tells and severity without rewriting.
- In-place edit: when given a file path or selection, make a minimal targeted edit and return the same receipt.

## Decision and output contract

Two outcomes, same as a real editor.

Already clean: if the copy passes with zero or only trivial issues, say so plainly and return it as-is. Do not manufacture edits to justify the skill. "This is clean, ready to post" is a valid and encouraged output.

Issues found: do not just list them, fix them. Then return, tight:

1. The cleaned text, ready to paste. This is the product.
2. TELLS FOUND: a short bullet list, each tell quoted, tagged by family (structural / lexical / format / leakage) and severity (P0 kill, P1 fix, P2 optional).
3. PLATFORM NOTE: one line on what was re-registered for the detected surface (fold rewritten, hashtags trimmed to N, emoji ladder removed, em dashes removed).
4. AUDIT LINE: confirms the final copy is em-dash-free and the top structural offender is gone.

## Edge cases and priority

- Already excellent: say so, return as-is. No invented edits.
- Severe structural problems: a heavy rewrite is appropriate. You have full authority to restructure, reorder, cut, and rewrite transitions. Preserve the core thesis and the key facts; everything else is fair game.
- When issues compound, fix in this order: (1) P0 removals (em dashes, AI leakage, banned phrases and the negation structure), (2) fluff and context-stuffing cuts, (3) structural flow and burstiness, (4) voice match, (5) platform format (fold, hashtags, emoji), (6) CTA.
- Fact safety: do not invent specifics. If you swap an inflated claim for a concrete one, only use a number or detail that is actually present in the source or the thread. If a stat is approximate, keep it flagged as approximate. Never fabricate a figure to sound concrete.
- Works on any draft regardless of who or what wrote it.

This skill is grounded in Wikipedia's community-maintained "Signs of AI writing", which is the right place to re-pull from when the lexicon drifts.
