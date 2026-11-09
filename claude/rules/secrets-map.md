---
description: The inventory of every credential this owner has - name, scope, exact location, and who can fetch it. Names and locations ONLY, never values. Read this before asking the owner for any credential; CLAUDE.md "Secrets" points here.
paths:
  - "**/.env*"
  - "**/secrets/**"
  - "**/.github/workflows/**"
  - "**/vercel.json"
  - "**/supabase/**"
---

# Secrets map

Names and locations only, never values. Claude adds a row every time a credential is filed
(CLAUDE.md "Secrets"). Updates to the shared setup never touch this file.

## Storage locations, what each one means

- `~/.claude/.env.local`: account-level values, loaded into every session by `hooks/load-env.sh`.
- `~/.claude/secrets/`: key files (JSON, .p8, .p12). Never committed, never scanned as a leak.
- A project's own `.env.local`: values for that project only, mirrored to Vercel with
  `vercel env add`.

## Account-level (loaded into every session automatically)

| Name | Location | Used for | Who fetches |
| --- | --- | --- | --- |

## Account-level FILES in `~/.claude/secrets/`

| File | What it is | Used by |
| --- | --- | --- |

## Per project

(One section per project: the names it needs, where each lives, and where it is mirrored.)
