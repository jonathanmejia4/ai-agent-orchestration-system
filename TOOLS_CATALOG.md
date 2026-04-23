# Tools Catalog & Health Registry

<!-- STATS_START -->
## Catalog Statistics

> **Last Updated:** 2026-04-23 11:32:07

| Total | Working | Broken | Progress |
|-------|---------|--------|----------|
| 255 | 255 | 0 | [████████████████████] 100.0% |

### By Location

| Location | Total | Working | Broken | % |
|----------|-------|---------|--------|---|
| ✅ `.github/workflows/` | 1 | 1 | 0 | 100% |
| ✅ `scripts/` | 3 | 3 | 0 | 100% |
| ✅ `tools/` | 242 | 242 | 0 | 100% |
| ✅ `tools/hooks/` | 9 | 9 | 0 | 100% |

### By Type

| Type | Count |
|------|-------|
| Python | 234 |
| Shell | 20 |
| Workflow | 1 |

<details>
<summary>By Category (click to expand)</summary>

| Category | Total | Working | Broken | % |
|----------|-------|---------|--------|---|
| ✅ CI/CD Core | 1 | 1 | 0 | 100% |
| ✅ Checkers & Scanners | 23 | 23 | 0 | 100% |
| ✅ Critic System | 1 | 1 | 0 | 100% |
| ✅ Dependency Analysis | 8 | 8 | 0 | 100% |
| ✅ Generators | 7 | 7 | 0 | 100% |
| ✅ Health & Monitoring | 6 | 6 | 0 | 100% |
| ✅ Issue & Catalog Mgmt | 8 | 8 | 0 | 100% |
| ✅ LogBook Management | 9 | 9 | 0 | 100% |
| ✅ Merge & Conflict | 6 | 6 | 0 | 100% |
| ✅ Metrics & Reporting | 9 | 9 | 0 | 100% |
| ✅ Notifications | 5 | 5 | 0 | 100% |
| ✅ PM & Promotion | 7 | 7 | 0 | 100% |
| ✅ Policy & Compliance | 6 | 6 | 0 | 100% |
| ✅ Protected Regions | 5 | 5 | 0 | 100% |
| ✅ Recovery & Rollback | 3 | 3 | 0 | 100% |
| ✅ SSOT & Wiring | 1 | 1 | 0 | 100% |
| ✅ Schema Validation | 1 | 1 | 0 | 100% |
| ✅ Security | 3 | 3 | 0 | 100% |
| ✅ Shell Scripts | 10 | 10 | 0 | 100% |
| ✅ Shell Scripts (Other) | 9 | 9 | 0 | 100% |
| ✅ Stage Gate | 2 | 2 | 0 | 100% |
| ✅ Standalone Scripts | 3 | 3 | 0 | 100% |
| ✅ Task Management | 1 | 1 | 0 | 100% |
| ✅ Template Management | 15 | 15 | 0 | 100% |
| ✅ Testing | 4 | 4 | 0 | 100% |
| ✅ Traceability & Audit | 4 | 4 | 0 | 100% |
| ✅ Utilities | 60 | 60 | 0 | 100% |
| ✅ Validation | 18 | 18 | 0 | 100% |
| ✅ Verification | 20 | 20 | 0 | 100% |

### Category Health Status

**Healthy (100%):** 29 categories

**Needs Attention:** None

</details>

<!-- STATS_END -->

<!-- BROKEN_TOOLS_START -->
## Broken Items

> **Purpose:** Quick reference for items that need fixing
> **Usage:** If an item appears here, it has syntax errors or failed validation

| Item | Location | Category | Error | Last Checked |
|------|----------|----------|-------|--------------|
| *None* | - | - | - | - |

<!-- BROKEN_TOOLS_END -->

---

## Quick Reference

