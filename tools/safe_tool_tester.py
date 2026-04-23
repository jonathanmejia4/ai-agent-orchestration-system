#!/usr/bin/env python3
"""
Safe Tool Tester - Functionally tests tools without breaking the repo

This script tests tools to verify they actually work, not just compile.
Tools are categorized by safety level and tested appropriately:
- SAFE: Run with --help, check exit code
- DRY_RUN: Run with --dry-run or --check flag
- SANDBOXED: Copy to temp directory, run, cleanup
- MANUAL_ONLY: Skip (too dangerous to auto-test)

Usage:
    python3 tools/safe_tool_tester.py              # Quick mode (SAFE + DRY_RUN)
    python3 tools/safe_tool_tester.py --full       # Include SANDBOXED tools
    python3 tools/safe_tool_tester.py --docker     # Run in container
    python3 tools/safe_tool_tester.py --tool X.py  # Test specific tool
    python3 tools/safe_tool_tester.py --verbose    # Detailed output
"""

import os
import re
import sys
import yaml
import shutil
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

# Base directory
BASE_DIR = Path(__file__).parent.parent
TOOLS_DIR = BASE_DIR / "tools"
CONFIG_PATH = TOOLS_DIR / "tool_safety_config.yaml"
CATALOG_PATH = BASE_DIR / "TOOLS_CATALOG.md"

class SafetyLevel(Enum):
    SAFE = "safe"           # Read-only, can run with --help
    DRY_RUN = "dry_run"     # Has --dry-run or --check flag
    SANDBOXED = "sandboxed" # Needs temp directory
    DOCKER_ONLY = "docker"  # Must run in container
    MANUAL_ONLY = "manual"  # Skip, too dangerous

class TestResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"

@dataclass
class ToolTestResult:
    tool: str
    result: TestResult
    safety_level: SafetyLevel
    message: str
    exit_code: Optional[int] = None
    duration_ms: int = 0
    is_auto_classified: bool = False  # True if not in config file

