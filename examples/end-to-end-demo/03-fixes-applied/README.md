# 03 — Fixes Applied

This directory shows the framework in action fixing one of the seeded issues.

## What's here

| File | Role |
|------|------|
| `X-01.md` | The issue file after it was marked `RESOLVED`. Note the new `Resolution` section at the bottom, the updated `status:` in frontmatter, and the `resolved_date:` field. |
| `diff.patch` | `git diff README.md` — the single-line change that actually fixed the problem. |

## The fix

`X-01` — "README omits `/verify-catalog` from Slash Commands table" — was fixed by adding a single row to the Slash Commands table in `README.md`:

```diff
 | `/find-all` | Hunt for issues across all 23 lanes in parallel |
 | `/fix-all` | Fix all open issues across all lanes in parallel |
 | `/verify-fixes` | Verify all RESOLVED issues are actually fixed |
+| `/verify-catalog` | Systematically re-verify every RESOLVED issue in the catalog |
```

Total edit: **one line added, zero lines removed**. This is intentionally the lowest-risk of the five seeded issues so the demo can be reproduced safely by anyone cloning the repo.

## Why only one fix?

The other four issues (`G-01`, `H-01`, `L-01`, `W-01`) are deliberately left OPEN so readers can:

- See the before-state of the catalog.
- Watch `verify_issue.py` correctly fail on an un-fixed issue.
- Contrast a resolved issue's frontmatter (`status: RESOLVED`) with an open one (`status: OPEN`).

## How the resolution was recorded

The issue file was edited in two places:

1. **Frontmatter** — `status: "OPEN"` → `status: "RESOLVED"`, plus new `resolved_date: "2026-04-23"`.
2. **Resolution section** — appended at the bottom with:
   - Date resolved
   - Description of the fix (including source of the description text)
   - The diff itself
   - Verification result

See `X-01.md` in this directory for the final state.