### Catalog Management
| Task | Tool | Command |
|------|------|---------|
| Sync tools catalog | `sync_tools_catalog` | `python3 tools/sync_tools_catalog.py` |
| Sync issue catalog stats | `sync_catalog_stats` | `python3 tools/sync_catalog_stats.py` |
| Verify a single issue | `verify_issue` | `python3 tools/verify_issue.py I-01` |
| Verify a lane | `verify_issue` | `python3 tools/verify_issue.py --lane I` |
| Check issue statistics | `issue_stats` | `python3 tools/issue_stats.py` |
| Add new issue | `add_issue` | `python3 tools/add_issue.py G "Title" --severity 7` |
| Scan for half-baked fixes | `verify_issue` | `python3 tools/verify_issue.py --check-halfbaked` |

### Tool Catalog Options
```bash
# Update tool catalog (scan and update stats)
python3 tools/sync_tools_catalog.py

# Check only (don't update)
python3 tools/sync_tools_catalog.py --check

# Verbose output
python3 tools/sync_tools_catalog.py --verbose
```

### Issue Catalog Options
```bash
# Update issue catalog stats
python3 tools/sync_catalog_stats.py

# Check only mode
python3 tools/sync_catalog_stats.py --check

# Verbose output
python3 tools/sync_catalog_stats.py --verbose
```

---

## Tool Categories

### Issue & Catalog Management

| Tool | Status | Description |
|------|--------|-------------|
| `add_issue.py` | Working | Creates new issue files |
| `issue_stats.py` | Working | Generates issue statistics |
| `sync_catalog_stats.py` | Working | Syncs issue catalog statistics |
| `sync_tools_catalog.py` | Working | Syncs tools catalog statistics |
| `verify_issue.py` | Working | Verifies issue resolution and scans for half-baked fixes |
| `validate_issue_frontmatter.py` | Working | Validates issue YAML frontmatter |
| `validate_issue_file.py` | Working | Security validator for issue files (schema, sensitive paths, dangerous shell patterns) |

### Validation & Quality

| Tool | Status | Description |
|------|--------|-------------|
| `schema_validator.py` | Working | Validates YAML/JSON schemas |
| `check_cross_references.py` | Working | Validates cross-references |
| `check_traceability.py` | Working | Verifies requirement traceability |

---

## How the Tools Catalog Works

### Auto-Scanning
The `sync_tools_catalog.py` script scans for:
1. **Tools** (`tools/*.py`, `tools/*.sh`)
2. **Scripts** (`scripts/*.py`, `scripts/*.sh`)
3. **Workflows** (`.github/workflows/*.yml`)
4. **Any executable files** in your repo

### Health Checking
For each file found, it:
1. Checks syntax (Python: `py_compile`, Shell: `bash -n`, YAML: parse)
2. Records working/broken status
3. Updates the statistics section above

### Usage Pattern
```bash
# After adding new tools, run:
python3 tools/sync_tools_catalog.py --verbose

# The catalog updates automatically with:
# - Total count of tools
# - Working vs broken breakdown
# - Category organization
```

---

## Customization

### Adding Tool Categories

Edit `sync_tools_catalog.py` to add your own categories:

```python
CATEGORY_RULES = [
    (r'test.*\.py$', 'Testing'),
    (r'validate.*\.py$', 'Validation'),
    (r'sync.*\.py$', 'Synchronization'),
    # Add your own patterns here
]
```

### Excluding Directories

Edit the `EXCLUDE_DIRS` set:

```python
EXCLUDE_DIRS = {'.git', '__pycache__', 'node_modules', '.venv'}
```

---

## Integration with Issue System

The tools catalog integrates with the issue system:

1. **Lane B (Half-Baked Fixes)**: `verify_issue.py --check-halfbaked` scans for incomplete fixes
2. **Issue Stats**: `issue_stats.py` shows resolution rates by lane
3. **Catalog Sync**: `sync_catalog_stats.py` updates ISSUE_CATALOG.md statistics

---

*Run `python3 tools/sync_tools_catalog.py` to populate this catalog with your actual tools.*


<!-- FUNCTIONAL_TEST_START -->
## Functional Test Results

> **Last Run:** 2026-04-23 11:31:43
> **Mode:** Quick

| Tested | Passed | Failed | Skipped | Errors | Pass Rate |
|--------|--------|--------|---------|--------|-----------|
| 154 | 132 | 22 | 77 | 0 | [█████████████████░░░] 85.7% |

### By Result

