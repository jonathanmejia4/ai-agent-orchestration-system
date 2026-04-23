#!/usr/bin/env python3
"""
failure_mode_detector.py - the system Failure Mode Detection Tool

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - System Integrity

Purpose:
    Detects potential failure modes in the system state,
    identifies issues before they cause problems.

Usage:
    python3 failure_mode_detector.py --check-all
    python3 failure_mode_detector.py --check state-corruption
    python3 failure_mode_detector.py --continuous --interval 60
"""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# Z-33 Fix: Recovery strategy mapping for detected failure modes
# Z-36 Fix: Use FMD-xxx IDs to avoid semantic conflict with FAILURE_MODES.md FM-xxx IDs
# FAILURE_MODES.md is authoritative for FM-001 through FM-020.
# This detector uses FMD (Failure Mode Detector) prefix for its runtime checks.
RECOVERY_STRATEGIES = {
    "FMD-001": {"strategy": "restore", "severity": "critical", "auto_recover": True},   # State Corruption
    "FMD-002": {"strategy": "restart", "severity": "high", "auto_recover": False},      # Orphaned Work Orders
    "FMD-003": {"strategy": "manual", "severity": "high", "auto_recover": False},       # Stale Escalations
    "FMD-004": {"strategy": "restore", "severity": "high", "auto_recover": True},       # Missing State Files
    "FMD-005": {"strategy": "manual", "severity": "high", "auto_recover": False},       # Invalid YAML
    "FMD-006": {"strategy": "restore", "severity": "medium", "auto_recover": True},     # LogBook Integrity
    "FMD-007": {"strategy": "rollback", "severity": "critical", "auto_recover": False}, # Circular Dependencies
    "FMD-008": {"strategy": "restart", "severity": "medium", "auto_recover": False},    # Agent Conflicts
}

@dataclass
class FailureMode:
    mode_id: str
    name: str
    severity: str
    detected: bool
    details: str = ""
    recommendation: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> dict:
        return {
            "mode_id": self.mode_id,
            "name": self.name,
            "severity": self.severity,
            "detected": self.detected,
            "details": self.details,
            "recommendation": self.recommendation,
            "timestamp": self.timestamp
        }

