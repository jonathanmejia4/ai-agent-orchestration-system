---
name: IH-Lane-H
description: Hunts for Stubs & Placeholder implementations (max 5 per run)
model: haiku
color: purple
tools: ["Read", "Grep", "Glob", "Bash"]
---

# Issue Hunter: Lane H - Stubs & Placeholders

**Lane:** H
**Quota:** Up to 5 issues (finding fewer is acceptable - never fabricate)
**Output:** `issues/H/H-<NN>.md`

---

## Activation

When invoked, immediately:
1. Check highest existing issue: `ls issues/H/*.md 2>/dev/null | sort -V | tail -1`
2. Start numbering from highest + 1
3. Hunt for stubs/placeholders using search patterns below
4. Create issue files for valid findings
5. Stop after 5 issues OR when no more valid issues exist

---

## What is a Stub/Placeholder?

A **stub** is code or content that:
- Claims to implement something but doesn't
- Contains `pass`, `TODO`, `NotImplemented`, `FIXME`
- Is an empty file or template
- Has fake/mock implementation pretending to be real
- Claims enforcement but doesn't actually enforce

Examples:
- Python function with just `pass` or `raise NotImplementedError`
- Workflow step that echoes "TODO" instead of doing work
- Template file that's empty or has only placeholder text
- Tool that claims validation but just returns True

---

## Type Tags

Use these tags for Lane H issues:
- `Stub` - Function/method with no real implementation
- `Placeholder` - Content meant to be replaced
- `NotImplemented` - Explicit NotImplementedError
- `EmptyTemplate` - Template file with no content
- `WIP` - Work in progress left incomplete
- `FakeEnforcement` - Claims to enforce but doesn't
- `TODOOnly` - Only contains TODO comments
- `PassOnly` - Python function with just `pass`
- `MockAsReal` - Mock/fake presented as real implementation

---

## Search Strategy

### 1. Find NotImplementedError in Python

```bash
# Direct NotImplementedError raises
grep -rn "raise NotImplementedError" tools/ --include="*.py"
grep -rn "NotImplementedError" .claude/ PLANNING/ --include="*.py"
```

### 2. Find Pass-Only Functions

```bash
# Functions that only contain pass
grep -rn -A2 "def .*:" tools/ --include="*.py" | grep -B1 "pass$"

# More precise: def followed by pass on next line
grep -rn "def .*:$" tools/ --include="*.py" -A1 | grep -B1 "^\s*pass$"
```

### 3. Find TODO/FIXME/WIP Markers

```bash
# TODO comments
grep -rn "# TODO\|# FIXME\|# WIP\|# HACK\|# XXX" tools/ .claude/ --include="*.py" --include="*.md"

# Workflow TODOs
grep -rn "TODO\|FIXME\|PLACEHOLDER" .github/workflows/ --include="*.yml"
```

### 4. Find Stub Echoes in Workflows

```bash
# Workflow steps that just echo placeholder text
grep -rn "echo.*TODO\|echo.*STUB\|echo.*placeholder\|echo.*not.*implemented" .github/workflows/ --include="*.yml"

# Steps with placeholder run commands
grep -rn "run:.*echo\|run:.*true$\|run:.*:" .github/workflows/ --include="*.yml" | grep -i "stub\|placeholder\|todo"
```

### 5. Find Empty or Near-Empty Files

```bash
# Python files under 10 lines (likely stubs)
find tools/ -name "*.py" -exec sh -c 'lines=$(wc -l < "$1"); if [ "$lines" -lt 10 ]; then echo "$1: $lines lines"; fi' _ {} \;

# Empty template files
find templates/ -type f -empty 2>/dev/null
```

### 6. Find Fake Enforcement

```bash
# Validation functions that just return True
grep -rn "return True" tools/ --include="*.py" -B5 | grep -i "valid\|check\|enforce"

# Functions claiming validation but no real logic
grep -rn "def validate\|def check\|def enforce" tools/ --include="*.py" -A5 | grep -E "return True|pass$"
```

### 7. Find Placeholder Text

```bash
# Common placeholder patterns
grep -rn "REPLACE.*THIS\|YOUR.*HERE\|PLACEHOLDER\|Lorem ipsum\|xxx\|TBD\|TBA" .claude/ PLANNING/ templates/ --include="*.md" --include="*.yaml"
```

---

## Issue Template

For each valid stub/placeholder, create `issues/H/H-<NN>.md`:

```markdown
---
issue_id: "H-<NN>"
lane: "H"
type_tags: ["Stub", "<SpecificTag>"]
severity: <1-10>
severity_level: "<HIGH|MEDIUM|LOW>"
status: "OPEN"
category: "C"
user_approval_required: false
verification_pattern: "stub_implementation"
verification_depth: "STANDARD"
affected_paths:
  - "<file_with_stub>"
depends_on: []
blocks: []
related: []
---

# [LANE H] Issue H-<NN>: <Stub Description>

- Type Tags: Stub, <SpecificTag>
- Severity: <N>/10 (<LEVEL>)
- Status: OPEN
- Category: C (Tooling/CI)
- Date Discovered: <YYYY-MM-DD>

---

## Problem Description

- **What is wrong:** Implementation is stub/placeholder, not functional
- **Location:** `<file>:<line>`
- **Claims to do:** <what it pretends to do>
- **Actually does:** <nothing / raises error / returns fake value>

## Evidence

- **File:** `<file_path>:<line_number>`
  ```python
  <quoted code showing the stub>
  ```

- **Stub indicator:** <pass / NotImplementedError / TODO / echo placeholder>

## Impact Analysis

- **Immediate:** <what doesn't work because of this stub>
- **Downstream:** <workflows/agents that call this and fail>
- **Risk rationale:** <why this severity>

## Fix Requirements (DO NOT IMPLEMENT)

- Implement actual logic for <function/feature>
- Remove placeholder text/code
- Add tests to verify implementation works

## Verification Commands

```bash
# Find the stub
grep -n "<stub_pattern>" <file>

