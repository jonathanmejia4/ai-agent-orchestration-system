#!/usr/bin/env python3
"""
BiasDetector - Automated bias detection for Critic verdicts.

Implements the BiasDetector class defined in critic-self-validation.md:166-294.
Detects agent bias, severity drift, and rubber-stamping patterns in verdict history.

Usage:
    python tools/bias_detector.py --verdict-history <path> [--current-verdict <path>]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


class BiasDetector:
    """Detects potential bias in Critic verdicts."""

    def __init__(self, verdict_history: List[Dict]):
        self.history = verdict_history

    def detect_agent_bias(self, current_verdict: Dict) -> Dict:
        """
        Detect if Critic treats agents differently.

        Returns bias indicators and statistical analysis.
        """
        agent = current_verdict.get("agent")
        verdict = current_verdict.get("verdict")

        # Calculate approval rates by agent
        agent_stats = self._calculate_agent_stats()

        # Check for statistical outliers
        if agent in agent_stats:
            agent_approval_rate = agent_stats[agent]["approval_rate"]
            overall_approval_rate = self._overall_approval_rate()

            deviation = abs(agent_approval_rate - overall_approval_rate)

            if deviation > 0.20:  # 20% deviation threshold
                return {
                    "bias_detected": True,
                    "bias_type": "AGENT_BIAS",
                    "agent": agent,
                    "agent_approval_rate": agent_approval_rate,
                    "overall_rate": overall_approval_rate,
                    "deviation": deviation,
                    "recommendation": "Review verdict for potential agent bias"
                }

        return {"bias_detected": False}

    def detect_severity_drift(self, current_verdict: Dict) -> Dict:
        """
        Detect if severity ratings are drifting over time.
        """
        recent_verdicts = self.history[-20:]  # Last 20 verdicts
        older_verdicts = self.history[-50:-20] if len(self.history) > 50 else []

        if not older_verdicts:
            return {"bias_detected": False, "reason": "Insufficient history"}

        recent_severity_avg = self._average_severity(recent_verdicts)
        older_severity_avg = self._average_severity(older_verdicts)

        drift = recent_severity_avg - older_severity_avg

        if abs(drift) > 0.5:  # Half severity level drift
            drift_type = "INFLATION" if drift > 0 else "DEFLATION"
            return {
                "bias_detected": True,
                "bias_type": f"SEVERITY_{drift_type}",
                "recent_avg": recent_severity_avg,
                "historical_avg": older_severity_avg,
                "drift": drift,
                "recommendation": f"Severity ratings drifting {drift_type.lower()}"
            }

        return {"bias_detected": False}

    def detect_rubber_stamping(self, recent_window: int = 10) -> Dict:
        """
        Detect if Critic is rubber-stamping approvals without thorough review.
        """
        recent = self.history[-recent_window:]

        if not recent:
            return {"bias_detected": False}

        # Check for suspiciously fast reviews
        fast_reviews = [v for v in recent if v.get("review_duration_minutes", 0) < 5]

        # Check for all-approval streaks
        approval_streak = all(v.get("verdict") == "APPROVED" for v in recent)

        # Check for lack of detailed feedback
        shallow_reviews = [v for v in recent if len(v.get("feedback", "")) < 100]

        if len(fast_reviews) > 5 or (approval_streak and len(recent) > 5) or len(shallow_reviews) > 7:
            return {
                "bias_detected": True,
                "bias_type": "RUBBER_STAMPING",
                "fast_reviews": len(fast_reviews),
                "approval_streak": approval_streak,
                "shallow_reviews": len(shallow_reviews),
                "recommendation": "Reviews may lack thoroughness - slow down and provide detailed feedback"
            }

        return {"bias_detected": False}

    def _calculate_agent_stats(self) -> Dict:
        """Calculate verdict statistics by agent."""
        stats = {}
        for verdict in self.history:
            agent = verdict.get("agent", "unknown")
            if agent not in stats:
                stats[agent] = {"total": 0, "approved": 0}
            stats[agent]["total"] += 1
            if verdict.get("verdict") == "APPROVED":
                stats[agent]["approved"] += 1

        for agent in stats:
            if stats[agent]["total"] > 0:
                stats[agent]["approval_rate"] = stats[agent]["approved"] / stats[agent]["total"]
            else:
                stats[agent]["approval_rate"] = 0

        return stats

    def _overall_approval_rate(self) -> float:
        """Calculate overall approval rate."""
        if not self.history:
            return 0.0
        approved = sum(1 for v in self.history if v.get("verdict") == "APPROVED")
        return approved / len(self.history)

    def _average_severity(self, verdicts: List[Dict]) -> float:
        """Calculate average severity from verdicts."""
        severity_map = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        severities = [severity_map.get(v.get("severity", "MEDIUM"), 2) for v in verdicts]
        return sum(severities) / len(severities) if severities else 2.0

    def detect_all(self, current_verdict: Optional[Dict] = None) -> Dict:
        """
        Run all bias detection checks.

        Args:
            current_verdict: Optional current verdict to check against history

        Returns:
            Dictionary with all bias detection results
        """
        results = {
            "bias_checks_performed": [],
            "biases_detected": []
        }

        # Agent bias check
        if current_verdict:
            agent_bias = self.detect_agent_bias(current_verdict)
            results["bias_checks_performed"].append("agent_bias")
            if agent_bias.get("bias_detected"):
                results["biases_detected"].append(agent_bias)

        # Severity drift check
        if current_verdict:
            severity_drift = self.detect_severity_drift(current_verdict)
            results["bias_checks_performed"].append("severity_drift")
            if severity_drift.get("bias_detected"):
                results["biases_detected"].append(severity_drift)

        # Rubber stamping check
        rubber_stamp = self.detect_rubber_stamping()
        results["bias_checks_performed"].append("rubber_stamping")
        if rubber_stamp.get("bias_detected"):
            results["biases_detected"].append(rubber_stamp)

        results["overall_bias_detected"] = len(results["biases_detected"]) > 0

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Detect bias patterns in Critic verdict history"
    )
    parser.add_argument(
        "--verdict-history",
        required=True,
        help="Path to JSON file containing verdict history (array of verdict objects)"
    )
    parser.add_argument(
        "--current-verdict",
        help="Path to JSON file containing current verdict to evaluate (optional)"
    )
    parser.add_argument(
        "--output",
        help="Output file for bias detection results (default: stdout)"
    )

    args = parser.parse_args()

    # Load verdict history
    history_path = Path(args.verdict_history)
    if not history_path.exists():
        print(f"ERROR: Verdict history file not found: {history_path}", file=sys.stderr)
        sys.exit(1)

    with open(history_path) as f:
        verdict_history = json.load(f)

    if not isinstance(verdict_history, list):
        print("ERROR: Verdict history must be a JSON array", file=sys.stderr)
        sys.exit(1)

    # Load current verdict if provided
    current_verdict = None
    if args.current_verdict:
        current_path = Path(args.current_verdict)
        if not current_path.exists():
            print(f"ERROR: Current verdict file not found: {current_path}", file=sys.stderr)
            sys.exit(1)
        with open(current_path) as f:
            current_verdict = json.load(f)

    # Run bias detection
    detector = BiasDetector(verdict_history)
    results = detector.detect_all(current_verdict)

    # Output results
    output_json = json.dumps(results, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output_json)
        print(f"Bias detection results written to {output_path}")
    else:
        print(output_json)

    # Exit with error code if bias detected
    if results["overall_bias_detected"]:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
