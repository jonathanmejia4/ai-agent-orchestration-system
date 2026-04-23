#!/usr/bin/env python3
"""
Preview Approver - PM Approval Gate for Diff Previews

Provides PM-facing interface for reviewing and approving diff previews
before task execution. Final gate before Builder writes files.

Usage:
    # Interactive approval (default)
    python3 tools/preview_approver.py previews/

    # Approve directly (non-interactive)
    python3 tools/preview_approver.py previews/ --approve

    # Reject directly (non-interactive)
    python3 tools/preview_approver.py previews/ --reject --reason "Security concern"

    # View only (no approval prompt)
    python3 tools/preview_approver.py previews/ --view-only

    # Output approval record
    python3 tools/preview_approver.py previews/ --output approval.json

Exit Codes:
    0 - Approved
    1 - Rejected
    2 - Deferred / Pending
    3 - Error (missing files, invalid manifest, etc.)

Referenced in:
    - SPEC_TO_DIFF_PREVIEWS_POLICY.md:1240, 1604, 1615

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

class ApprovalDecision(Enum):
    """Approval decision types"""
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    PENDING = "pending"

@dataclass
class ApprovalRecord:
    """Record of approval decision"""
    task_id: str
    task_name: str
    preview_generated_at: str
    decision: str
    decided_at: str
    decided_by: str = "PM"
    reason: Optional[str] = None
    risk_level: str = "unknown"
    files_reviewed: int = 0
    additions: int = 0
    deletions: int = 0
    conditions: List[str] = field(default_factory=list)

class PreviewApprover:
    """PM approval interface for diff previews"""

    # ANSI color codes for terminal output
    COLORS = {
        'reset': '\033[0m',
        'bold': '\033[1m',
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'cyan': '\033[96m',
        'gray': '\033[90m',
    }

    def __init__(self, preview_dir: Path, no_color: bool = False):
        self.preview_dir = preview_dir
        self.no_color = no_color
        self.manifest = None
        self.diff_content = None

    def color(self, text: str, color: str) -> str:
        """Apply color to text if colors enabled"""
        if self.no_color:
            return text
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"

    def load_preview(self) -> bool:
        """Load preview manifest and diff"""
        manifest_path = self.preview_dir / 'preview_manifest.yaml'
        diff_path = self.preview_dir / 'preview.diff'

        if not manifest_path.exists():
            print(f"Error: Manifest not found: {manifest_path}", file=sys.stderr)
            return False

        if not diff_path.exists():
            print(f"Error: Diff not found: {diff_path}", file=sys.stderr)
            return False

        try:
            with open(manifest_path, 'r') as f:
                self.manifest = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"Error: Invalid manifest YAML: {e}", file=sys.stderr)
            return False

        self.diff_content = diff_path.read_text()
        return True

    def get_risk_level(self) -> str:
        """Determine risk level from manifest"""
        preview = self.manifest.get('preview', {})
        summary = preview.get('summary', {})

        files_modified = summary.get('files_modified', 0)
        files_deleted = summary.get('files_deleted', 0)
        total_deletions = summary.get('total_deletions', 0)

        if files_deleted > 0 or total_deletions > 100:
            return "high"
        elif files_modified > 5 or total_deletions > 50:
            return "medium"
        elif files_modified > 0:
            return "low"
        else:
            return "minimal"

    def display_summary(self):
        """Display preview summary"""
        preview = self.manifest.get('preview', {})
        summary = preview.get('summary', {})

        print(self.color("=" * 60, 'blue'))
        print(self.color("PREVIEW APPROVAL REQUEST", 'bold'))
        print(self.color("=" * 60, 'blue'))
        print()

        print(f"Task ID:   {preview.get('task_id', 'unknown')}")
        print(f"Task Name: {preview.get('task_name', 'unknown')}")
        print(f"Generated:  {preview.get('generated_at', 'unknown')}")
        print()

        # Summary
        print(self.color("Summary:", 'bold'))
        print(f"  Total Files:  {summary.get('total_files', 0)}")
        print(f"  Created:      {self.color(str(summary.get('files_created', 0)), 'green')}")
        print(f"  Modified:     {self.color(str(summary.get('files_modified', 0)), 'yellow')}")
        print(f"  Deleted:      {self.color(str(summary.get('files_deleted', 0)), 'red')}")
        print(f"  Unchanged:    {summary.get('files_unchanged', 0)}")
        print()

        additions = summary.get('total_additions', 0)
        deletions = summary.get('total_deletions', 0)
        print(f"  Lines Added:   {self.color(f'+{additions}', 'green')}")
        print(f"  Lines Removed: {self.color(f'-{deletions}', 'red')}")
        print()

        # Risk assessment
        risk_level = self.get_risk_level()
        risk_color = {'high': 'red', 'medium': 'yellow', 'low': 'green', 'minimal': 'cyan'}
        print(f"Risk Level: {self.color(risk_level.upper(), risk_color.get(risk_level, 'reset'))}")

        # Approval reasons
        if preview.get('requires_approval'):
            print()
            print(self.color("Requires Approval:", 'yellow'))
            for reason in preview.get('approval_reasons', []):
                print(f"  - {reason}")

        print()

    def display_changes(self):
        """Display list of changes"""
        preview = self.manifest.get('preview', {})
        changes = preview.get('changes', [])

        if not changes:
            print("No changes to review.")
            return

        print(self.color("Changes:", 'bold'))
        for change in changes:
            change_type = change.get('type', 'unknown')
            path = change.get('path', 'unknown')
            additions = change.get('additions', 0)
            deletions = change.get('deletions', 0)

            icon = {
                'create': self.color('[+]', 'green'),
                'modify': self.color('[~]', 'yellow'),
                'delete': self.color('[-]', 'red'),
            }.get(change_type, '[?]')

            stats = f"(+{additions}/-{deletions})"
            print(f"  {icon} {path} {self.color(stats, 'gray')}")

        print()

    def display_diff(self, max_lines: int = 100):
        """Display diff with syntax highlighting"""
        print(self.color("Diff Preview:", 'bold'))
        print(self.color("-" * 60, 'gray'))

        lines = self.diff_content.split('\n')
        displayed = 0

        for line in lines:
            if displayed >= max_lines:
                remaining = len(lines) - displayed
                print(self.color(f"... ({remaining} more lines)", 'gray'))
                break

            if line.startswith('+++') or line.startswith('---'):
                print(self.color(line, 'bold'))
            elif line.startswith('+'):
                print(self.color(line, 'green'))
            elif line.startswith('-'):
                print(self.color(line, 'red'))
            elif line.startswith('@@'):
                print(self.color(line, 'cyan'))
            elif line.startswith('#'):
                print(self.color(line, 'gray'))
            else:
                print(line)

            displayed += 1

        print(self.color("-" * 60, 'gray'))
        print()

    def prompt_decision(self) -> Tuple[ApprovalDecision, Optional[str], List[str]]:
        """Interactive prompt for approval decision"""
        print(self.color("Decision:", 'bold'))
        print("  [A] Approve - Allow Builder to execute changes")
        print("  [R] Reject  - Block execution, require revision")
        print("  [D] Defer   - Postpone decision for later review")
        print("  [V] View    - Show full diff")
        print("  [Q] Quit    - Exit without decision")
        print()

        conditions = []
        reason = None

        while True:
            try:
                choice = input(self.color("Your decision (A/R/D/V/Q): ", 'yellow')).strip().upper()
            except (KeyboardInterrupt, EOFError):
                print("\nOperation cancelled.")
                return ApprovalDecision.PENDING, "Cancelled by user", []

            if choice == 'A':
                # Ask for conditions
                print()
                print("Any conditions for approval? (leave blank for none)")
                condition_input = input("Conditions: ").strip()
                if condition_input:
                    conditions = [c.strip() for c in condition_input.split(',')]
                return ApprovalDecision.APPROVED, None, conditions

            elif choice == 'R':
                # Require reason
                print()
                reason = input("Reason for rejection: ").strip()
                if not reason:
                    print("Rejection requires a reason.")
                    continue
                return ApprovalDecision.REJECTED, reason, []

            elif choice == 'D':
                print()
                reason = input("Reason for deferral (optional): ").strip() or None
                return ApprovalDecision.DEFERRED, reason, []

            elif choice == 'V':
                print()
                self.display_diff(max_lines=500)
                continue

            elif choice == 'Q':
                return ApprovalDecision.PENDING, "User quit without decision", []

            else:
                print("Invalid choice. Please enter A, R, D, V, or Q.")

    def create_approval_record(self, decision: ApprovalDecision,
                                reason: Optional[str],
                                conditions: List[str]) -> ApprovalRecord:
        """Create approval record"""
        preview = self.manifest.get('preview', {})
        summary = preview.get('summary', {})

        return ApprovalRecord(
            task_id=preview.get('task_id', 'unknown'),
            task_name=preview.get('task_name', 'unknown'),
            preview_generated_at=preview.get('generated_at', ''),
            decision=decision.value,
            decided_at=datetime.now().isoformat(),
            reason=reason,
            risk_level=self.get_risk_level(),
            files_reviewed=summary.get('total_files', 0),
            additions=summary.get('total_additions', 0),
            deletions=summary.get('total_deletions', 0),
            conditions=conditions
        )

    def save_approval(self, record: ApprovalRecord, output_path: Optional[Path] = None):
        """Save approval record to file"""
        output_path = output_path or (self.preview_dir / 'approval.json')

        with open(output_path, 'w') as f:
            json.dump(asdict(record), f, indent=2)

        print(f"Approval recorded: {output_path}")

    def run_interactive(self) -> ApprovalRecord:
        """Run interactive approval workflow"""
        if not self.load_preview():
            sys.exit(3)

        self.display_summary()
        self.display_changes()

        # Show abbreviated diff
        preview = self.manifest.get('preview', {})
        if preview.get('requires_approval'):
            self.display_diff(max_lines=30)

        decision, reason, conditions = self.prompt_decision()
        record = self.create_approval_record(decision, reason, conditions)

        return record

    def run_auto_approve(self, reason: Optional[str] = None) -> ApprovalRecord:
        """Auto-approve without prompting"""
        if not self.load_preview():
            sys.exit(3)

        record = self.create_approval_record(
            ApprovalDecision.APPROVED,
            reason or "Auto-approved",
            []
        )
        return record

    def run_auto_reject(self, reason: str) -> ApprovalRecord:
        """Auto-reject without prompting"""
        if not self.load_preview():
            sys.exit(3)

        record = self.create_approval_record(
            ApprovalDecision.REJECTED,
            reason,
            []
        )
        return record

    def run_view_only(self):
        """View preview without approval prompt"""
        if not self.load_preview():
            sys.exit(3)

        self.display_summary()
        self.display_changes()
        self.display_diff(max_lines=500)

# Need to import Tuple for type hints
from typing import Tuple

def main():
    parser = argparse.ArgumentParser(
        description='PM approval gate for diff previews',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s previews/
    %(prog)s previews/ --approve
    %(prog)s previews/ --reject --reason "Security concern"
    %(prog)s previews/ --view-only
        """
    )

    parser.add_argument('preview_dir', type=Path, help='Directory containing preview files')
    parser.add_argument('--approve', '-a', action='store_true',
                        help='Auto-approve without prompting')
    parser.add_argument('--reject', '-r', action='store_true',
                        help='Auto-reject without prompting')
    parser.add_argument('--reason', type=str,
                        help='Reason for approval/rejection')
    parser.add_argument('--view-only', '-v', action='store_true',
                        help='View only, no approval prompt')
    parser.add_argument('--output', '-o', type=Path,
                        help='Output file for approval record')
    parser.add_argument('--no-color', action='store_true',
                        help='Disable colored output')
    parser.add_argument('--json', action='store_true',
                        help='Output approval record as JSON to stdout')

    args = parser.parse_args()

    # Validate inputs
    if not args.preview_dir.exists():
        print(f"Error: Preview directory not found: {args.preview_dir}", file=sys.stderr)
        sys.exit(3)

    if args.reject and not args.reason:
        print("Error: --reject requires --reason", file=sys.stderr)
        sys.exit(3)

    # Create approver
    approver = PreviewApprover(args.preview_dir, no_color=args.no_color)

    # Run appropriate mode
    if args.view_only:
        approver.run_view_only()
        sys.exit(0)

    elif args.approve:
        record = approver.run_auto_approve(args.reason)

    elif args.reject:
        record = approver.run_auto_reject(args.reason)

    else:
        record = approver.run_interactive()

    # Save or output record
    if args.json:
        print(json.dumps(asdict(record), indent=2))
    else:
        approver.save_approval(record, args.output)

        # Print decision summary
        decision = record.decision
        if decision == 'approved':
            print(f"\n{approver.color('APPROVED', 'green')} - Builder may proceed")
        elif decision == 'rejected':
            print(f"\n{approver.color('REJECTED', 'red')} - Changes blocked")
            print(f"Reason: {record.reason}")
        elif decision == 'deferred':
            print(f"\n{approver.color('DEFERRED', 'yellow')} - Decision postponed")
        else:
            print(f"\n{approver.color('PENDING', 'gray')} - No decision made")

    # Exit code based on decision
    exit_codes = {
        'approved': 0,
        'rejected': 1,
        'deferred': 2,
        'pending': 2
    }
    sys.exit(exit_codes.get(record.decision, 3))

if __name__ == '__main__':
    main()
