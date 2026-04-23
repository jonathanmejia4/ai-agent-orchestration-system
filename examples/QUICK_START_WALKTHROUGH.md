# Quick Start Walkthrough

This is exactly what happens when you run the framework for the first time against this repo. Every output block below was **captured from a real run on 2026-04-23** — not simulated.

A permanent snapshot of the artifacts produced by this walkthrough lives at [`end-to-end-demo/`](end-to-end-demo/).

---

## Step 1 — Clone and install

```bash
$ git clone https://github.com/jonathanmejia4/ai-agent-orchestration-system.git
$ cd ai-agent-orchestration-system
$ pip install -r requirements.txt
```

`requirements.txt` is intentionally tiny — only `pyyaml` is required for the core tooling to run.

---

## Step 2 — Check the starting state of the catalog

```bash
$ python3 tools/issue_stats.py
======================================================================
Issue Catalog Statistics
======================================================================
Last Updated: 2026-04-23 10:54:25

TOTAL: 0 issues | ✅ 0 resolved | ❌ 0 open
Progress: [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0.0%

Severity: 🔴 HIGH: 0 | 🟡 MEDIUM: 0 | 🟢 LOW: 0

----------------------------------------------------------------------
Lane    Total  Resolved   Open     Progress  HIGH   MED   LOW
----------------------------------------------------------------------
----------------------------------------------------------------------
```

Clean slate. Twenty-six empty lane directories under `issues/`, no issue files yet.

---

## Step 3 — Seed some real issues

In a full run you would use `/find-all` to spawn 26 hunter agents in parallel. For this walkthrough we seed five issues manually — all of them **real problems that actually exist in the public repo on the day of this run**:

```bash
$ python3 tools/add_issue.py G "README references 23 lanes but 26 exist (A-Z)" --severity 4 --path README.md
Created: issues/G/G-01.md

$ python3 tools/add_issue.py L "Missing CI/CD workflow configuration" --severity 5 --path .github/workflows/
Created: issues/L/L-01.md

$ python3 tools/add_issue.py W "No test suite exists for tools/" --severity 6 --path tests/
Created: issues/W/W-01.md

$ python3 tools/add_issue.py X "README omits /verify-catalog from Slash Commands table" --severity 2 --path README.md
Created: issues/X/X-01.md

$ python3 tools/add_issue.py H "Lane B missing from ISSUE_CATALOG.md Lane Definitions table" --severity 3 --path ISSUE_CATALOG.md
Created: issues/H/H-01.md
```

Each command produces a markdown file with YAML frontmatter, a template for Problem Description / Evidence / Fix Requirements / Verification Commands, and populated `affected_paths`.

Each was then **edited by hand to add real evidence**: actual `grep` output, file counts, and runnable verification commands. The full enriched files live at [`end-to-end-demo/01-issues-found/`](end-to-end-demo/01-issues-found/).

---

## Step 4 — Sync the catalog

```bash
$ python3 tools/sync_catalog_stats.py
Scanning issue files...

Found: 5 issues, 0 resolved, 5 open
Updating catalog...
✅ Catalog updated successfully

$ python3 tools/issue_stats.py
======================================================================
Issue Catalog Statistics
======================================================================
Last Updated: 2026-04-23 10:57:46

TOTAL: 5 issues | ✅ 0 resolved | ❌ 5 open
Progress: [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0.0%

Severity: 🔴 HIGH: 0 | 🟡 MEDIUM: 5 | 🟢 LOW: 0

----------------------------------------------------------------------
Lane    Total  Resolved   Open     Progress  HIGH   MED   LOW
----------------------------------------------------------------------
G           1         0      1 🔴     0%      0     1     0
H           1         0      1 🔴     0%      0     1     0
L           1         0      1 🔴     0%      0     1     0
W           1         0      1 🔴     0%      0     1     0
X           1         0      1 🔴     0%      0     1     0
----------------------------------------------------------------------
```

`ISSUE_CATALOG.md` has been rewritten to reflect the five new entries. A snapshot of this intermediate state lives at [`end-to-end-demo/02-catalog-snapshot.md`](end-to-end-demo/02-catalog-snapshot.md).

---

## Step 5 — Inspect one of the issues

```bash
$ head -40 issues/X/X-01.md
---
issue_id: "X-01"
lane: "X"
severity: 2
severity_level: "LOW"
type_tags: ["X-Issue", "Doc-Drift", "Slash-Commands"]
status: "RESOLVED"
resolved_date: "2026-04-23"
affected_paths:
  - "README.md"
---

# [LANE X] Issue X-01: README omits /verify-catalog from Slash Commands table

- Type Tags: X-Issue, Doc-Drift, Slash-Commands
- Severity: 2/10 (LOW)
- Status: RESOLVED
- Date Discovered: 2026-04-23
- Date Resolved: 2026-04-23

---

## Problem Description

- **What is wrong:** The "Slash Commands" table in `README.md` lists only three commands
  (`/find-all`, `/fix-all`, `/verify-fixes`), but the repo actually ships **four** slash
  commands. `/verify-catalog` exists at `.claude/commands/verify-catalog.md` and is
  documented in the commands directory, yet a new user reading the README would not
  know it exists.
...
```

