# Project Arrow Tools Inventory

> **Last Updated:** 2026-01-08
> **Total Tools:** 24 (23 Python + 1 Shell)

---

## Quick Reference

### Issue Management (Daily Use)

| Task | Tool | Command |
|------|------|---------|
| Sync catalog stats | `sync_catalog_stats` | `python3 tools/sync_catalog_stats.py` |
| Add new issue | `add_issue` | `python3 tools/add_issue.py E "Title" --severity HIGH` |
| Add to catalog | `add_issue_to_catalog` | `python3 tools/add_issue_to_catalog.py add --id G-01 --title "..."` |
| Verify single issue | `verify_issue` | `python3 tools/verify_issue.py E-01` |
| Verify multiple | `batch_verify` | `python3 tools/batch_verify.py --lane E` |
| Full verification | `comprehensive_verify` | `python3 tools/comprehensive_verify.py E-01` |
| Issue statistics | `issue_stats` | `python3 tools/issue_stats.py` |
| Validate frontmatter | `validate_issue_frontmatter` | `python3 tools/validate_issue_frontmatter.py issues/E/E-01.md` |

### Validation & Quality

| Task | Tool | Command |
|------|------|---------|
| Validate schema | `schema_validator` | `python3 tools/schema_validator.py file.yaml schema.yaml` |
| Validate action plan | `validate_action_plan` | `python3 tools/validate_action_plan.py .task/action_plan.yaml` |
| Validate verdict | `validate_verdict` | `python3 tools/validate_verdict.py LogBook/critic/verdict.yaml` |
| Check write boundaries | `validate_write_boundaries` | `python3 tools/validate_write_boundaries.py` |

### Pre-commit Hooks

| Task | Tool | Command |
|------|------|---------|
| SSOT validation | `ssot_validator` | `python3 tools/ssot_validator.py .task/wiring.yaml` |
| DAG validation | `dag_validator` | `python3 tools/dag_validator.py` |
| Template version | `template_version_checker` | `python3 tools/template_version_checker.py --check-only` |
| Retired templates | `retired_template_checker` | `python3 tools/retired_template_checker.py` |
| Cross references | `check_cross_references` | `python3 tools/check_cross_references.py` |
| Traceability | `check_traceability` | `python3 tools/check_traceability.py` |
| Cycle detection | `find_cycles` | `python3 tools/find_cycles.py .task/graph.yaml` |
| Builder scope | `check_builder_scope` | `bash tools/check_builder_scope.sh` |

### LogBook Management

| Task | Tool | Command |
|------|------|---------|
| Update logbook | `logbook_update` | `python3 tools/logbook_update.py` |
| Validate logbook | `logbook_validator` | `python3 tools/logbook_validator.py` |

### Catalog Maintenance

| Task | Tool | Command |
|------|------|---------|
| Restructure catalog | `restructure_catalog` | `python3 tools/restructure_catalog.py --dry-run` |

---

## Tool Descriptions

### Issue Management

#### `sync_catalog_stats.py`
Scans all issue files in `issues/` and updates `ISSUE_CATALOG.md` with accurate statistics.

```bash
python3 tools/sync_catalog_stats.py           # Update catalog
python3 tools/sync_catalog_stats.py --check   # Check only, don't update
python3 tools/sync_catalog_stats.py --verbose # Detailed output
```

#### `add_issue.py`
Creates a new issue file with proper frontmatter and structure.

```bash
python3 tools/add_issue.py E "Missing validation" --severity HIGH
python3 tools/add_issue.py G "Broken link to docs" --severity MEDIUM
```

#### `add_issue_to_catalog.py`
Adds an issue entry to the Open Issues section of `ISSUE_CATALOG.md`.

```bash
python3 tools/add_issue_to_catalog.py add --id E-01 --title "Missing validation" --severity HIGH
python3 tools/add_issue_to_catalog.py list --lane E
```

#### `verify_issue.py`
Verifies that an issue has been properly resolved.

```bash
python3 tools/verify_issue.py E-01            # Verify single issue
python3 tools/verify_issue.py --lane E        # Verify all in lane
python3 tools/verify_issue.py --all           # Verify all issues
```

