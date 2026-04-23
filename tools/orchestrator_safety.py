#!/usr/bin/env python3
"""
the system Orchestrator Safety Module (Z-25)
=====================================

Comprehensive safety controls for autonomous agent operation:
- Forbidden pattern detection
- Write boundary enforcement
- Output validation pipeline
- Human approval gates
- Safety audit logging
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# =============================================================================
# FORBIDDEN PATTERNS
# =============================================================================

FORBIDDEN_PATTERNS = {
    "file_destruction": [
        r"rm\s+-rf\s+/",
        r"rm\s+-rf\s+\*",
        r"rm\s+-r\s+/",
        r"rmdir\s+/",
        r">\s*/dev/",
        r"truncate\s+-s\s+0",
    ],
    "db_destruction": [
        r"DROP\s+TABLE",
        r"DROP\s+DATABASE",
        r"DELETE\s+FROM\s+\w+\s*;",
        r"TRUNCATE\s+TABLE",
    ],
    "system_compromise": [
        r"chmod\s+777",
        r"chmod\s+-R\s+777",
        r"chown\s+root",
        r"sudo\s+rm",
        r"curl.*\|\s*bash",
        r"wget.*\|\s*sh",
        r"eval\s*\(",
        r"exec\s*\(",
    ],
    "credential_exposure": [
        r"ANTHROPIC_API_KEY\s*=",
        r"AWS_SECRET",
        r"password\s*=\s*['\"][^'\"]+['\"]",
        r"api_key\s*=\s*['\"]sk-",
        r"secret\s*=\s*['\"][^'\"]+['\"]",
    ],
    "network_exfil": [
        r"curl\s+-d",
        r"wget\s+--post",
        r"nc\s+-e",
        r"netcat",
    ],
    "git_destructive": [
        r"git\s+push\s+--force",
        r"git\s+push\s+-f",
        r"git\s+reset\s+--hard",
        r"git\s+clean\s+-fd",
    ],
}

# =============================================================================
# WRITE BOUNDARIES
# =============================================================================

AGENT_WRITE_BOUNDARIES = {
    "pm": [
        "LogBook/pm/",
        "LogBook/escalations/",
        "issues/",
        "PLANNING/MASTER_PLAN.md",
        "PLANNING/WORK_ORDER_QUEUE.yaml",
        "PLANNING/PROJECT_CONTEXT.md",
        "PLANNING/MILESTONE_TRACKER.md",
        "ISSUE_CATALOG.md",
        ".claude/guidelines/",
    ],
    "fix-verifier": [
        "LogBook/verification/",
        "issues/",
    ],
    "builder": [
        "src/",
        "tools/",
        "templates/",
        ".task/",
    ],
    "planner": [
        "LogBook/progress/plans/",
        ".task/",
    ],
    "critic": [
        "LogBook/critic/",
    ],
    "plan-auditor": [
        "LogBook/critic/",
    ],
}

# Dimension critics have no write boundaries (read-only)
for critic in ["critic-dependencies", "critic-effort", "critic-execution-ready",
               "critic-spec-fit", "critic-verification", "critic-security", "critic-acl"]:
    AGENT_WRITE_BOUNDARIES[critic] = []

# =============================================================================
# HUMAN APPROVAL KEYWORDS
# =============================================================================

REQUIRES_HUMAN_APPROVAL = [
    "delete",
    "remove",
    "drop",
    "truncate",
    "push",
    "deploy",
    "production",
    "destroy",
]

# =============================================================================
# VALIDATION CLASSES
# =============================================================================

@dataclass
class ValidationFailure:
    """A single validation failure"""
    category: str
    pattern: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    details: Optional[str] = None

@dataclass
class ValidationResult:
    """Result of output validation"""
    passed: bool
    failures: List[ValidationFailure] = field(default_factory=list)

class OutputValidator:
    """Validates agent output for safety violations"""

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or Path("LogBook/orchestrator/safety")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def validate(self, agent_name: str, output: str) -> ValidationResult:
        """
        Validate agent output for safety violations.

        Returns ValidationResult with passed=True if safe, False if violations found.
        """
        failures = []

        # Check forbidden patterns
        for category, patterns in FORBIDDEN_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, output, re.IGNORECASE):
                    failures.append(ValidationFailure(
                        category=category,
                        pattern=pattern,
                        severity="CRITICAL"
                    ))

        # Check write boundary violations
        write_paths = self._extract_write_paths(output)
        for path in write_paths:
            if not validate_write_path(agent_name, path):
                failures.append(ValidationFailure(
                    category="write_boundary",
                    pattern=path,
                    severity="HIGH",
                    details=f"Agent {agent_name} not allowed to write to {path}"
                ))

        result = ValidationResult(
            passed=len(failures) == 0,
            failures=failures
        )

        # Log if there were failures
        if not result.passed:
            self._log_violations(agent_name, output, failures)

        return result

    def _extract_write_paths(self, output: str) -> List[str]:
        """Extract potential file write paths from output"""
        paths = []

        # Match common write patterns
        patterns = [
            r"write(?:_to)?\s*\(\s*['\"]([^'\"]+)['\"]",
            r"open\s*\(\s*['\"]([^'\"]+)['\"].*['\"]w['\"]",
            r">\s*([^\s|&;]+)",
            r">>>\s*([^\s|&;]+)",
            r"save(?:_to)?\s*\(\s*['\"]([^'\"]+)['\"]",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, output)
            paths.extend(matches)

        return paths

    def _log_violations(self, agent_name: str, output: str, failures: List[ValidationFailure]):
        """Log safety violations to audit log"""
        if not YAML_AVAILABLE:
            return

        log_file = self.log_dir / "SAFETY_LOG.yaml"

        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "failures": [
                {
                    "category": f.category,
                    "pattern": f.pattern,
                    "severity": f.severity,
                    "details": f.details
                }
                for f in failures
            ],
            "output_snippet": output[:500] if len(output) > 500 else output
        }

        # Append to log
        existing = []
        if log_file.exists():
            with open(log_file) as f:
                data = yaml.safe_load(f) or {}
                existing = data.get("safety_events", [])

        existing.append(entry)

        with open(log_file, 'w') as f:
            yaml.dump({"safety_events": existing[-100:]}, f, default_flow_style=False)

def validate_write_path(agent_name: str, path: str) -> bool:
    """Check if agent is allowed to write to path"""
    allowed = AGENT_WRITE_BOUNDARIES.get(agent_name, [])

    # Normalize path
    path = path.lstrip("./")

    # Check if path is within any allowed boundary
    return any(path.startswith(boundary) for boundary in allowed)

def check_human_approval(action: str, interactive: bool = True) -> bool:
    """
    Check if action requires human approval.

    Args:
        action: The action description to check
        interactive: If True, prompt for approval. If False, just check.

    Returns:
        True if approved or no approval needed, False if denied.
    """
    needs_approval = any(
        keyword in action.lower()
        for keyword in REQUIRES_HUMAN_APPROVAL
    )

    if not needs_approval:
        return True

    if not interactive:
        return False  # Non-interactive mode denies by default

    print(f"\n{'='*60}")
    print("HUMAN APPROVAL REQUIRED")
    print(f"{'='*60}")
    print(f"Action: {action}")
    print(f"{'='*60}")

    try:
        response = input("Approve? (yes/no): ").strip().lower()
        return response == "yes"
    except (EOFError, KeyboardInterrupt):
        return False

# =============================================================================
# CLI
# =============================================================================

def main():
    """Test safety module"""
    print("the system Orchestrator Safety Module (Z-25)")
    print("=" * 50)

    validator = OutputValidator()

    # Test forbidden pattern
    test1 = "rm -rf /tmp/test"
    result1 = validator.validate("builder", test1)
    print(f"\nTest 1: '{test1}'")
    print(f"  Passed: {result1.passed}")
    if result1.failures:
        print(f"  Failures: {[f.pattern for f in result1.failures]}")

    # Test write boundary
    test2 = "write_to('LogBook/pm/decisions/test.yaml')"
    result2 = validator.validate("builder", test2)
    print(f"\nTest 2: '{test2}'")
    print(f"  Passed: {result2.passed}")
    if result2.failures:
        print(f"  Failures: {[f.details for f in result2.failures]}")

    # Test valid write
    test3 = "write_to('src/test.py')"
    result3 = validator.validate("builder", test3)
    print(f"\nTest 3: '{test3}'")
    print(f"  Passed: {result3.passed}")

    print("\nSafety module tests complete.")

if __name__ == "__main__":
    main()