The issue has an Evidence block with actual `grep` output and a Verification Commands block with three runnable checks.

---

## Step 6 — Fix the issue

This is the smallest-possible fix of the five: add one row to the README's Slash Commands table. Applied as a single-line `Edit`:

```diff
 | `/find-all` | Hunt for issues across all 23 lanes in parallel |
 | `/fix-all` | Fix all open issues across all lanes in parallel |
 | `/verify-fixes` | Verify all RESOLVED issues are actually fixed |
+| `/verify-catalog` | Systematically re-verify every RESOLVED issue in the catalog |
```

Then update the issue's frontmatter (`status: OPEN` → `status: RESOLVED`) and append a Resolution section with date and diff.

The full committed fix lives at [`end-to-end-demo/03-fixes-applied/`](end-to-end-demo/03-fixes-applied/) (resolved issue + `diff.patch`).

---

## Step 7 — Verify the fix

Two layers of verification. First, the framework's automated verifier:

```bash
$ python3 tools/verify_issue.py X-01 --verbose

============================================================
✅ X-01: PASS
============================================================
Pattern:     embedded_commands
Depth:       STANDARD
Checks:      3/3 passed
Confidence:  100%
Targets:     .claude/commands/verify-catalog.md

Check Results:
------------------------------------------------------------
  ✅ file_exists
      Command: test -f .claude/commands/verify-catalog.md...
      Exit: expected=0, actual=0
  ✅ file_not_empty
      Command: test -s .claude/commands/verify-catalog.md...
      Exit: expected=0, actual=0
  ✅ git_tracked
      Command: git ls-files --error-unmatch .claude/commands/veri...
      Exit: expected=0, actual=0
============================================================
```

Second, the three verification commands the hunter embedded directly into the issue file:

```bash
$ grep -q "/verify-catalog" README.md && echo "PASS" || echo "FAIL"
PASS

$ for cmd in find-all fix-all verify-fixes verify-catalog; do
    grep -q "/$cmd" README.md || { echo "FAIL (missing /$cmd)"; exit 1; }
  done && echo "PASS"
PASS

$ [ "$(grep -cE '^\| `/' README.md)" -ge 4 ] && echo "PASS" || echo "FAIL"
PASS
```

Both layers independently agree. The raw captured output lives at [`end-to-end-demo/04-verification-results/verification-output.txt`](end-to-end-demo/04-verification-results/verification-output.txt).

---

## Step 8 — Re-sync the catalog to reflect the resolution

```bash
$ python3 tools/sync_catalog_stats.py
Scanning issue files...

Found: 5 issues, 1 resolved, 4 open
Updating catalog...
✅ Catalog updated successfully

$ python3 tools/issue_stats.py
======================================================================
Issue Catalog Statistics
======================================================================
Last Updated: 2026-04-23 10:59:11

TOTAL: 5 issues | ✅ 1 resolved | ❌ 4 open
Progress: [██████░░░░░░░░░░░░░░░░░░░░░░░░] 20.0%

Severity: 🔴 HIGH: 0 | 🟡 MEDIUM: 5 | 🟢 LOW: 0

----------------------------------------------------------------------
Lane    Total  Resolved   Open     Progress  HIGH   MED   LOW
----------------------------------------------------------------------
G           1         0      1 🔴     0%      0     1     0
H           1         0      1 🔴     0%      0     1     0
L           1         0      1 🔴     0%      0     1     0
W           1         0      1 🔴     0%      0     1     0
X           1         1      0 ✅   100%      0     1     0
----------------------------------------------------------------------
```

Lane X now reads 100% resolved. The snapshot of this final catalog state is at [`end-to-end-demo/05-final-catalog.md`](end-to-end-demo/05-final-catalog.md).

---

## What this demonstrates

- **Real issues found** — five problems that actually exist in the public repo: a ghost reference (README claims 23 lanes, 26 exist), a missing catalog row (Lane B), a missing CI config, a missing test suite, and an omitted slash command from the README.
- **Real fix applied** — one-line README edit, diff preserved in the repo as evidence.
- **Real verification passed** — both `verify_issue.py` and the issue's embedded bash commands returned `PASS` independently.
- **Real catalog update** — `ISSUE_CATALOG.md` and `issue_stats.py` both reflect 1/5 resolved, 4/5 still open.

Four issues are deliberately left OPEN so the before/after contrast stays visible in the tree. Running `/fix-all` would pick up the other four; the demo stops after the first fix to keep the diff reviewable.
