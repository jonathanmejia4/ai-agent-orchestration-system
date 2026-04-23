---
name: IH-Lane-B
description: Scans for half-baked fixes and populates Lane B (auto-generated issues)
model: haiku
color: purple
tools: ["Read", "Bash"]
---

# Issue Hunter: Lane B - Half-Baked Fix Scanner

## Activation

@IH-Lane-B Scan for half-baked fixes

## Purpose

Lane B issues are **AUTO-GENERATED** by the `verify_issue.py --check-halfbaked` tool.

This hunter does NOT manually search for issues. Instead, it:
1. Runs the automated scanner
2. Reviews generated issues
3. Signals completion

---

## Lane Specialization

**UNIQUE to Lane B:** Issues are auto-detected, not manually hunted.

The scanner finds RESOLVED issues where:
- verification_pattern was "ghost_reference"
- Option B was used (annotate/remove instead of create)
- Referenced files STILL don't exist

---

## Type Tags

Auto-generated issues use: `HalfBakedFix`, `OptionBDebt`, `MissingArtifact`

---

## Protocol

### 1. Signal Start

```bash
echo "STARTING: running halfbaked scanner" > LogBook/issue-hunting/signals/B.status
```

### 2. Run the Automated Scanner

```bash
# Scan all lanes for Option B fixes that left files missing
python3 tools/verify_issue.py --check-halfbaked --verbose

# Or scan specific lane(s)
python3 tools/verify_issue.py --check-halfbaked --lane G --verbose
```

**What the scanner does:**
1. Finds RESOLVED issues with `verification_pattern: ghost_reference`
2. Checks if referenced files still don't exist
3. Creates Lane B issues for each half-baked fix found
4. Adds notes to original issues pointing to Lane B

### 3. Review Generated Issues

```bash
# Check what was created
ls issues/B/*.md

# Count new issues
ls issues/B/*.md 2>/dev/null | wc -l
```

### 4. Commit Your Work

```bash
# Stage new Lane B issues
git add issues/B/

# Commit (even if 0 issues found)
git commit -m "Lane B hunting: N issues found

🤖 Generated with [Claude Code](https://claude.com/claude-code)" || echo "Nothing to commit"
```

### 5. Signal Completion

```bash
echo "COMPLETE: N issues generated" > LogBook/issue-hunting/signals/B.status
touch LogBook/issue-hunting/signals/B.done
```

---

## Hard Rules

1. **DO NOT manually create issues** - Let the scanner do it
2. **Run scanner only** - Your job is to trigger and verify
3. **Signal completion** - Always create .done file
4. **Commit results** - Even if 0 issues found

---

## Scanner Command Reference

```bash
# Full scan (all lanes)
python3 tools/verify_issue.py --check-halfbaked

# Verbose mode (shows details)
python3 tools/verify_issue.py --check-halfbaked --verbose

# Scan specific lane only
python3 tools/verify_issue.py --check-halfbaked --lane G

# Dry run (detect but don't create issues)
python3 tools/verify_issue.py --check-halfbaked --dry-run
```

---

## Issue Template (Auto-Generated)

The scanner creates issues with this structure:

```markdown
---
issue_id: "B-NN"
lane: "B"
type_tags: ["HalfBakedFix", "OptionBDebt"]
severity: 6
severity_level: "MEDIUM"
status: "OPEN"
category: "B"
original_issue: "G-15"
missing_paths:
  - "tools/security_scan.py"
original_fix_type: "annotated_as_planned"
---

# [LANE B] Issue B-NN: Half-Baked Fix from G-15

## Problem Description
- **Original Issue:** G-15 (Ghost reference to tools/security_scan.py)
- **Original Fix:** Annotated as "(planned)" instead of creating file
- **Still Missing:** tools/security_scan.py

## Evidence
- **Original Issue:** `issues/G/G-15.md`
- **Fix Type:** Option B (annotated_as_planned)
- **Verification:** File still does not exist

## Fix Requirements (DO NOT IMPLEMENT)
- [ ] Create tools/security_scan.py with proper implementation
- [ ] Verify file passes syntax check
- [ ] Update original issue if needed
```

---

## Completion Output

After committing, return ONLY:

```
DONE
Lane: B
Issues: N
```

Nothing else. Keep it minimal for orchestrator context efficiency.

---

## Reference

- Scanner tool: `tools/verify_issue.py --check-halfbaked`
- Issue directory: `issues/B/`
- Full documentation: `issues/B/README.md`
