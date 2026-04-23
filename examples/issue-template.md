---
issue_id: "{LANE}-NN"
lane: "{LANE}"
severity: 5
severity_level: "MEDIUM"
type_tags: ["Tag1", "Tag2"]
status: "OPEN"
affected_paths:
  - "path/to/affected/file"
  - "another/path"
depends_on: []
blocks: []
---

# [LANE {LANE}] Issue {LANE}-NN: Issue Title Here

- Type Tags: Tag1, Tag2
- Severity: 5/10 (MEDIUM)
- Status: OPEN
- Date Discovered: YYYY-MM-DD

---

## Problem Description

- **What is wrong:** Clear, specific description of the issue
- **Expected (per guidelines):** What the correct state should be
- **Actual:** What's actually happening/present
- **Scope:** Which components/files are affected

## Evidence

```bash
$ grep -rn "pattern" src/
src/file.py:42:matching line of code
```

- **Source:** `path/to/file.py:42`
  > "relevant code snippet here"

## Impact Analysis

- **Immediate:** Direct consequences of this issue
- **Downstream:** Other things affected by this
- **Risk rationale:** Why this severity level

## Fix Requirements (DO NOT IMPLEMENT)

- [ ] Specific required change #1
- [ ] Specific required change #2
- [ ] Verification of fix

## Verification Commands

```bash
# Check 1: Verify file exists
test -f path/to/expected/file && echo "PASS" || echo "FAIL"

# Check 2: Verify content
grep -q "expected_pattern" path/to/file && echo "PASS" || echo "FAIL"
```

## Dedup Verification

- **Search terms:** "relevant", "keywords"
- **Files checked:** issues/{LANE}/, ISSUE_CATALOG.md
- **Result:** No duplicates found

---

## Resolution (Added After Fix)

> This section is filled in by the issue fixer agent

- **Fixed:** YYYY-MM-DD
- **Fixed By:** IF-Lane-{LANE}
- **Changes Made:**
  - `file1.py`: Description of change
  - `file2.yaml`: Description of change
- **Verification:** PASS