| Status | Count | Description |
|--------|-------|-------------|
| ✅ PASS | 132 | Tool runs without error |
| ❌ FAIL | 22 | Tool crashes or returns error |
| ⏭️ SKIP | 77 | Manual-only or sandboxed (use --full) |
| ⚠️ ERROR | 0 | Could not test (timeout, missing deps) |

### By Safety Level

| Level | Count | Test Method |
|-------|-------|-------------|
| SAFE | 139 | Run with `--help` |
| DRY_RUN | 15 | Run with `--dry-run` or `--check` |
| SANDBOXED | 52 | Run in temp directory |
| MANUAL | 25 | Skipped (dangerous) |

### Failed Tools

| Tool | Safety Level | Error |
|------|--------------|-------|
| `approve_action.py` * | dry_run | --dry-run failed: usage: approve_action.py [-h] -- |
| `check_agent_compatibility.py` * | safe | --help failed:  |
| `critic_self_validation.py` * | safe | --help failed: Traceback (most recent call last):
 |
| `generate.py` * | dry_run | --dry-run failed: usage: generate.py [-h] --task T |
| `permission_guardrails.py` * | safe | --help failed:  |
| `pm_promote.py` * | dry_run | --dry-run failed: usage: pm_promote.py [-h] [-n] [ |
| `scan_timestamps.py` * | dry_run | --dry-run failed: usage: scan_timestamps.py [-h] [ |
| `schema_validator.py` | safe | --help failed:  |
| `stage_gate_enforcer.py` * | dry_run | --dry-run failed:  |
| `stage_promotion.py` * | dry_run | --dry-run failed: usage: stage_promotion.py [-h] { |
| `template_metadata_generator.py` * | dry_run | --dry-run failed:  |
| `template_registry_manager.py` * | dry_run | --dry-run failed: usage: template_registry_manager |
| `template_upgrade_assistant.py` * | dry_run | --dry-run failed: usage: template_upgrade_assistan |
| `time_box_monitor.py` * | safe | --help failed: Traceback (most recent call last):
 |
| `traceability_checker.py` * | safe | --help failed:  |
| `validate_environment.py` * | safe | --help failed:  |
| `validate_issue_file.py` * | safe | --help failed: error: not found: --help
 |
| `validate_work_order.py` * | safe | --help failed:  |
| `verify_all_resolved.py` | safe | --help failed: Traceback (most recent call last):
 |
| `verify_optimization.py` * | safe | --help failed:  |
| `verify_phase2.py` * | safe | --help failed:  |
| `verify_phase3.py` * | safe | --help failed:  |

### Auto-Classified Tools (132 tools)

> These tools are not in `tool_safety_config.yaml` and were classified automatically.
> Add them to the config file for explicit control.

| Tool | Detected Level | Reason |
|------|----------------|--------|
| `access_control_validator.py` | safe | Auto-detected |
| `account_merge_tool.py` | dry_run | Auto-detected |
| `add_pattern_vars.py` | sandboxed | Auto-detected |
| `add_permission_handling_to_lanes.py` | sandboxed | Auto-detected |
| `agent_session_state.py` | sandboxed | Auto-detected |
| `ai_adapter.py` | sandboxed | Auto-detected |
| `alert_manager.py` | manual | Auto-detected |
| `alt_branch_stats.py` | safe | Auto-detected |
| `approve_action.py` | dry_run | Auto-detected |
| `approve_preview.py` | manual | Auto-detected |
| `ast_merge_engine.py` | sandboxed | Auto-detected |
| `audit_trail_validator.py` | safe | Auto-detected |
| `auto_resolution.py` | sandboxed | Auto-detected |
| `bias_detector.py` | sandboxed | Auto-detected |
| `breaking_change_frequency.py` | manual | Auto-detected |
| `build_embeddings.py` | sandboxed | Auto-detected |
| `card_expiry_notifier.py` | manual | Auto-detected |
| `causal_mapper.py` | sandboxed | Auto-detected |
| `check_agent_compatibility.py` | safe | Auto-detected |
| `check_canonicalization.py` | safe | Auto-detected |
| ... | ... | 112 more auto-classified |

<!-- FUNCTIONAL_TEST_END -->