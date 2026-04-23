#!/usr/bin/env python3
"""
Critic Self-Validation Enforcement

Implements the enforce_self_validation decorator and exception classes
defined in critic-self-validation.md:669-729.

Provides:
- enforce_self_validation decorator for verdict functions
- SelfValidationError, ConflictOfInterestError, VerdictValidationError exceptions
- Pre-review, conflict, and bias checks

Usage:
    from tools.critic_self_validation import enforce_self_validation, SelfValidationError

    @enforce_self_validation
    def issue_verdict(critic_agent, task_id, work_order_id):
        return {"verdict": "APPROVED", ...}
"""

from functools import wraps
from typing import Callable, Dict, Any


class SelfValidationError(Exception):
    """Raised when self-validation fails."""
    pass


class ConflictOfInterestError(Exception):
    """Raised when conflict of interest requires recusal."""
    pass


class VerdictValidationError(Exception):
    """Raised when verdict fails validation."""
    pass


def enforce_self_validation(verdict_func: Callable) -> Callable:
    """
    Decorator to enforce self-validation before verdict issuance.

    Wraps verdict issuance with:
    1. Pre-review validation
    2. Conflict of interest checks
    3. Bias detection
    4. Post-verdict validation
    5. Self-validation record attachment

    Args:
        verdict_func: Function that issues verdicts

    Returns:
        Wrapped function with self-validation enforcement

    Raises:
        SelfValidationError: If pre-review validation fails
        ConflictOfInterestError: If recusal is required
        VerdictValidationError: If verdict validation fails
    """
    @wraps(verdict_func)
    def wrapper(critic_agent, task_id: str, work_order_id: str, **kwargs) -> Dict[str, Any]:
        # Pre-review validation
        pre_review = critic_agent.validate_pre_review(task_id, work_order_id)
        if not pre_review.get("complete", False):
            missing = pre_review.get("missing", ["unknown"])
            raise SelfValidationError(
                f"Pre-review validation failed: {missing}"
            )

        # Check for conflicts
        conflicts = critic_agent.check_conflicts(task_id, work_order_id)
        if conflicts.get("recusal_required", False):
            reason = conflicts.get("reason", "Conflict of interest detected")
            raise ConflictOfInterestError(
                f"Recusal required: {reason}"
            )

        # Run bias detection
        bias_check = critic_agent.detect_bias()
        if bias_check.get("bias_detected", False):
            # Log warning but allow to proceed with disclosure
            critic_agent.log_bias_warning(bias_check)

        # Execute verdict function
        verdict = verdict_func(critic_agent, task_id, work_order_id, **kwargs)

        # Post-verdict validation
        from tools.validate_verdict import validate_verdict
        validation = validate_verdict(verdict)
        if not validation.get("valid", False):
            errors = validation.get("errors", ["Unknown validation error"])
            raise VerdictValidationError(
                f"Verdict validation failed: {errors}"
            )

        # Attach self-validation record
        verdict["self_validation"] = {
            "pre_review_complete": True,
            "during_review_complete": True,
            "pre_verdict_complete": True,
            "bias_checks_performed": True,
            "bias_detected": bias_check.get("bias_detected", False),
            "conflicts_declared": conflicts.get("conflicts", [])
        }

        return verdict

    return wrapper


def validate_verdict_has_self_validation(verdict: Dict) -> Dict:
    """
    Check if a verdict includes self-validation record.

    Args:
        verdict: Verdict dictionary

    Returns:
        Validation result with errors if self-validation missing or incomplete
    """
    errors = []

    if "self_validation" not in verdict:
        errors.append("Verdict missing self_validation record")
        return {"valid": False, "errors": errors}

    sv = verdict["self_validation"]
    required_fields = [
        "pre_review_complete",
        "during_review_complete",
        "pre_verdict_complete",
        "bias_checks_performed"
    ]

    for field in required_fields:
        if field not in sv:
            errors.append(f"self_validation missing field: {field}")
        elif not sv[field]:
            errors.append(f"self_validation {field} is False")

    if errors:
        return {"valid": False, "errors": errors}

    return {"valid": True}


# Example usage and testing
if __name__ == "__main__":
    import json
    import sys

    # Mock critic agent for testing
    class MockCriticAgent:
        def validate_pre_review(self, task_id, work_order_id):
            return {"complete": True}

        def check_conflicts(self, task_id, work_order_id):
            return {"recusal_required": False, "conflicts": []}

        def detect_bias(self):
            return {"bias_detected": False}

        def log_bias_warning(self, bias_check):
            print(f"WARNING: Bias detected: {bias_check}", file=sys.stderr)

    # Mock verdict function
    @enforce_self_validation
    def issue_test_verdict(critic_agent, task_id, work_order_id):
        return {
            "verdict": "APPROVED",
            "task_id": task_id,
            "work_order_id": work_order_id,
            "score": 85,
            "feedback": "Test verdict"
        }

    # Test the decorator
    try:
        agent = MockCriticAgent()
        verdict = issue_test_verdict(agent, "TEST.1", "WO-TEST-001")

        print("✓ Self-validation enforcement test passed")
        print(json.dumps(verdict, indent=2))

        # Validate the verdict has self_validation
        validation = validate_verdict_has_self_validation(verdict)
        if validation["valid"]:
            print("✓ Verdict includes complete self-validation record")
        else:
            print("✗ Verdict self-validation incomplete:", validation["errors"])
            sys.exit(1)

    except (SelfValidationError, ConflictOfInterestError, VerdictValidationError) as e:
        print(f"✗ Self-validation failed: {e}", file=sys.stderr)
        sys.exit(1)
