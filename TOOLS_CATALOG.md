# Tools Catalog & Health Registry

<!-- STATS_START -->
## Catalog Statistics

> **Last Updated:** 2026-01-10 12:03:27

| Total | Working | Broken | Progress |
|-------|---------|--------|----------|
| 134 | 132 | 2 | [███████████████████░] 98.5% |

### By Location

| Location | Total | Working | Broken | % |
|----------|-------|---------|--------|---|
| 🔴 `.github/workflows/` | 2 | 0 | 2 | 0% |
| ✅ `tools/` | 123 | 123 | 0 | 100% |
| ✅ `tools/hooks/` | 9 | 9 | 0 | 100% |

### By Type

| Type | Count |
|------|-------|
| Python | 112 |
| Shell | 20 |
| Workflow | 2 |

<details>
<summary>By Category (click to expand)</summary>

| Category | Total | Working | Broken | % |
|----------|-------|---------|--------|---|
| ✅ Checkers & Scanners | 11 | 11 | 0 | 100% |
| ✅ Dependency Analysis | 5 | 5 | 0 | 100% |
| ✅ Generators | 2 | 2 | 0 | 100% |
| ✅ Health & Monitoring | 3 | 3 | 0 | 100% |
| ✅ Issue & Catalog Mgmt | 7 | 7 | 0 | 100% |
| ✅ LogBook Management | 6 | 6 | 0 | 100% |
| ✅ Merge & Conflict | 1 | 1 | 0 | 100% |
| ✅ Metrics & Reporting | 6 | 6 | 0 | 100% |
| ✅ Notifications | 2 | 2 | 0 | 100% |
| 🔴 Other Workflows | 2 | 0 | 2 | 0% |
| ✅ Policy & Compliance | 2 | 2 | 0 | 100% |
| ✅ Protected Regions | 9 | 9 | 0 | 100% |
| ✅ Recovery & Rollback | 3 | 3 | 0 | 100% |
| ✅ SSOT & Wiring | 1 | 1 | 0 | 100% |
| ✅ Schema Validation | 1 | 1 | 0 | 100% |
| ✅ Security | 2 | 2 | 0 | 100% |
| ✅ Shell Scripts | 11 | 11 | 0 | 100% |
| ✅ Shell Scripts (Other) | 9 | 9 | 0 | 100% |
| ✅ Stage Gate | 1 | 1 | 0 | 100% |
| ✅ Template Management | 3 | 3 | 0 | 100% |
| ✅ Testing | 3 | 3 | 0 | 100% |
| ✅ Traceability & Audit | 2 | 2 | 0 | 100% |
| ✅ Utilities | 27 | 27 | 0 | 100% |
| ✅ Validation | 3 | 3 | 0 | 100% |
| ✅ Verification | 12 | 12 | 0 | 100% |

### Category Health Status

**Healthy (100%):** 24 categories

**Needs Attention:**
| Category | Progress | Broken |
|----------|----------|--------|
| Other Workflows | 0% | 2 |

</details>

<!-- STATS_END -->

<!-- BROKEN_TOOLS_START -->
## Broken Items

> **Purpose:** Quick reference for items that need fixing
> **Usage:** If an item appears here, it has syntax errors or failed validation

| Item | Location | Category | Error | Last Checked |
|------|----------|----------|-------|--------------|
| `dependency-catalog.yml` | .github/workflows/ | Other Workflows | while scanning a simple key
  in "/Users... | 2026-01-10 |
| `architecture-catalog.yml` | .github/workflows/ | Other Workflows | while scanning a simple key
  in "/Users... | 2026-01-10 |

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
