#!/usr/bin/env python3
"""
PM Promote - Task Promotion Tool for Project Manager

Promotes approved template upgrade tasks after Critic verification.
Updates system to use new template versions and records promotion
decisions in LogBook.

Usage:
    python3 tools/pm_promote.py <task-id>
    python3 tools/pm_promote.py <task-id> --dry-run
    python3 tools/pm_promote.py <task-id> --force
    python3 tools/pm_promote.py --help

Exit Codes:
    0 - Promotion successful
    1 - Promotion failed (not approved, validation error)
    2 - Error (task not found, invalid data, etc.)

Referenced in:
    - PLANNING/TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md:1966

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import re
import yaml
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

class PromotionStatus(Enum):
    """Promotion status types"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"

@dataclass
class PromotionRecord:
    """Record of promotion decision"""
    task_id: str
    timestamp: str
    status: str
    template_name: Optional[str] = None
    old_version: Optional[str] = None
    new_version: Optional[str] = None
    promoted_by: str = "Project-Manager"
    reason: Optional[str] = None
    files_updated: List[str] = field(default_factory=list)
    verdict_reference: Optional[str] = None
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class PMPromoter:
    """Project Manager promotion tool for approved tasks"""

    def __init__(self, task_id: str, dry_run: bool = False,
                 force: bool = False, verbose: bool = False):
        self.task_id = task_id
        self.dry_run = dry_run
        self.force = force
        self.verbose = verbose
        self.repo_root = Path.cwd()
        self.task_dir = None
        self.task_manifest = None
        self.verdict = None
        self.record = PromotionRecord(
            task_id=task_id,
            timestamp=datetime.now().isoformat(),
            status=PromotionStatus.PENDING.value,
            dry_run=dry_run
        )

    def log(self, message: str):
        """Log message if verbose mode"""
        if self.verbose:
            print(f"  [DEBUG] {message}")

    def find_task(self) -> bool:
        """Locate task directory and manifest"""
        search_paths = [
            self.repo_root / '.task',
            self.repo_root / 'PLANNING' / 'tasks',
            self.repo_root / 'LogBook' / 'progress' / 'tasks',
        ]

        for base_path in search_paths:
            if not base_path.exists():
                continue

            for task_path in base_path.rglob('task.yaml'):
                try:
                    with open(task_path) as f:
                        manifest = yaml.safe_load(f)
                    if manifest and manifest.get('id') == self.task_id:
                        self.task_dir = task_path.parent
                        self.task_manifest = manifest
                        self.log(f"Found task at: {self.task_dir}")
                        return True
                except:
                    continue

            for task_path in base_path.rglob('task.yml'):
                try:
                    with open(task_path) as f:
                        manifest = yaml.safe_load(f)
                    if manifest and manifest.get('id') == self.task_id:
                        self.task_dir = task_path.parent
                        self.task_manifest = manifest
                        return True
                except:
                    continue

        # Try direct path
        direct_path = self.repo_root / '.task' / 'task.yaml'
        if direct_path.exists():
            try:
                with open(direct_path) as f:
                    manifest = yaml.safe_load(f)
                if manifest:
                    self.task_dir = direct_path.parent
                    self.task_manifest = manifest
                    return True
            except:
                pass

        return False

    def check_critic_approval(self) -> Tuple[bool, Optional[str]]:
        """Verify task is approved by Critic"""
        verdicts_dir = self.repo_root / 'LogBook' / 'critic' / 'verdicts'

        if not verdicts_dir.exists():
            return False, "Verdicts directory not found"

        # Find verdict for this task
        verdict_files = sorted(
            verdicts_dir.glob(f'verdict_{self.task_id}_*.json'),
            reverse=True  # Most recent first
        )

        if not verdict_files:
            # Try alternative naming patterns
            verdict_files = sorted(
                verdicts_dir.glob(f'*{self.task_id}*.json'),
                reverse=True
            )

        if not verdict_files:
            return False, f"No verdict found for task {self.task_id}"

        # Load most recent verdict
        try:
            with open(verdict_files[0]) as f:
                self.verdict = json.load(f)
        except json.JSONDecodeError as e:
            return False, f"Invalid verdict JSON: {e}"

        self.record.verdict_reference = str(verdict_files[0])

        # Check approval status
        status = self.verdict.get('overall_status', '')

        if status in ['APPROVED', 'APPROVED_WITH_WARNINGS']:
            return True, f"Approved ({status})"
        elif status == 'REJECTED':
            return False, f"Task was rejected by Critic"
        else:
            return False, f"Unknown verdict status: {status}"

    def extract_template_info(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract template name and versions from task"""
        if not self.task_manifest:
            return None, None, None

        template = self.task_manifest.get('template', {})

        if isinstance(template, str):
            template_name = template
            new_version = None
            old_version = None
        elif isinstance(template, dict):
            template_name = template.get('name')
            new_version = template.get('version')
            old_version = template.get('previous_version') or template.get('base_version')
        else:
            template_name = None
            new_version = None
            old_version = None

        self.record.template_name = template_name
        self.record.new_version = new_version
        self.record.old_version = old_version

        return template_name, old_version, new_version

    def update_template_registry(self, template_name: str, new_version: str) -> bool:
        """Update template registry with new version"""
        registry_paths = [
            self.repo_root / 'templates' / 'registry.yaml',
            self.repo_root / '.task' / 'template_registry.yaml',
            self.repo_root / 'PLANNING' / 'template_registry.yaml',
        ]

        for registry_path in registry_paths:
            if not registry_path.exists():
                continue

            self.log(f"Updating registry: {registry_path}")

            try:
                with open(registry_path) as f:
                    registry = yaml.safe_load(f) or {}
            except yaml.YAMLError:
                continue

            # Update template version
            templates = registry.get('templates', {})
            if template_name in templates:
                if not self.dry_run:
                    templates[template_name]['version'] = new_version
                    templates[template_name]['updated'] = datetime.now().isoformat()

                    with open(registry_path, 'w') as f:
                        yaml.dump(registry, f, default_flow_style=False)

                self.record.files_updated.append(str(registry_path))
                return True

        return False

    def update_task_status(self) -> bool:
        """Update task status to promoted"""
        if not self.task_manifest or not self.task_dir:
            return False

        manifest_path = self.task_dir / 'task.yaml'
        if not manifest_path.exists():
            manifest_path = self.task_dir / 'task.yml'

        if not manifest_path.exists():
            return False

        if not self.dry_run:
            self.task_manifest['status'] = 'promoted'
            self.task_manifest['promoted_at'] = datetime.now().isoformat()
            self.task_manifest['promoted_by'] = 'Project-Manager'

            with open(manifest_path, 'w') as f:
                yaml.dump(self.task_manifest, f, default_flow_style=False)

        self.record.files_updated.append(str(manifest_path))
        return True

    def archive_task(self) -> bool:
        """Archive promoted task"""
        if not self.task_dir:
            return False

        archive_dir = self.repo_root / 'archives' / 'promoted'
        archive_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_path = archive_dir / f"{self.task_id}_{timestamp}"

        if not self.dry_run:
            try:
                shutil.copytree(self.task_dir, archive_path)
                self.record.files_updated.append(str(archive_path))
                return True
            except Exception as e:
                self.log(f"Archive failed: {e}")
                return False

        return True

    def record_decision(self) -> Path:
        """Record promotion decision in LogBook"""
        decisions_dir = self.repo_root / 'LogBook' / 'pm' / 'decisions'
        decisions_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        decision_file = decisions_dir / f"promote_{self.task_id}_{timestamp}.json"

        if not self.dry_run:
            with open(decision_file, 'w') as f:
                json.dump(self.record.to_dict(), f, indent=2)

        return decision_file

    def notify_agents(self) -> List[str]:
        """Notify relevant agents of template version change"""
        notifications = []

        # Create notification record
        notification = {
            'type': 'template_promotion',
            'task_id': self.task_id,
            'template': self.record.template_name,
            'new_version': self.record.new_version,
            'timestamp': self.record.timestamp,
            'status': self.record.status,
        }

        # Write to notifications directory if it exists
        notifications_dir = self.repo_root / 'LogBook' / 'notifications'
        if notifications_dir.exists() or not self.dry_run:
            notifications_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            notif_file = notifications_dir / f"promotion_{self.task_id}_{timestamp}.json"

            if not self.dry_run:
                with open(notif_file, 'w') as f:
                    json.dump(notification, f, indent=2)

            notifications.append(str(notif_file))

        return notifications

    def promote(self) -> PromotionRecord:
        """Execute promotion workflow"""
        print(f"\n{'='*60}")
        print(f"PM Promote: {self.task_id}")
        if self.dry_run:
            print(f"(DRY RUN - no changes will be made)")
        print(f"{'='*60}\n")

        # Step 1: Find task
        print("1. Locating task...")
        if not self.find_task():
            self.record.status = PromotionStatus.FAILED.value
            self.record.reason = f"Task not found: {self.task_id}"
            print(f"   \033[91m❌ Task not found\033[0m")
            return self.record
        print(f"   \033[92m✓\033[0m Found at: {self.task_dir}")

        # Step 2: Check Critic approval
        print("\n2. Verifying Critic approval...")
        if not self.force:
            approved, message = self.check_critic_approval()
            if not approved:
                self.record.status = PromotionStatus.FAILED.value
                self.record.reason = message
                print(f"   \033[91m❌ {message}\033[0m")
                print("\n   Use --force to promote without approval (not recommended)")
                return self.record
            print(f"   \033[92m✓\033[0m {message}")
        else:
            print(f"   \033[93m⚠\033[0m Skipped (--force used)")

        # Step 3: Extract template info
        print("\n3. Extracting template information...")
        template_name, old_version, new_version = self.extract_template_info()
        if template_name:
            print(f"   Template: {template_name}")
            if old_version and new_version:
                print(f"   Version:  {old_version} → {new_version}")
            elif new_version:
                print(f"   Version:  {new_version}")
        else:
            print(f"   \033[93m⚠\033[0m No template info found")

        # Step 4: Update template registry
        print("\n4. Updating template registry...")
        if template_name and new_version:
            if self.update_template_registry(template_name, new_version):
                print(f"   \033[92m✓\033[0m Registry updated")
            else:
                print(f"   \033[93m⚠\033[0m No registry found (skipped)")
        else:
            print(f"   \033[93m⚠\033[0m Skipped (no template/version)")

        # Step 5: Update task status
        print("\n5. Updating task status...")
        if self.update_task_status():
            print(f"   \033[92m✓\033[0m Status set to 'promoted'")
        else:
            print(f"   \033[93m⚠\033[0m Could not update status")

        # Step 6: Archive task
        print("\n6. Archiving task...")
        if self.archive_task():
            print(f"   \033[92m✓\033[0m Archived to archives/promoted/")
        else:
            print(f"   \033[93m⚠\033[0m Archive skipped")

        # Step 7: Record decision
        print("\n7. Recording decision...")
        self.record.status = PromotionStatus.SUCCESS.value
        decision_path = self.record_decision()
        print(f"   \033[92m✓\033[0m Recorded: {decision_path}")

        # Step 8: Notify agents
        print("\n8. Notifying agents...")
        notifications = self.notify_agents()
        if notifications:
            print(f"   \033[92m✓\033[0m Notifications sent")
        else:
            print(f"   \033[93m⚠\033[0m No notifications sent")

        return self.record

def main():
    parser = argparse.ArgumentParser(
        description='PM Promote - Promote approved tasks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s 772g0622-e29b-41d4-a716-446655440999
    %(prog)s task-123 --dry-run
    %(prog)s task-123 --force --verbose

Exit Codes:
    0 - Promotion successful
    1 - Promotion failed (not approved, validation error)
    2 - Error (task not found, invalid data)
        """
    )

    parser.add_argument('task_id', help='Task ID to promote')
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='Show what would be done without making changes')
    parser.add_argument('-f', '--force', action='store_true',
                        help='Promote without Critic approval (not recommended)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose output')
    parser.add_argument('--json', action='store_true',
                        help='Output promotion record as JSON')

    args = parser.parse_args()

    # Run promotion
    promoter = PMPromoter(
        args.task_id,
        dry_run=args.dry_run,
        force=args.force,
        verbose=args.verbose
    )
    record = promoter.promote()

    # Print summary
    print(f"\n{'='*60}")
    if record.status == PromotionStatus.SUCCESS.value:
        if args.dry_run:
            print(f"\033[92m✅ PROMOTION WOULD SUCCEED\033[0m (dry run)")
        else:
            print(f"\033[92m✅ PROMOTION SUCCESSFUL\033[0m")
    elif record.status == PromotionStatus.FAILED.value:
        print(f"\033[91m❌ PROMOTION FAILED\033[0m")
        if record.reason:
            print(f"   Reason: {record.reason}")
    else:
        print(f"\033[93m⚠️  PROMOTION {record.status.upper()}\033[0m")
    print(f"{'='*60}")

    # Summary
    if record.files_updated:
        print(f"\nFiles updated ({len(record.files_updated)}):")
        for f in record.files_updated[:10]:
            print(f"  - {f}")

    # JSON output
    if args.json:
        print(f"\n{json.dumps(record.to_dict(), indent=2)}")

    # Exit code
    if record.status == PromotionStatus.SUCCESS.value:
        sys.exit(0)
    elif record.status == PromotionStatus.FAILED.value:
        sys.exit(1)
    else:
        sys.exit(2)

if __name__ == '__main__':
    main()