#### `batch_verify.py`
Verifies multiple issues at once with detailed reporting.

```bash
python3 tools/batch_verify.py --lane E        # Verify lane E
python3 tools/batch_verify.py --all           # Verify everything
python3 tools/batch_verify.py --verbose       # Detailed output
```

#### `comprehensive_verify.py`
Deep verification of issue resolution with multiple checks.

```bash
python3 tools/comprehensive_verify.py E-01
python3 tools/comprehensive_verify.py --all
```

#### `issue_stats.py`
Generates statistics about issues across all lanes.

```bash
python3 tools/issue_stats.py                  # Summary stats
python3 tools/issue_stats.py --detailed       # Per-lane breakdown
python3 tools/issue_stats.py --format json    # JSON output
```

#### `validate_issue_frontmatter.py`
Validates that issue files have correct YAML frontmatter.

```bash
python3 tools/validate_issue_frontmatter.py issues/E/E-01.md
python3 tools/validate_issue_frontmatter.py --all
```

#### `restructure_catalog.py`
Restructures and reorganizes the issue catalog.

```bash
python3 tools/restructure_catalog.py --dry-run  # Preview changes
python3 tools/restructure_catalog.py            # Apply changes
```

### Validation Tools

#### `schema_validator.py`
Generic YAML/JSON schema validation tool.

```bash
python3 tools/schema_validator.py config.yaml PLANNING/schemas/config_schema.yaml
```

#### `validate_action_plan.py`
Validates action plan files against the schema.

```bash
python3 tools/validate_action_plan.py .task/action_plan.yaml
```

#### `validate_verdict.py`
Validates Critic verdict files.

```bash
python3 tools/validate_verdict.py LogBook/critic/verdict.yaml
```

#### `validate_write_boundaries.py`
Checks that agents write only to their allowed paths.

```bash
python3 tools/validate_write_boundaries.py
```

### Pre-commit Hook Tools

#### `ssot_validator.py`
Validates Single Source of Truth (SSOT) wiring files.

```bash
python3 tools/ssot_validator.py .task/wiring.yaml
```

#### `dag_validator.py`
Validates Directed Acyclic Graph (DAG) dependencies.

```bash
python3 tools/dag_validator.py
python3 tools/dag_validator.py .task/graph.yaml
```

#### `template_version_checker.py`
Checks template versions are up-to-date.

```bash
python3 tools/template_version_checker.py --check-only
```

#### `retired_template_checker.py`
Detects usage of retired/deprecated templates.

```bash
python3 tools/retired_template_checker.py
```

#### `check_cross_references.py`
Validates cross-references between files.

```bash
python3 tools/check_cross_references.py
```

#### `check_traceability.py`
Checks traceability of requirements and implementations.

```bash
python3 tools/check_traceability.py
```

#### `find_cycles.py`
Detects cycles in dependency graphs.

```bash
python3 tools/find_cycles.py .task/graph.yaml
```

#### `check_builder_scope.sh`
Shell script to verify builder agent stays within scope.

```bash
bash tools/check_builder_scope.sh
```

### LogBook Tools

#### `logbook_update.py`
Updates LogBook entries with new information.

```bash
python3 tools/logbook_update.py
```

#### `logbook_validator.py`
Validates LogBook structure and entries.

```bash
python3 tools/logbook_validator.py
python3 tools/logbook_validator.py LogBook/issue-hunting/
```

---

## Integration with Pre-commit

These tools are integrated into `.pre-commit-config.yaml`:

```yaml
# Issue catalog sync
- id: catalog-stats-sync
  entry: python3 tools/sync_catalog_stats.py
  files: ^issues/.*\.md$

# Action plan validation
- id: action-plan-validator
  entry: python3 tools/validate_action_plan.py
  files: \.task/action_plan\.yaml$

# And more...
```

Run all hooks:
```bash
pre-commit run --all-files
```

---

## Adding New Tools

1. Create the Python file in `tools/`
2. Add a CLI interface with argparse
3. Update this inventory
4. If needed, add to `.pre-commit-config.yaml`

---

## Dependencies

Most tools only require Python 3 standard library plus:
- `pyyaml` - YAML parsing

Install:
```bash
pip install pyyaml
```
