#!/usr/bin/env python3
"""
Conflict of Interest Declaration Validator

Validates conflict declarations per critic-self-validation.md:610-661.
Ensures Critics declare conflicts before reviewing, following the conflict resolution flow.

Usage:
    python tools/validate_conflict_declaration.py --verdict <path>
    python tools/validate_conflict_declaration.py --declaration <path>
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


class ConflictOfInterestError(Exception):
    """Raised when conflict of interest requires recusal."""
    pass


CONFLICT_TYPES = {
    "SELF_REVIEW",
    "PRIOR_INVOLVEMENT",
    "AGENT_RELATIONSHIP",
    "TIME_PRESSURE",
    "OUTCOME_INTEREST"
}

SEVERITY_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

DECISIONS = {
    "PROCEED_WITH_DISCLOSURE",
    "RECUSE",
    "ESCALATE_TO_PM"
}


def validate_conflict_declaration(declaration: Dict) -> Tuple[bool, List[str]]:
    """
    Validate a conflict declaration structure.

    Args:
        declaration: Conflict declaration dict

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Required top-level fields
    required_fields = ["reviewer", "task_id", "work_order_id", "timestamp"]
    for field in required_fields:
        if field not in declaration:
            errors.append(f"Missing required field: {field}")

    # Must have either conflicts_identified or no_conflicts_statement
    has_conflicts = "conflicts_identified" in declaration
    has_no_conflicts = declaration.get("no_conflicts_statement", False)

    if not has_conflicts and not has_no_conflicts:
        errors.append("Must have either conflicts_identified or no_conflicts_statement=true")

    if has_conflicts and has_no_conflicts:
        errors.append("Cannot have both conflicts_identified and no_conflicts_statement=true")

    # Validate timestamp format
    if "timestamp" in declaration:
        try:
            datetime.fromisoformat(declaration["timestamp"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            errors.append(f"Invalid timestamp format: {declaration.get('timestamp')}")

    # Validate conflicts if present
    if has_conflicts:
        conflicts = declaration.get("conflicts_identified", [])
        if not isinstance(conflicts, list):
            errors.append("conflicts_identified must be a list")
        else:
            for i, conflict in enumerate(conflicts):
                conflict_errors = validate_conflict_entry(conflict, i)
                errors.extend(conflict_errors)

    # Validate recusal_required field
    if "recusal_required" not in declaration:
        errors.append("Missing required field: recusal_required")
    elif not isinstance(declaration["recusal_required"], bool):
        errors.append("recusal_required must be boolean")

    # Check for CRITICAL/HIGH severity conflicts that should trigger recusal
    if has_conflicts and not declaration.get("recusal_required", False):
        critical_conflicts = [
            c for c in declaration.get("conflicts_identified", [])
            if c.get("severity") in ["CRITICAL", "HIGH"]
        ]
        if critical_conflicts:
            errors.append(
                f"CRITICAL/HIGH severity conflicts detected but recusal_required=false. "
                f"Conflicts: {[c.get('type') for c in critical_conflicts]}"
            )

    # Check for self-review or outcome interest (must recuse)
    if has_conflicts:
        must_recuse_types = {"SELF_REVIEW", "OUTCOME_INTEREST"}
        blocking_conflicts = [
            c for c in declaration.get("conflicts_identified", [])
            if c.get("type") in must_recuse_types
        ]
        if blocking_conflicts and not declaration.get("recusal_required", False):
            errors.append(
                f"SELF_REVIEW or OUTCOME_INTEREST conflict requires recusal_required=true. "
                f"Conflicts: {[c.get('type') for c in blocking_conflicts]}"
            )

    return (len(errors) == 0, errors)


def validate_conflict_entry(conflict: Dict, index: int) -> List[str]:
    """Validate a single conflict entry."""
    errors = []
    prefix = f"conflicts_identified[{index}]"

    # Required fields
    required = ["type", "description", "severity", "decision"]
    for field in required:
        if field not in conflict:
            errors.append(f"{prefix}: Missing required field '{field}'")

    # Validate type
    if "type" in conflict and conflict["type"] not in CONFLICT_TYPES:
        errors.append(
            f"{prefix}: Invalid conflict type '{conflict['type']}'. "
            f"Must be one of: {CONFLICT_TYPES}"
        )

    # Validate severity
    if "severity" in conflict and conflict["severity"] not in SEVERITY_LEVELS:
        errors.append(
            f"{prefix}: Invalid severity '{conflict['severity']}'. "
            f"Must be one of: {SEVERITY_LEVELS}"
        )

    # Validate decision
    if "decision" in conflict and conflict["decision"] not in DECISIONS:
        errors.append(
            f"{prefix}: Invalid decision '{conflict['decision']}'. "
            f"Must be one of: {DECISIONS}"
        )

    # Check for SELF_REVIEW or OUTCOME_INTEREST with wrong decision
    if conflict.get("type") in {"SELF_REVIEW", "OUTCOME_INTEREST"}:
        if conflict.get("decision") == "PROCEED_WITH_DISCLOSURE":
            errors.append(
                f"{prefix}: {conflict['type']} requires RECUSE or ESCALATE_TO_PM, "
                "not PROCEED_WITH_DISCLOSURE"
            )

    # Check severity-decision alignment
    severity = conflict.get("severity")
    decision = conflict.get("decision")
    if severity == "CRITICAL" and decision == "PROCEED_WITH_DISCLOSURE":
        errors.append(
            f"{prefix}: CRITICAL severity should not PROCEED_WITH_DISCLOSURE"
        )

    return errors


def validate_verdict_has_conflict_declaration(verdict: Dict) -> Tuple[bool, List[str]]:
    """
    Validate that a verdict includes a conflict declaration.

    Args:
        verdict: Verdict dictionary

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    if "conflict_declaration" not in verdict:
        errors.append("Verdict missing required conflict_declaration field")
        return (False, errors)

    declaration = verdict["conflict_declaration"]
    return validate_conflict_declaration(declaration)


def main():
    parser = argparse.ArgumentParser(
        description="Validate conflict of interest declarations for Critic verdicts"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--verdict",
        help="Path to verdict JSON file (must contain conflict_declaration)"
    )
    group.add_argument(
        "--declaration",
        help="Path to standalone conflict declaration JSON file"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error even on warnings"
    )

    args = parser.parse_args()

    # Load and validate
    try:
        if args.verdict:
            verdict_path = Path(args.verdict)
            if not verdict_path.exists():
                print(f"ERROR: Verdict file not found: {verdict_path}", file=sys.stderr)
                sys.exit(1)

            with open(verdict_path) as f:
                verdict = json.load(f)

            is_valid, errors = validate_verdict_has_conflict_declaration(verdict)
            source = f"verdict {verdict_path}"

        else:  # args.declaration
            declaration_path = Path(args.declaration)
            if not declaration_path.exists():
                print(f"ERROR: Declaration file not found: {declaration_path}", file=sys.stderr)
                sys.exit(1)

            with open(declaration_path) as f:
                declaration = json.load(f)

            is_valid, errors = validate_conflict_declaration(declaration)
            source = f"declaration {declaration_path}"

    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Report results
    if is_valid:
        print(f"✓ Conflict declaration valid: {source}")
        sys.exit(0)
    else:
        print(f"✗ Conflict declaration validation failed: {source}", file=sys.stderr)
        print("\nErrors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