# Default safety classifications (can be overridden by config file)
DEFAULT_CLASSIFICATIONS = {
    # SAFE - Read-only tools, validators, reporters
    "safe": [
        "issue_stats.py", "dag_validator.py", "schema_validator.py",
        "verify_issue.py", "batch_verify.py", "comprehensive_verify.py",
        "accurate_verify.py", "smart_verify.py", "final_verify.py",
        "ssot_validator.py", "wiring_validator.py", "logbook_validator.py",
        "validate_logbook.py", "validate_action_plan.py",
        "validate_write_boundaries.py", "validate_issue_frontmatter.py",
        "validate_task.py", "validate_task_manifest.py", "validate_state.py",
        "validate_status.py", "validate_pm_state.py", "validate_rollback.py",
        "validate_critic_verdict.py", "validate_environment.py",
        "check_cross_references.py", "check_traceability.py", "check_dependencies.py",
        "circular_dep_detector.py", "find_cycles.py", "topological_sort.py",
        "retired_template_checker.py", "template_version_checker.py",
        "template_drift_detector.py", "template_compliance_checker.py",
        "convention_checker.py", "code_quality_analyzer.py", "pii_scanner.py",
        "security_scanner.py", "access_control_validator.py",
        "traceability_checker.py", "audit_trail_validator.py",
        "coverage_reporter.py", "doc_coverage.py", "progress_reporter.py",
        "metric_aggregator.py", "qa_metrics_collector.py",
        "health_monitor.py", "agent_health_monitor.py", "system_health_check.py",
        "gate_validator.py", "stage_gate_enforcer.py", "family_validator.py",
        "plugin_validator.py", "variant_validator.py",
        "idempotence_validator.py", "fixture_validator.py", "lisp_syntax_checker.py",
        "env_config_validator.py", "api_docs_validator.py",
        "extension_point_validator.py", "escape_hatch_validator.py",
        "policy_version_checker.py", "version_compatibility_checker.py",
        "version_pin_checker.py", "breaking_change_frequency.py",
        "critical_path_analyzer.py", "dependency_analyzer.py", "causal_mapper.py",
        "parallel_work_estimator.py", "change_impact_analyzer.py",
        "test_coverage_checker.py", "test_mirror_checker.py",
        "protected_paths_checker.py", "protected_regions_validator.py",
        "naming_pattern_checker.py", "fixture_suffix_checker.py",
        "embedded_test_data_checker.py", "spec_compliance_checker.py",
        "variant_symmetry_checker.py", "plugin_compatibility_checker.py",
        "check_agent_compatibility.py", "check_canonicalization.py",
        "failure_mode_detector.py", "file_integrity_checker.py",
        "markdown_link_checker.py", "template_scanner.py", "task_scanner.py",
        "deprecated_template_scanner.py",
        "template_usage.py", "detect_missing_manifests.py",
        "verify_frontmatter.py", "verify_patterns.py", "verify_stats.py",
        "verify_dashboard.py", "verify_execution_order.py", "verify_optimization.py",
        "verify_security_test_coverage.py", "verify_all_tools.py",
        "verify_all_resolved.py", "verify_phase2.py", "verify_phase3.py",
        "log_aggregator.py", "scan_timestamps.py", "progress_dashboard.py",
        "orchestrator_dashboard.py", "update_dashboard.py",
        "logbook_access_checker.py", "logbook_compliance_report.py",
        "logbook_query.py", "audit.py", "ux_click_audit.py",
        "template_diff_analyzer.py", "template_lineage.py",
        "traceability_mapper.py",
        "compute_dependencies.py", "dag_builder.py",
        "get_base_version.py", "graduation_tracker.py", "task_status_tracker.py",
        "task_lifecycle_tracker.py", "time_box_monitor.py",
        "region_interface_checker.py",
        "region_reuse_detector.py", "alt_branch_stats.py", "agent_session_state.py",
        "validate_ci_references.py", "validate_composition.py",
        "validate_crossrefs.py", "validate_equivalence_contracts.py",
        "validate_escalation.py", "validate_integration_test.py",
        "validate_monitoring.py", "validate_planner_output.py",
        "validate_template_metadata.py", "validate_wo_queue.py",
        "validate_work_order.py",
        "idempotence_checker.py", "compliance_reporter.py",
        "sync_tools_catalog.py",  # Has --check flag but also safe with no args
    ],

    # DRY_RUN - Tools with safe execution flags
    "dry_run": {
        "sync_catalog_stats.py": "--check",
        "restructure_catalog.py": "--dry-run",
        "template_upgrade_assistant.py": "--dry-run",
        "template_upgrade_candidates.py": "--dry-run",
        "pm_promote.py": "--dry-run",
        "stage_promotion.py": "--dry-run",
        "task_rollback.py": "--dry-run",
        "merge_preview.py": "--dry-run",
        "generate_preview.py": "--dry-run",
        "preview_generator.py": "--dry-run",
        "conflict_resolver.py": "--dry-run",
        "three_way_merge.py": "--dry-run",
        "migrate_to_ssot.py": "--dry-run",
    },

    # SANDBOXED - Need temp directory isolation
    "sandboxed": [
        "add_issue.py", "add_issue_to_catalog.py", "add_fix_checklist.py",
        "add_frontmatter.py", "add_pattern_vars.py", "add_resolution_template.py",
        "add_verification_commands.py", "fix_frontmatter.py", "fix_pattern_vars.py",
        "fix_section4.py", "fix_verification_commands.py",
        "logbook_update.py", "logbook_auto_append.py", "logbook_archive.py",
        "logbook_immutability.py", "generate_task.py", "generate_report.py",
        "generate_daily_digest.py", "generate_doc_appendix.py",
        "generate_expected_outputs.py", "generate_security_tests.py",
        "template_metadata_generator.py", "template_registry_manager.py",
        "canonicalize.py", "auto_resolution.py", "auto_resolve.py",
        "update_base_version.py", "update_ssot_section_9.py",
        "update_future_index.py", "regenerate_verification_commands.py",
        "enforce_write_boundaries.py", "policy_enforcement_engine.py",
        "policy_version_control.py", "collect_evidence.py",
    ],

    # MANUAL_ONLY - Too dangerous, skip
    "manual": [
        "orchestrator.py", "orchestrator_recovery.py", "recovery_orchestrator.py",
        "orchestrator_safety.py", "snapshot_manager.py", "checkpoint_runner.py",
        "approve_action.py", "approve_preview.py", "preview_approver.py",
        "promotion_gate.py", "heartbeat_daemon.py", "alert_manager.py",
        "escalation_handler.py", "notification_dispatcher.py", "teams_notifier.py",
        "card_expiry_notifier.py", "account_merge_tool.py", "ast_merge_engine.py",
        "merge_engine.py", "fraud_appeal_processor.py", "password_breach_check.py",
        "critic_review.py", "reconstruct_pm_state.py", "workflow_state_manager.py",
        "smoke_test.py", "test_runner.py", "integration_test_runner.py",
        "run_integration_tests.py", "performance_profiler.py", "sphinx_executor.py",
        "ai_adapter.py", "build_embeddings.py", "generate.py",
        "monetization_health_check.py", "protected_regions.py",
        "send_notification.sh", "eod.sh", "pm_monitor.sh", "retry.sh",
        "setup_saf.sh", "install_hooks.sh", "health_check.sh",
        "logbook_append.sh", "logbook_rollup.sh", "test_idempotence.sh",
        "validate_alt_branch_policy.sh", "validate_tool.sh", "check_builder_scope.sh",
        "dependency_boundary_checker.py",
    ],
}

