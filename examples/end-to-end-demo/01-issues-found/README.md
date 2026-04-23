# 01 — Issues Found

Each file in this directory is an exact snapshot of `issues/<LANE>/<ID>.md` immediately after it was seeded into the catalog. The issues here are the raw output a hunter agent would produce (with human-written Evidence sections — this demo was seeded manually, not by spawning the full 26-lane hunter swarm).

## Files

| File | Issue | What it catches |
|------|-------|-----------------|
| `G-01.md` | Ghost reference | README claims 23 lanes, but 26 lane files actually exist on disk. |
| `H-01.md` | Catalog drift | `ISSUE_CATALOG.md` Lane Definitions table is missing the Lane B row even though Lane B has a hunter and appears in the Completion Status table. |
| `L-01.md` | Missing CI | No `.github/workflows/` directory exists — zero automated verification of the 247 tools. |
| `W-01.md` | Missing tests | No `tests/` directory, no `pytest` in `requirements.txt`, no `test_*.py` files anywhere in the repo. |
| `X-01.md` | Doc omission | README's Slash Commands table lists 3 commands but the repo ships 4 (`/verify-catalog` is missing). |

## Anatomy of a seeded issue file

Each file follows the standard issue template:

1. **YAML frontmatter** — `issue_id`, `lane`, `severity`, `status`, `affected_paths`
2. **Problem Description** — what, expected, actual, scope
3. **Evidence** — actual terminal output proving the issue is real
4. **Fix Requirements** — what needs to change (but doesn't implement)
5. **Verification Commands** — bash one-liners that return `PASS` once the fix is correct
6. **Dedup Verification** — search terms used to confirm no duplicate already exists

## How they were created

```bash
python3 tools/add_issue.py G "README references 23 lanes but 26 exist (A-Z)" --severity 4 --path README.md
python3 tools/add_issue.py L "Missing CI/CD workflow configuration" --severity 5 --path .github/workflows/
python3 tools/add_issue.py W "No test suite exists for tools/" --severity 6 --path tests/
python3 tools/add_issue.py X "README omits /verify-catalog from Slash Commands table" --severity 2 --path README.md
python3 tools/add_issue.py H "Lane B missing from ISSUE_CATALOG.md Lane Definitions table" --severity 3 --path ISSUE_CATALOG.md
```

The generated template was then enriched with real `grep`/`ls` evidence and runnable verification commands — exactly what a hunter agent is expected to do before declaring a lane scan complete.
