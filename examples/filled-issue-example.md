---
issue_id: "G-12"
lane: "G"
severity: 7
severity_level: "HIGH"
type_tags: ["GhostRef", "MissingTool"]
status: "RESOLVED"
affected_paths:
  - "PLANNING/WORKFLOW_GUIDE.md"
  - "tools/validate_config.py"
depends_on: []
blocks: ["G-15", "H-03"]
---

# [LANE G] Issue G-12: Ghost reference to validate_config.py in WORKFLOW_GUIDE

- Type Tags: GhostRef, MissingTool
- Severity: 7/10 (HIGH)
- Status: RESOLVED
- Date Discovered: 2026-01-05

---

## Problem Description

- **What is wrong:** `PLANNING/WORKFLOW_GUIDE.md:45` references `tools/validate_config.py` which does not exist
- **Expected (per guidelines):** Documentation should only reference tools that exist
- **Actual:** Line 45 says "Run `python3 tools/validate_config.py`" but this file is missing
- **Scope:** Users following the workflow guide will hit an error at step 3

## Evidence

```bash
$ grep -n "validate_config.py" PLANNING/WORKFLOW_GUIDE.md
45:3. Run `python3 tools/validate_config.py` to validate your configuration

$ test -f tools/validate_config.py && echo "EXISTS" || echo "GHOST"
GHOST
```

- **Source:** `PLANNING/WORKFLOW_GUIDE.md:45`
  > "3. Run `python3 tools/validate_config.py` to validate your configuration"

## Impact Analysis

- **Immediate:** Workflow step 3 fails with "file not found"
- **Downstream:** G-15 (another doc referencing same tool) and H-03 (placeholder marked "needs validation tool")
- **Risk rationale:** HIGH because this blocks a documented workflow that users will follow

## Fix Requirements (DO NOT IMPLEMENT)

- [x] Option A: Create `tools/validate_config.py` with actual validation logic
- [ ] Option B: Remove/update the reference in WORKFLOW_GUIDE.md
- [x] Verify the tool works after creation

## Verification Commands

```bash
# Check 1: Tool file exists
test -f tools/validate_config.py && echo "PASS" || echo "FAIL"

# Check 2: Tool is executable (has shebang or works with python)
python3 -c "import ast; ast.parse(open('tools/validate_config.py').read())" && echo "PASS" || echo "FAIL"

# Check 3: Documentation reference still exists (should)
grep -q "validate_config.py" PLANNING/WORKFLOW_GUIDE.md && echo "PASS" || echo "FAIL"
```

## Dedup Verification

- **Search terms:** "validate_config", "WORKFLOW_GUIDE", "ghost"
- **Files checked:** issues/G/, ISSUE_CATALOG.md
- **Result:** No duplicates found - first instance of this ghost reference

---

## Resolution (Added After Fix)

- **Fixed:** 2026-01-06
- **Fixed By:** IF-Lane-G
- **Changes Made:**
  - `tools/validate_config.py`: Created new validation tool (87 lines)
    - Validates YAML config files against schema
    - Returns clear error messages
    - Exit codes: 0 = pass, 1 = fail
  - `tools/validate_config_schema.yaml`: Added schema definition
- **Verification:** PASS (all 3 checks passed)
- **Commit:** abc1234

---

## Why This Example Is Useful

This issue demonstrates:
1. **Clear problem description** - exact file:line reference
2. **Concrete evidence** - runnable bash commands showing the problem
3. **Impact analysis** - explains why this matters (blocks workflows)
4. **Multiple fix options** - often you can either create the missing thing OR remove the reference
5. **Verification commands** - runnable checks that confirm the fix works
6. **Dedup section** - prevents duplicate issues
7. **Resolution section** - filled in after the fix, showing what was done