def load_config() -> Dict:
    """Load safety classifications from config file or use defaults."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Could not load config: {e}")
    return DEFAULT_CLASSIFICATIONS

# Patterns for auto-classification of new tools
SAFE_NAME_PATTERNS = [
    r'^validate_.*\.py$',    # validate_*.py
    r'^verify_.*\.py$',      # verify_*.py
    r'^check_.*\.py$',       # check_*.py
    r'.*_validator\.py$',    # *_validator.py
    r'.*_checker\.py$',      # *_checker.py
    r'.*_scanner\.py$',      # *_scanner.py
    r'.*_analyzer\.py$',     # *_analyzer.py
    r'.*_reporter\.py$',     # *_reporter.py
    r'.*_stats\.py$',        # *_stats.py
    r'.*_audit\.py$',        # *_audit.py
    r'.*_monitor\.py$',      # *_monitor.py (read-only monitors)
]

SANDBOXED_NAME_PATTERNS = [
    r'^add_.*\.py$',         # add_*.py (adds content)
    r'^fix_.*\.py$',         # fix_*.py (modifies content)
    r'^update_.*\.py$',      # update_*.py (updates content)
    r'^generate_.*\.py$',    # generate_*.py (creates files)
    r'^regenerate_.*\.py$',  # regenerate_*.py
]

MANUAL_NAME_PATTERNS = [
    r'.*orchestrator.*\.py$',  # orchestrators
    r'.*daemon.*\.py$',        # daemons
    r'.*notifier.*\.py$',      # notifiers (external)
    r'.*_runner\.py$',         # test runners
    r'.*\.sh$',                # all shell scripts
]

# Code patterns that indicate file writes (SANDBOXED)
FILE_WRITE_PATTERNS = [
    r'open\s*\([^)]+["\']w["\']',           # open(..., 'w')
    r'open\s*\([^)]+["\']a["\']',           # open(..., 'a')
    r'\.write\s*\(',                         # .write(
    r'\.write_text\s*\(',                    # Path.write_text(
    r'\.write_bytes\s*\(',                   # Path.write_bytes(
    r'shutil\.(copy|move|rmtree)',           # shutil operations
    r'os\.(remove|unlink|rmdir|makedirs)',   # os file operations
]

# Code patterns that indicate dangerous operations (MANUAL)
DANGEROUS_PATTERNS = [
    r'subprocess\.(run|call|Popen)',         # subprocess calls
    r'os\.system\s*\(',                      # os.system
    r'requests\.(get|post|put|delete)',      # HTTP requests
    r'urllib',                               # URL operations
    r'smtplib',                              # Email
    r'socket\.',                             # Network sockets
]

# Code patterns that indicate dry-run support
DRYRUN_PATTERNS = [
    r'--dry-run',
    r"'--dry-run'",
    r'"--dry-run"',
    r'--check',
    r"'--check'",
    r'"--check"',
    r'dry_run',
    r'dryrun',
]

def auto_classify_tool(tool_path: Path) -> Tuple[SafetyLevel, Optional[str], bool]:
    """
    Auto-classify a tool based on name patterns and code analysis.

    Returns: (SafetyLevel, dry_run_flag, is_auto_classified)
    """
    name = tool_path.name

    # Check name patterns first (fast)
    for pattern in MANUAL_NAME_PATTERNS:
        if re.match(pattern, name, re.IGNORECASE):
            return SafetyLevel.MANUAL_ONLY, None, True

    for pattern in SANDBOXED_NAME_PATTERNS:
        if re.match(pattern, name, re.IGNORECASE):
            return SafetyLevel.SANDBOXED, None, True

    for pattern in SAFE_NAME_PATTERNS:
        if re.match(pattern, name, re.IGNORECASE):
            return SafetyLevel.SAFE, None, True

    # Read file content for deeper analysis
    try:
        content = tool_path.read_text(errors='ignore')
    except Exception:
        # Can't read file, default to MANUAL for safety
        return SafetyLevel.MANUAL_ONLY, None, True

    # Check for dry-run support
    for pattern in DRYRUN_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            # Try to find the actual flag
            if '--dry-run' in content:
                return SafetyLevel.DRY_RUN, '--dry-run', True
            elif '--check' in content:
                return SafetyLevel.DRY_RUN, '--check', True

    # Check for dangerous patterns (MANUAL)
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, content):
            return SafetyLevel.MANUAL_ONLY, None, True

    # Check for file write patterns (SANDBOXED)
    for pattern in FILE_WRITE_PATTERNS:
        if re.search(pattern, content):
            return SafetyLevel.SANDBOXED, None, True

    # Default: SAFE (but flag as auto-classified so we can track)
    return SafetyLevel.SAFE, None, True

def classify_tool(tool_name: str, config: Dict, tool_path: Optional[Path] = None) -> Tuple[SafetyLevel, Optional[str], bool]:
    """
    Classify a tool by safety level. Returns (level, dry_run_flag, is_auto).

    First checks config file, then falls back to auto-classification.
    """
    # Check explicit config first
    if tool_name in config.get("safe", []):
        return SafetyLevel.SAFE, None, False
    if tool_name in config.get("dry_run", {}):
        return SafetyLevel.DRY_RUN, config["dry_run"][tool_name], False
    if tool_name in config.get("sandboxed", []):
        return SafetyLevel.SANDBOXED, None, False
    if tool_name in config.get("manual", []):
        return SafetyLevel.MANUAL_ONLY, None, False

    # Not in config - use auto-classification
    if tool_path and tool_path.exists():
        return auto_classify_tool(tool_path)

    # Can't analyze, default to MANUAL for safety
    return SafetyLevel.MANUAL_ONLY, None, True

def test_with_help(tool_path: Path, timeout: int = 10) -> ToolTestResult:
    """Test a tool by running it with --help."""
    start = datetime.now()
    try:
        result = subprocess.run(
            ["python3", str(tool_path), "--help"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=BASE_DIR
        )
        duration = int((datetime.now() - start).total_seconds() * 1000)

        if result.returncode == 0:
            return ToolTestResult(
                tool=tool_path.name,
                result=TestResult.PASS,
                safety_level=SafetyLevel.SAFE,
                message="--help succeeded",
                exit_code=0,
                duration_ms=duration
            )
        else:
            return ToolTestResult(
                tool=tool_path.name,
                result=TestResult.FAIL,
                safety_level=SafetyLevel.SAFE,
                message=f"--help failed: {result.stderr[:100]}",
                exit_code=result.returncode,
                duration_ms=duration
            )
    except subprocess.TimeoutExpired:
        return ToolTestResult(
            tool=tool_path.name,
            result=TestResult.ERROR,
            safety_level=SafetyLevel.SAFE,
            message=f"Timeout after {timeout}s"
        )
    except Exception as e:
        return ToolTestResult(
            tool=tool_path.name,
            result=TestResult.ERROR,
            safety_level=SafetyLevel.SAFE,
            message=str(e)[:100]
        )

def test_with_dryrun(tool_path: Path, flag: str, timeout: int = 30) -> ToolTestResult:
    """Test a tool by running it with its dry-run flag."""
    start = datetime.now()
    try:
        result = subprocess.run(
            ["python3", str(tool_path), flag],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=BASE_DIR
        )
        duration = int((datetime.now() - start).total_seconds() * 1000)

        # Exit code 0 or 1 are both acceptable (1 might mean "found issues")
        if result.returncode in [0, 1]:
            return ToolTestResult(
                tool=tool_path.name,
                result=TestResult.PASS,
                safety_level=SafetyLevel.DRY_RUN,
                message=f"{flag} succeeded (exit {result.returncode})",
                exit_code=result.returncode,
                duration_ms=duration
            )
        else:
            return ToolTestResult(
                tool=tool_path.name,
                result=TestResult.FAIL,
                safety_level=SafetyLevel.DRY_RUN,
                message=f"{flag} failed: {result.stderr[:100]}",
                exit_code=result.returncode,
                duration_ms=duration
            )
    except subprocess.TimeoutExpired:
        return ToolTestResult(
            tool=tool_path.name,
            result=TestResult.ERROR,
            safety_level=SafetyLevel.DRY_RUN,
            message=f"Timeout after {timeout}s"
        )
    except Exception as e:
        return ToolTestResult(
            tool=tool_path.name,
            result=TestResult.ERROR,
            safety_level=SafetyLevel.DRY_RUN,
            message=str(e)[:100]
        )

def create_sandbox() -> Path:
    """Create a minimal sandbox copy of the repo."""
    sandbox = Path(tempfile.mkdtemp(prefix="saf_sandbox_"))

    # Copy essential directories
    dirs_to_copy = ["tools", "PLANNING", "issues", "templates", ".task"]
    files_to_copy = ["TOOLS_CATALOG.md", "ISSUE_CATALOG.md", "CLAUDE.md"]

    for dir_name in dirs_to_copy:
        src = BASE_DIR / dir_name
        if src.exists():
            shutil.copytree(src, sandbox / dir_name, dirs_exist_ok=True)

    for file_name in files_to_copy:
        src = BASE_DIR / file_name
        if src.exists():
            shutil.copy2(src, sandbox / file_name)

    # Create empty LogBook structure
    (sandbox / "LogBook").mkdir(exist_ok=True)

    return sandbox

def test_sandboxed(tool_path: Path, timeout: int = 60) -> ToolTestResult:
    """Test a tool in a sandboxed temp directory."""
    sandbox = None
    start = datetime.now()
    try:
        sandbox = create_sandbox()
        sandboxed_tool = sandbox / "tools" / tool_path.name

        if not sandboxed_tool.exists():
            return ToolTestResult(
                tool=tool_path.name,
                result=TestResult.ERROR,
                safety_level=SafetyLevel.SANDBOXED,
                message="Tool not found in sandbox"
            )

        result = subprocess.run(
            ["python3", str(sandboxed_tool), "--help"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=sandbox
        )
        duration = int((datetime.now() - start).total_seconds() * 1000)

        if result.returncode == 0:
            return ToolTestResult(
                tool=tool_path.name,
                result=TestResult.PASS,
                safety_level=SafetyLevel.SANDBOXED,
                message="Sandboxed --help succeeded",
                exit_code=0,
                duration_ms=duration
            )
        else:
            return ToolTestResult(
                tool=tool_path.name,
                result=TestResult.FAIL,
                safety_level=SafetyLevel.SANDBOXED,
                message=f"Sandboxed test failed: {result.stderr[:100]}",
                exit_code=result.returncode,
                duration_ms=duration
            )
    except subprocess.TimeoutExpired:
        return ToolTestResult(
            tool=tool_path.name,
            result=TestResult.ERROR,
            safety_level=SafetyLevel.SANDBOXED,
            message=f"Timeout after {timeout}s"
        )
    except Exception as e:
        return ToolTestResult(
            tool=tool_path.name,
            result=TestResult.ERROR,
            safety_level=SafetyLevel.SANDBOXED,
            message=str(e)[:100]
        )
    finally:
        if sandbox and sandbox.exists():
            shutil.rmtree(sandbox, ignore_errors=True)

def test_in_docker(tool_path: Path, timeout: int = 120) -> ToolTestResult:
    """Test a tool inside Docker container."""
    start = datetime.now()
    try:
        # Check if Docker is available
        docker_check = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10
        )
        if docker_check.returncode != 0:
            return ToolTestResult(
                tool=tool_path.name,
                result=TestResult.SKIP,
                safety_level=SafetyLevel.DOCKER_ONLY,
                message="Docker not available"
            )

        # Run tool in container
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{BASE_DIR}:/app:ro",
                "-w", "/app",
                "python:3.11-slim",
                "python3", f"tools/{tool_path.name}", "--help"
            ],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        duration = int((datetime.now() - start).total_seconds() * 1000)

        if result.returncode == 0:
            return ToolTestResult(
                tool=tool_path.name,
                result=TestResult.PASS,
                safety_level=SafetyLevel.DOCKER_ONLY,
                message="Docker test succeeded",
                exit_code=0,
                duration_ms=duration
            )
        else:
            return ToolTestResult(
                tool=tool_path.name,
                result=TestResult.FAIL,
                safety_level=SafetyLevel.DOCKER_ONLY,
                message=f"Docker test failed: {result.stderr[:100]}",
                exit_code=result.returncode,
                duration_ms=duration
            )
    except subprocess.TimeoutExpired:
        return ToolTestResult(
            tool=tool_path.name,
            result=TestResult.ERROR,
            safety_level=SafetyLevel.DOCKER_ONLY,
            message=f"Timeout after {timeout}s"
        )
    except FileNotFoundError:
        return ToolTestResult(
            tool=tool_path.name,
            result=TestResult.SKIP,
            safety_level=SafetyLevel.DOCKER_ONLY,
            message="Docker not installed"
        )
    except Exception as e:
        return ToolTestResult(
            tool=tool_path.name,
            result=TestResult.ERROR,
            safety_level=SafetyLevel.DOCKER_ONLY,
            message=str(e)[:100]
        )

def run_tests(
    full: bool = False,
    docker: bool = False,
    specific_tool: Optional[str] = None,
    verbose: bool = False
) -> List[ToolTestResult]:
    """Run all tests and return results."""
    config = load_config()
    results = []
    auto_classified_count = 0

    # Get all Python tools
    tools = sorted(TOOLS_DIR.glob("*.py"))
    if specific_tool:
        tools = [t for t in tools if t.name == specific_tool]
        if not tools:
            print(f"Tool not found: {specific_tool}")
            return []

    total = len(tools)
    for i, tool_path in enumerate(tools, 1):
        if tool_path.name in ["__init__.py", "safe_tool_tester.py"]:
            continue

        safety_level, dry_run_flag, is_auto = classify_tool(tool_path.name, config, tool_path)

        if is_auto:
            auto_classified_count += 1

        if verbose:
            auto_tag = " [AUTO]" if is_auto else ""
            print(f"[{i}/{total}] Testing {tool_path.name} ({safety_level.value}{auto_tag})...", end=" ", flush=True)

        # Test based on safety level
        if safety_level == SafetyLevel.MANUAL_ONLY:
            result = ToolTestResult(
                tool=tool_path.name,
                result=TestResult.SKIP,
                safety_level=SafetyLevel.MANUAL_ONLY,
                message="Manual-only tool, skipped",
                is_auto_classified=is_auto
            )
        elif docker:
            result = test_in_docker(tool_path)
            result.is_auto_classified = is_auto
        elif safety_level == SafetyLevel.SAFE:
            result = test_with_help(tool_path)
            result.is_auto_classified = is_auto
        elif safety_level == SafetyLevel.DRY_RUN:
            result = test_with_dryrun(tool_path, dry_run_flag)
            result.is_auto_classified = is_auto
        elif safety_level == SafetyLevel.SANDBOXED:
            if full:
                result = test_sandboxed(tool_path)
                result.is_auto_classified = is_auto
            else:
                result = ToolTestResult(
                    tool=tool_path.name,
                    result=TestResult.SKIP,
                    safety_level=SafetyLevel.SANDBOXED,
                    message="Sandboxed, use --full to test",
                    is_auto_classified=is_auto
                )
        else:
            result = test_with_help(tool_path)
            result.is_auto_classified = is_auto

        results.append(result)

        if verbose:
            status = "✅" if result.result == TestResult.PASS else \
                     "❌" if result.result == TestResult.FAIL else \
                     "⏭️" if result.result == TestResult.SKIP else "⚠️"
            print(f"{status} {result.message[:50]}")

    if verbose and auto_classified_count > 0:
        print(f"\n⚠️  {auto_classified_count} tools were auto-classified (not in config file)")

    return results

def generate_progress_bar(percentage: float, width: int = 20) -> str:
    """Generate ASCII progress bar."""
    filled = int(width * percentage / 100)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"

def update_catalog(results: List[ToolTestResult]):
    """Update TOOLS_CATALOG.md with functional test results."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Calculate stats
    total = len(results)
    passed = sum(1 for r in results if r.result == TestResult.PASS)
    failed = sum(1 for r in results if r.result == TestResult.FAIL)
    skipped = sum(1 for r in results if r.result == TestResult.SKIP)
    errors = sum(1 for r in results if r.result == TestResult.ERROR)
    auto_classified = sum(1 for r in results if r.is_auto_classified)

    testable = total - skipped
    pass_rate = (passed / testable * 100) if testable > 0 else 0
    progress_bar = generate_progress_bar(pass_rate)

    # Count by safety level
    by_safety = {}
    for r in results:
        level = r.safety_level.value
        by_safety[level] = by_safety.get(level, 0) + 1

    # Generate functional test section
    func_section = f"""<!-- FUNCTIONAL_TEST_START -->
## Functional Test Results

> **Last Run:** {now}
> **Mode:** {'Full' if any(r.safety_level == SafetyLevel.SANDBOXED and r.result != TestResult.SKIP for r in results) else 'Quick'}

| Tested | Passed | Failed | Skipped | Errors | Pass Rate |
|--------|--------|--------|---------|--------|-----------|
| {testable} | {passed} | {failed} | {skipped} | {errors} | {progress_bar} {pass_rate:.1f}% |

### By Result

| Status | Count | Description |
|--------|-------|-------------|
| ✅ PASS | {passed} | Tool runs without error |
| ❌ FAIL | {failed} | Tool crashes or returns error |
| ⏭️ SKIP | {skipped} | Manual-only or sandboxed (use --full) |
| ⚠️ ERROR | {errors} | Could not test (timeout, missing deps) |

### By Safety Level

| Level | Count | Test Method |
|-------|-------|-------------|
| SAFE | {by_safety.get('safe', 0)} | Run with `--help` |
| DRY_RUN | {by_safety.get('dry_run', 0)} | Run with `--dry-run` or `--check` |
| SANDBOXED | {by_safety.get('sandboxed', 0)} | Run in temp directory |
| MANUAL | {by_safety.get('manual', 0)} | Skipped (dangerous) |

"""

    # Add failed tools section
    failed_results = [r for r in results if r.result == TestResult.FAIL]
    if failed_results:
        func_section += """### Failed Tools

| Tool | Safety Level | Error |
|------|--------------|-------|
"""
        for r in failed_results:
            auto_tag = " *" if r.is_auto_classified else ""
            func_section += f"| `{r.tool}`{auto_tag} | {r.safety_level.value} | {r.message[:50]} |\n"

    # Add error tools section
    error_results = [r for r in results if r.result == TestResult.ERROR]
    if error_results:
        func_section += """
### Tools with Errors

| Tool | Safety Level | Error |
|------|--------------|-------|
"""
        for r in error_results:
            auto_tag = " *" if r.is_auto_classified else ""
            func_section += f"| `{r.tool}`{auto_tag} | {r.safety_level.value} | {r.message[:50]} |\n"

    # Add auto-classified tools section if any
    auto_results = [r for r in results if r.is_auto_classified]
    if auto_results:
        func_section += f"""
### Auto-Classified Tools ({auto_classified} tools)

> These tools are not in `tool_safety_config.yaml` and were classified automatically.
> Add them to the config file for explicit control.

| Tool | Detected Level | Reason |
|------|----------------|--------|
"""
        for r in auto_results[:20]:  # Limit to first 20
            func_section += f"| `{r.tool}` | {r.safety_level.value} | Auto-detected |\n"
        if len(auto_results) > 20:
            func_section += f"| ... | ... | {len(auto_results) - 20} more auto-classified |\n"

    func_section += "\n<!-- FUNCTIONAL_TEST_END -->"

    # Update catalog
    if CATALOG_PATH.exists():
        content = CATALOG_PATH.read_text()

        # Check if functional test section exists
        if "<!-- FUNCTIONAL_TEST_START -->" in content:
            content = re.sub(
                r'<!-- FUNCTIONAL_TEST_START -->.*?<!-- FUNCTIONAL_TEST_END -->',
                func_section,
                content,
                flags=re.DOTALL
            )
        else:
            # Add before TOOL_STATUS section or at end
            if "<!-- TOOL_STATUS_START -->" in content:
                content = content.replace(
                    "<!-- TOOL_STATUS_START -->",
                    f"{func_section}\n\n<!-- TOOL_STATUS_START -->"
                )
            else:
                content += f"\n\n{func_section}"

        CATALOG_PATH.write_text(content)
        print(f"✅ Updated TOOLS_CATALOG.md: {passed}/{testable} tools passing ({pass_rate:.1f}%)")
    else:
        print(f"❌ TOOLS_CATALOG.md not found")