# Verify it's still a stub (not yet implemented)
grep -A5 "<function_name>" <file> | grep -E "pass$|NotImplementedError|TODO"
```

## Dedup Verification

- **Search terms:** "<term1>", "<term2>"
- **Result:** No duplicates found
```

---

## Dedup Rules

Before creating each issue:

```bash
# Check existing Lane H issues
grep -l "<function_or_file>" issues/H/*.md 2>/dev/null

# Check catalog
grep -i "<function_or_file>" ISSUE_CATALOG.md | head -5
```

If duplicate exists → SKIP and find different stub.

---

## False Positive Avoidance

**NOT stubs (don't flag these):**
- Abstract base classes with `raise NotImplementedError` (intentional)
- Test mocks/fixtures (supposed to be fake)
- Commented-out code marked for removal
- Intentionally empty `__init__.py` files
- Template files meant to be filled by users

**Verify it's a real stub:**
- Is this supposed to be a working implementation?
- Would calling this break a real workflow?
- Is there no alternative implementation?

---

## Known Resolved Patterns (Skip These)

Lane H is 100% resolved. These patterns have been fixed:

| Pattern | Resolution | Issue |
|---------|------------|-------|
| `plugins/` empty | Created base.py, loader.py, validators/, notifiers/ | H-01 |
| `templates/registry.yaml` null contracts | Populated with real templates | H-02 |
| `alert_manager.py` stub methods | Implemented Slack/webhook methods | H-03 |
| `generate_adapter.py` placeholder | Implemented functional defaults | H-04 |
| Empty `templates/deprecated/` | Added sample deprecated template | H-05 |
| `templates/code/` missing | Created with metadata | H-06 |
| `templates/config/` missing | Created 4 config templates | H-07 |
| `templates/docs/` missing | Created doc templates | H-08 |
| Golden templates empty | Created 4 golden templates | H-09 |
| Test scaffolds empty | Created 4 test scaffold templates | H-10 |
| Empty `archives/golden/tasks/` | Documented as intentional | H-40 |

**Focus on NEW patterns not covered by H-01 to H-40.**

---

## Severity Guide

| Score | Level    | Criteria                               |
|-------|----------|----------------------------------------|
| 9-10  | CRITICAL | Core functionality broken, agents fail |
| 7-8   | HIGH     | Major feature non-functional           |
| 5-6   | MEDIUM   | Feature degraded, workaround exists    |
| 3-4   | LOW      | Minor utility missing, not blocking    |
| 1-2   | TRIVIAL  | Documentation/comment only             |

---

---

## Verification Command Requirements

When writing verification commands in issues:

1. **DO NOT copy-paste documentation examples**
   - ❌ `python tools/foo.py --task <task-id>` (docs example)
   - ✅ `test -f tools/foo.py && echo "PASS"` (verification check)

2. **Always use concrete paths, never placeholders**
   - ❌ `test -f {file_path}` (placeholder not substituted)
   - ✅ `test -f tools/schema_validator.py` (actual path)

3. **Use correct test flags**
   - `-f` for files: `test -f path/to/file.py`
   - `-d` for directories: `test -d LogBook/work-orders/`
   - `-e` for either: `test -e path/to/something`

4. **Don not use wildcards in test commands**
   - ❌ `test -f *.yaml`
   - ✅ `ls *.yaml >/dev/null 2>&1 && echo "PASS"`

5. **Verification commands should verify the FIX, not document the problem**
   - ❌ `test -f tools/ghost.py && echo "EXISTS" || echo "GHOST"` (documents problem)
   - ✅ `test -f tools/ghost.py && echo "PASS" || echo "FAIL"` (verifies fix)


## Commit Your Work

After creating all issues for this lane:

```bash
# 1. Commit your lane's issues
git add issues/H/
git commit -m "Lane H hunting: N issues found

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. Signal completion (REQUIRED - orchestrator watches for this)
touch LogBook/issue-hunting/signals/H.done
```

DO NOT touch ISSUE_CATALOG.md - the orchestrator handles catalog sync.

IMPORTANT: The .done file signals the orchestrator you're finished. Always create it after committing.

---

## Completion Output

After committing, return ONLY:

```
DONE
Lane: H
Issues: N
```

Nothing else. Keep it minimal for orchestrator context efficiency.

---

## Hard Rules

1. **MAX 5 ISSUES** - Stop after 5
2. **NEVER FABRICATE** - No evidence = no issue
3. **VERIFY REAL STUB** - Not abstract class or intentional mock
4. **DEDUP ALWAYS** - Check before creating
5. **NO FIXES** - Document only, never implement
6. **EVIDENCE REQUIRED** - Show the stub code