class FailureModeDetector:
    """Detects potential failure modes in the system."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.results: List[FailureMode] = []

    def check_all(self) -> List[FailureMode]:
        """Run all failure mode checks."""
        checks = [
            self.check_state_corruption,
            self.check_orphaned_work_orders,
            self.check_stale_escalations,
            self.check_missing_state_files,
            self.check_yaml_validity,
            self.check_logbook_integrity,
            self.check_circular_dependencies,
            self.check_agent_conflicts,
        ]

        results = []
        for check in checks:
            result = check()
            results.append(result)

        self.results = results
        return results

    def check_state_corruption(self) -> FailureMode:
        """Check for corrupted state files.

        Note: Uses FMD-001 (Failure Mode Detector ID) to distinguish from
        FM-001 (Timestamps Break Idempotence) in FAILURE_MODES.md.
        Z-36 Fix: Avoid semantic ID conflicts with authoritative catalog.
        """
        mode = FailureMode(
            mode_id="FMD-001",
            name="State Corruption",
            severity="critical",
            detected=False
        )

        state_files = list(self.base_path.glob("LogBook/*/STATE.md"))
        corrupted = []

        for state_file in state_files:
            try:
                content = state_file.read_text()
                if len(content) < 10:
                    corrupted.append(str(state_file))
                elif content.count('\x00') > 0:
                    corrupted.append(str(state_file))
            except Exception as e:
                corrupted.append(f"{state_file}: {e}")

        if corrupted:
            mode.detected = True
            mode.details = f"Corrupted files: {corrupted}"
            mode.recommendation = "Restore from backup or regenerate state files"

        return mode

    def check_orphaned_work_orders(self) -> FailureMode:
        """Check for work orders without assigned agents.

        Note: Uses FMD-002 to distinguish from FM-002 (Non-Canonical Output)
        in FAILURE_MODES.md. Z-36 Fix.
        """
        mode = FailureMode(
            mode_id="FMD-002",
            name="Orphaned Work Orders",
            severity="high",
            detected=False
        )

        wo_queue = self.base_path / "LogBook/pm/WO_QUEUE.yaml"
        if wo_queue.exists() and HAS_YAML:
            try:
                with open(wo_queue) as f:
                    data = yaml.safe_load(f) or {}
                orphaned = []
                stale_in_progress = []
                stale_threshold_hours = 24  # Work orders in progress > 24 hours are stale

                for wo in data.get("work_orders", []):
                    if wo.get("status") == "PENDING" and not wo.get("agent"):
                        orphaned.append(wo.get("work_order_id", "unknown"))
                    # Check for stale in-progress work orders
                    if wo.get("status") == "IN_PROGRESS":
                        started_at = wo.get("started_at") or wo.get("assigned_at")
                        if started_at:
                            try:
                                start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                                hours_elapsed = (datetime.now(start_time.tzinfo) - start_time).total_seconds() / 3600 if start_time.tzinfo else (datetime.now() - start_time.replace(tzinfo=None)).total_seconds() / 3600
                                if hours_elapsed > stale_threshold_hours:
                                    stale_in_progress.append({
                                        "wo_id": wo.get("work_order_id", "unknown"),
                                        "hours_elapsed": round(hours_elapsed, 1)
                                    })
                            except (ValueError, TypeError):
                                # Can't parse timestamp - flag as potentially stale
                                stale_in_progress.append({
                                    "wo_id": wo.get("work_order_id", "unknown"),
                                    "hours_elapsed": "unknown"
                                })

                if orphaned or stale_in_progress:
                    mode.detected = True
                    details_parts = []
                    recommendations = []
                    if orphaned:
                        details_parts.append(f"Orphaned WOs: {orphaned}")
                        recommendations.append("Assign agents to pending work orders")
                    if stale_in_progress:
                        stale_ids = [s["wo_id"] for s in stale_in_progress]
                        details_parts.append(f"Stale IN_PROGRESS WOs (>{stale_threshold_hours}h): {stale_ids}")
                        recommendations.append("Review stale work orders for stuck agents")
                    mode.details = "; ".join(details_parts)
                    mode.recommendation = "; ".join(recommendations)
            except Exception as e:
                mode.details = f"Error checking: {e}"

        return mode

    def check_stale_escalations(self) -> FailureMode:
        """Check for unresolved escalations.

        Note: Uses FMD-003 to distinguish from FM-003 (Missing Wiring File)
        in FAILURE_MODES.md. Z-36 Fix.
        """
        mode = FailureMode(
            mode_id="FMD-003",
            name="Stale Escalations",
            severity="high",
            detected=False
        )

        esc_file = self.base_path / "LogBook/pm/escalations.yaml"
        if esc_file.exists() and HAS_YAML:
            try:
                with open(esc_file) as f:
                    data = yaml.safe_load(f) or {}
                stale = []
                for esc in data.get("escalations", []):
                    if esc.get("status") in ("open", "acknowledged"):
                        stale.append(esc.get("escalation_id", "unknown"))

                if len(stale) > 5:  # Threshold for stale
                    mode.detected = True
                    mode.details = f"Unresolved escalations: {len(stale)}"
                    mode.recommendation = "Review and resolve pending escalations"
            except Exception:
                pass

        return mode

    def check_missing_state_files(self) -> FailureMode:
        """Check for missing required state files.

        Note: Uses FMD-004 to distinguish from FM-004 (Circular Dependencies)
        in FAILURE_MODES.md. Z-36 Fix.
        """
        mode = FailureMode(
            mode_id="FMD-004",
            name="Missing State Files",
            severity="high",
            detected=False
        )

        required = [
            "LogBook/pm/STATE.md",
            "LogBook/builder/STATE.md",
            "LogBook/critic/STATE.md",
        ]

        missing = []
        for path in required:
            if not (self.base_path / path).exists():
                missing.append(path)

        if missing:
            mode.detected = True
            mode.details = f"Missing: {missing}"
            mode.recommendation = "Create missing state files"

        return mode

    def check_yaml_validity(self) -> FailureMode:
        """Check all YAML files for validity.

        Note: Uses FMD-005 to distinguish from FM-005 (Protected Region Corruption)
        in FAILURE_MODES.md. Z-36 Fix.
        """
        mode = FailureMode(
            mode_id="FMD-005",
            name="Invalid YAML",
            severity="high",
            detected=False
        )

        if not HAS_YAML:
            mode.details = "PyYAML not available"
            return mode

        invalid = []
        for yaml_file in self.base_path.glob("**/*.yaml"):
            try:
                with open(yaml_file) as f:
                    yaml.safe_load(f)
            except Exception as e:
                invalid.append(f"{yaml_file.name}: {e}")

        if invalid:
            mode.detected = True
            mode.details = f"Invalid files: {invalid[:5]}"
            mode.recommendation = "Fix YAML syntax errors"

        return mode

    def check_logbook_integrity(self) -> FailureMode:
        """Check LogBook directory integrity.

        Note: Uses FMD-006 to distinguish from FM-006 (SSOT Drift)
        in FAILURE_MODES.md. Z-36 Fix.
        """
        mode = FailureMode(
            mode_id="FMD-006",
            name="LogBook Integrity",
            severity="medium",
            detected=False
        )

        logbook = self.base_path / "LogBook"
        if not logbook.exists():
            mode.detected = True
            mode.details = "LogBook directory missing"
            mode.recommendation = "Create LogBook directory structure"
            return mode

        required_dirs = ["pm", "builder", "critic"]
        missing = []
        for d in required_dirs:
            if not (logbook / d).exists():
                missing.append(d)

        if missing:
            mode.detected = True
            mode.details = f"Missing agent directories: {missing}"
            mode.recommendation = "Create missing agent LogBook directories"

        return mode

    def check_circular_dependencies(self) -> FailureMode:
        """Check for circular work order dependencies.

        Note: Uses FMD-007 to distinguish from FM-007 (Agent Mid-Task Crash)
        in FAILURE_MODES.md. Z-36 Fix.
        """
        mode = FailureMode(
            mode_id="FMD-007",
            name="Circular Dependencies",
            severity="critical",
            detected=False
        )

        wo_queue = self.base_path / "LogBook/pm/WO_QUEUE.yaml"
        if wo_queue.exists() and HAS_YAML:
            try:
                with open(wo_queue) as f:
                    data = yaml.safe_load(f) or {}

                # Build dependency graph
                deps = {}
                for wo in data.get("work_orders", []):
                    wo_id = wo.get("work_order_id")
                    wo_deps = wo.get("dependencies", [])
                    deps[wo_id] = wo_deps

                # Simple cycle detection
                def has_cycle(node, visited, stack):
                    visited.add(node)
                    stack.add(node)
                    for dep in deps.get(node, []):
                        if dep not in visited:
                            if has_cycle(dep, visited, stack):
                                return True
                        elif dep in stack:
                            return True
                    stack.remove(node)
                    return False

                for wo_id in deps:
                    if has_cycle(wo_id, set(), set()):
                        mode.detected = True
                        mode.details = f"Circular dependency involving {wo_id}"
                        mode.recommendation = "Remove circular dependencies"
                        break

            except Exception:
                pass

        return mode

    def check_agent_conflicts(self) -> FailureMode:
        """Check for agent state conflicts.

        Note: Uses FMD-008 to distinguish from FM-008 (Promotion Gate Bypass)
        in FAILURE_MODES.md. Z-36 Fix.
        """
        mode = FailureMode(
            mode_id="FMD-008",
            name="Agent Conflicts",
            severity="medium",
            detected=False
        )

        # Check for multiple agents claiming same work
        wo_queue = self.base_path / "LogBook/pm/WO_QUEUE.yaml"
        if wo_queue.exists() and HAS_YAML:
            try:
                with open(wo_queue) as f:
                    data = yaml.safe_load(f) or {}

                in_progress = {}
                for wo in data.get("work_orders", []):
                    if wo.get("status") == "IN_PROGRESS":
                        agent = wo.get("agent")
                        if agent:
                            if agent not in in_progress:
                                in_progress[agent] = []
                            in_progress[agent].append(wo.get("work_order_id"))

                # Check for agents with too many concurrent items
                for agent, wos in in_progress.items():
                    if len(wos) > 3:  # Threshold
                        mode.detected = True
                        mode.details = f"{agent} has {len(wos)} concurrent work orders"
                        mode.recommendation = "Reduce concurrent work per agent"
                        break

            except Exception:
                pass

        return mode

    # Z-33 Fix: Integration with recovery_orchestrator.py
    def get_recovery_strategy(self, mode_id: str) -> Optional[Dict]:
        """Get recovery strategy for a failure mode."""
        return RECOVERY_STRATEGIES.get(mode_id)

    def trigger_recovery(self, failure_mode: FailureMode, dry_run: bool = False) -> Dict:
        """
        Trigger recovery for a detected failure mode.

        Integrates with tools/recovery_orchestrator.py per FAILURE_MODES.md Section 4.

        Args:
            failure_mode: The detected failure mode
            dry_run: If True, only simulate recovery

        Returns:
            Recovery result dictionary
        """
        strategy_info = self.get_recovery_strategy(failure_mode.mode_id)
        if not strategy_info:
            return {
                "success": False,
                "error": f"No recovery strategy defined for {failure_mode.mode_id}"
            }

        result = {
            "mode_id": failure_mode.mode_id,
            "strategy": strategy_info["strategy"],
            "auto_recover": strategy_info["auto_recover"],
            "dry_run": dry_run,
            "triggered_at": datetime.utcnow().isoformat() + "Z"
        }

        if not strategy_info["auto_recover"] and not dry_run:
            result["success"] = False
            result["message"] = "Manual intervention required - auto-recover disabled for this mode"
            return result

        if dry_run:
            result["success"] = True
            result["message"] = f"Would trigger {strategy_info['strategy']} recovery"
            return result

        # Call recovery_orchestrator.py based on strategy
        try:
            if strategy_info["strategy"] == "restore":
                cmd = [
                    sys.executable, str(self.base_path / "tools/recovery_orchestrator.py"),
                    "recover", "--agent", "system", "--strategy", "restore"
                ]
            elif strategy_info["strategy"] == "rollback":
                cmd = [
                    sys.executable, str(self.base_path / "tools/recovery_orchestrator.py"),
                    "checkpoint", "list", "--limit", "1"
                ]
            elif strategy_info["strategy"] == "restart":
                cmd = [
                    sys.executable, str(self.base_path / "tools/recovery_orchestrator.py"),
                    "recover", "--agent", "system", "--strategy", "restart"
                ]
            else:
                result["success"] = False
                result["message"] = f"Strategy {strategy_info['strategy']} requires manual intervention"
                return result

            proc = subprocess.run(cmd, capture_output=True, text=True)
            result["success"] = proc.returncode == 0
            result["output"] = proc.stdout
            if proc.stderr:
                result["stderr"] = proc.stderr

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)

        return result

    def check_and_recover(self, auto_recover: bool = False, dry_run: bool = False) -> List[Dict]:
        """
        Run all checks and optionally trigger recovery for detected issues.

        Z-33 Fix: Links detection to recovery per FAILURE_MODES.md and ROLLBACK_PROCEDURES.md.

        Args:
            auto_recover: If True, trigger recovery for auto-recoverable modes
            dry_run: If True, simulate recovery actions

        Returns:
            List of check results with recovery status
        """
        results = []
        detected_modes = self.check_all()

        for mode in detected_modes:
            entry = mode.to_dict()
            entry["recovery"] = None

            if mode.detected and auto_recover:
                recovery_result = self.trigger_recovery(mode, dry_run=dry_run)
                entry["recovery"] = recovery_result

            results.append(entry)

        return results

def main():
    parser = argparse.ArgumentParser(description="the system Failure Mode Detector")
    parser.add_argument("--check-all", action="store_true", help="Run all checks")
    parser.add_argument("--check", help="Run specific check")
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=60, help="Check interval (seconds)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any detection")
    # Z-33 Fix: Add auto-recover option to integrate with recovery_orchestrator.py
    parser.add_argument("--auto-recover", action="store_true",
                        help="Automatically trigger recovery for auto-recoverable failure modes")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate recovery actions without executing them")

    args = parser.parse_args()

    detector = FailureModeDetector()

    def run_checks():
        # Z-33 Fix: Use check_and_recover if auto-recover is enabled
        if args.auto_recover:
            results = detector.check_and_recover(
                auto_recover=True,
                dry_run=args.dry_run
            )
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                print("\n" + "=" * 50)
                print("Failure Mode Detection & Recovery Report")
                print("=" * 50)

                detected = [r for r in results if r.get("detected")]
                if detected:
                    print(f"\n{len(detected)} potential issues detected:\n")
                    for r in detected:
                        severity_color = {
                            "critical": "\033[91m",
                            "high": "\033[93m",
                            "medium": "\033[33m"
                        }.get(r.get("severity", ""), "")
                        print(f"{severity_color}[{r.get('severity', 'unknown').upper()}]\033[0m {r.get('name')}")
                        print(f"  {r.get('details')}")
                        print(f"  Recommendation: {r.get('recommendation')}")

                        # Show recovery status
                        recovery = r.get("recovery")
                        if recovery:
                            status = "\033[92mSUCCESS\033[0m" if recovery.get("success") else "\033[91mFAILED\033[0m"
                            print(f"  Recovery: {status} - {recovery.get('strategy', 'N/A')}")
                            if recovery.get("message"):
                                print(f"    {recovery.get('message')}")
                        print()
                else:
                    print("\n\033[92mNo failure modes detected\033[0m")

            return any(r.get("detected") for r in results)
        else:
            results = detector.check_all()

            if args.json:
                print(json.dumps([r.to_dict() for r in results], indent=2))
            else:
                print("\n" + "=" * 50)
                print("Failure Mode Detection Report")
                print("=" * 50)

                detected = [r for r in results if r.detected]
                if detected:
                    print(f"\n{len(detected)} potential issues detected:\n")
                    for r in detected:
                        severity_color = {
                            "critical": "\033[91m",
                            "high": "\033[93m",
                            "medium": "\033[33m"
                        }.get(r.severity, "")
                        print(f"{severity_color}[{r.severity.upper()}]\033[0m {r.name}")
                        print(f"  {r.details}")
                        print(f"  Recommendation: {r.recommendation}")

                        # Z-33 Fix: Show recovery strategy info
                        strategy = detector.get_recovery_strategy(r.mode_id)
                        if strategy:
                            auto_tag = "\033[92m[auto]\033[0m" if strategy["auto_recover"] else "\033[93m[manual]\033[0m"
                            print(f"  Recovery: {strategy['strategy']} {auto_tag}")
                        print()
                else:
                    print("\n\033[92mNo failure modes detected\033[0m")

            return any(r.detected for r in results)

    if args.continuous:
        while True:
            run_checks()
            time.sleep(args.interval)
    else:
        has_issues = run_checks()
        return 1 if (has_issues and args.strict) else 0

if __name__ == "__main__":
    sys.exit(main())