def print_summary(results: List[ToolTestResult]):
    """Print test summary to console."""
    total = len(results)
    passed = sum(1 for r in results if r.result == TestResult.PASS)
    failed = sum(1 for r in results if r.result == TestResult.FAIL)
    skipped = sum(1 for r in results if r.result == TestResult.SKIP)
    errors = sum(1 for r in results if r.result == TestResult.ERROR)

    testable = total - skipped
    pass_rate = (passed / testable * 100) if testable > 0 else 0

    print(f"\n{'='*60}")
    print("FUNCTIONAL TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total Tools: {total}")
    print(f"Testable: {testable}")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  ⏭️ Skipped: {skipped}")
    print(f"  ⚠️ Errors: {errors}")
    print(f"Pass Rate: {pass_rate:.1f}%")

    if failed > 0:
        print(f"\n❌ Failed Tools:")
        for r in results:
            if r.result == TestResult.FAIL:
                print(f"  - {r.tool}: {r.message}")

    if errors > 0:
        print(f"\n⚠️ Error Tools:")
        for r in results:
            if r.result == TestResult.ERROR:
                print(f"  - {r.tool}: {r.message}")

def main():
    """Main entry point."""
    full = "--full" in sys.argv
    docker = "--docker" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    check_only = "--check" in sys.argv

    specific_tool = None
    if "--tool" in sys.argv:
        idx = sys.argv.index("--tool")
        if idx + 1 < len(sys.argv):
            specific_tool = sys.argv[idx + 1]

    if verbose:
        mode = "Docker" if docker else "Full" if full else "Quick"
        print(f"Running functional tests in {mode} mode...")
        if specific_tool:
            print(f"Testing specific tool: {specific_tool}")

    results = run_tests(
        full=full,
        docker=docker,
        specific_tool=specific_tool,
        verbose=verbose
    )

    if not results:
        print("No tools tested")
        sys.exit(1)

    print_summary(results)

    if not check_only:
        update_catalog(results)

    # Exit with error if any failures
    failed = sum(1 for r in results if r.result == TestResult.FAIL)
    sys.exit(1 if failed > 0 else 0)

if __name__ == "__main__":
    main()
