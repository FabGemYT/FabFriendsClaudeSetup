---
name: web-design-guidelines
description: 'Reviews a UI for accessibility and compliance against the Web Interface Guidelines, covering contrast ratios, semantic HTML, focus management, ARIA roles, keyboard nav, and screen-reader behavior. Serves as the final-pass quality and compliance check, run before calling any UI, page, or component work done. Not for aesthetic direction (frontend-design-official), pattern lookup (ui-ux-pro-max), or polish (impeccable); this is compliance only.'
argument-hint: <file-or-pattern>
---

# Web Interface Guidelines

Review files for compliance with Web Interface Guidelines.

## How It Works

1. Fetch the latest guidelines from the source URL below
2. Read the specified files (or prompt user for files/pattern)
3. Check against all rules in the fetched guidelines
4. Output findings in the terse `file:line` format

## Guidelines Source

Fetch fresh guidelines before each review:

```
https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
```

Use WebFetch to retrieve the latest rules. The fetched content contains all the rules and output format instructions.

### If the fetch fails

This skill is a thin wrapper around that URL, so a failed fetch means it has no rules to check
against. Do not quietly review from memory and present it as a guidelines pass -- that produces a
confident compliance verdict backed by nothing.

Instead: say the fetch failed, then either review against the baseline below and LABEL it as the
offline subset, or stop and let the caller retry.

Offline baseline (a genuine subset, not the full guidelines): text contrast >= 4.5:1 for body and
3:1 for large text; every interactive element reachable and operable by keyboard with a visible
focus ring; semantic elements over `div` with a click handler; a label or accessible name on every
control; alt text on informative images and `alt=""` on decorative ones; no information carried by
colour alone; heading levels in order with no skips; `prefers-reduced-motion` respected; form
errors announced and tied to their input; touch targets >= 44px.

Note for anyone running this inside a subagent: it needs `WebFetch`. Without it the skill loads,
looks authoritative, and can do nothing. `design-reviewer` is granted WebFetch for exactly this
reason.

## Usage

When a user provides a file or pattern argument:
1. Fetch guidelines from the source URL above
2. Read the specified files
3. Apply all rules from the fetched guidelines
4. Output findings using the format specified in the guidelines

If no files specified, ask the user which files to review.
