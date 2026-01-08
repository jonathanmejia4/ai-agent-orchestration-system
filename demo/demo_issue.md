---
# ============================================================
# DEMO / NON-PRODUCTION
# This file demonstrates issue format only
# Real issues use proprietary detection patterns
# ============================================================
issue_id: "X-001"
lane: "X"
severity: 6
severity_level: "MEDIUM"
type_tags: ["DemoIssue", "ConfigurationGap"]
status: "OPEN"
category: "C"
user_approval_required: false
verification_pattern: "file_exists"
verification_depth: "STANDARD"
affected_paths:
  - "config/settings.yaml"
depends_on: []
blocks: []
related: []
---

# [LANE X] Issue X-001: Missing Configuration File

- Type Tags: DemoIssue, ConfigurationGap
- Severity: 6/10 (MEDIUM)
- Status: OPEN
- Category: C (Configuration)
- Date Discovered: 2026-01-07

---

## Problem Description

- **What is wrong:** Configuration file is missing from expected location
- **Expected:** `config/settings.yaml` should exist with required fields
- **Actual:** File does not exist
- **Scope:** Application configuration, startup

## Evidence

```bash
$ test -f config/settings.yaml && echo "EXISTS" || echo "MISSING"
MISSING
```

## Impact Analysis

- **Immediate:** Application may fail to start
- **Downstream:** Default settings may cause unexpected behavior
- **Risk rationale:** MEDIUM severity - recoverable but impacts consistency

## Fix Requirements (DO NOT IMPLEMENT)

- [ ] Create `config/settings.yaml`
- [ ] Add required configuration fields
- [ ] Validate against schema

## Verification Commands

```bash
# Check file exists
test -f config/settings.yaml && echo "PASS" || echo "FAIL"

# Check required fields present
grep -q "app_name:" config/settings.yaml && echo "PASS" || echo "FAIL"
grep -q "version:" config/settings.yaml && echo "PASS" || echo "FAIL"
```

## Dedup Verification

- **Search terms:** "config settings missing"
- **Files checked:** demo/
- **Result:** No duplicates found

---

**NOTE: This is a DEMO issue for showcase purposes only.**
**Real issues contain proprietary detection logic and policies.**
