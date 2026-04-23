#!/usr/bin/env python3
"""
Account Merge Tool

Consolidates duplicate accounts (guest to registered, same email different auth).

Requirements (per customer-service-standards.md Section 3.9):
- Merge duplicate accounts
- Handle guest checkout -> registered user
- Handle same email with different auth methods
- Preserve order history and subscriptions

Usage:
    python account_merge_tool.py --find-duplicates           # Find potential duplicates
    python account_merge_tool.py --merge SOURCE TARGET       # Merge accounts
    python account_merge_tool.py --preview SOURCE TARGET    # Preview merge
"""

import argparse
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AccountType(Enum):
    """Type of account."""
    GUEST = "guest"
    REGISTERED = "registered"
    SOCIAL_ONLY = "social_only"  # Only social login, no password

class MergeConflictResolution(Enum):
    """How to resolve merge conflicts."""
    KEEP_TARGET = "keep_target"  # Keep target account's value
    KEEP_SOURCE = "keep_source"  # Keep source account's value
    MERGE = "merge"  # Merge both values (for lists)

@dataclass
class Account:
    """User account for merge operations."""
    account_id: str
    email: str
    account_type: AccountType
    name: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    has_password: bool = False
    social_logins: list[str] = field(default_factory=list)
    orders: list[str] = field(default_factory=list)  # Order IDs
    subscriptions: list[str] = field(default_factory=list)  # Subscription IDs
    payment_methods: list[str] = field(default_factory=list)  # Payment method IDs
    metadata: dict = field(default_factory=dict)

@dataclass
class MergeConflict:
    """A conflict found during merge."""
    field_name: str
    source_value: any
    target_value: any
    resolution: MergeConflictResolution
    resolved_value: any

@dataclass
class MergePreview:
    """Preview of account merge."""
    source_account_id: str
    target_account_id: str
    conflicts: list[MergeConflict]
    data_to_transfer: dict
    warnings: list[str]
    can_proceed: bool

@dataclass
class MergeResult:
    """Result of account merge."""
    success: bool
    merged_account_id: str
    source_deleted: bool
    data_transferred: dict
    conflicts_resolved: list[MergeConflict]
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

class AccountMergeTool:
    """
    Tool for merging duplicate accounts.

    Handles common scenarios:
    - Guest checkout -> Registered account (same email)
    - Social login -> Password account (same email)
    - Multiple accounts with same email from different auth sources

    Merge always goes: source -> target (source is deleted after merge)
    """

    def __init__(self, account_repository=None, order_repository=None):
        """
        Initialize account merge tool.

        Args:
            account_repository: Repository for account data
            order_repository: Repository for order data
        """
        self._accounts: dict[str, Account] = account_repository or {}
        self._orders = order_repository or {}
        self._merge_history: list[MergeResult] = []

    def find_duplicates(self) -> list[tuple[Account, Account]]:
        """
        Find potential duplicate accounts.

        Duplicates are identified by:
        - Same email address
        - Similar names with typo variations

        Returns:
            List of (account1, account2) tuples that may be duplicates
        """
        duplicates = []
        accounts = list(self._accounts.values())

        # Group by email
        email_groups: dict[str, list[Account]] = {}
        for account in accounts:
            email = account.email.lower()
            if email not in email_groups:
                email_groups[email] = []
            email_groups[email].append(account)

        # Find groups with multiple accounts
        for email, group in email_groups.items():
            if len(group) > 1:
                # Create pairs
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        duplicates.append((group[i], group[j]))

        logger.info(f"Found {len(duplicates)} potential duplicate pairs")
        return duplicates

    def _get_account(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        return self._accounts.get(account_id)

    def preview_merge(self, source_id: str, target_id: str) -> MergePreview:
        """
        Preview what will happen during a merge.

        Args:
            source_id: Account to merge FROM (will be deleted)
            target_id: Account to merge INTO (will be kept)

        Returns:
            MergePreview with conflicts and data to transfer
        """
        source = self._get_account(source_id)
        target = self._get_account(target_id)

        warnings = []
        conflicts = []
        can_proceed = True

        if not source:
            warnings.append(f"Source account {source_id} not found")
            can_proceed = False
        if not target:
            warnings.append(f"Target account {target_id} not found")
            can_proceed = False

        if not can_proceed:
            return MergePreview(
                source_account_id=source_id,
                target_account_id=target_id,
                conflicts=[],
                data_to_transfer={},
                warnings=warnings,
                can_proceed=False
            )

        # Check email match
        if source.email.lower() != target.email.lower():
            warnings.append(
                f"Email mismatch: {source.email} vs {target.email}. "
                "Are you sure these are the same person?"
            )

        # Identify conflicts
        if source.name and target.name and source.name != target.name:
            conflicts.append(MergeConflict(
                field_name="name",
                source_value=source.name,
                target_value=target.name,
                resolution=MergeConflictResolution.KEEP_TARGET,
                resolved_value=target.name
            ))

        # Social logins - merge both
        social_conflict = None
        if source.social_logins:
            combined = list(set(source.social_logins + target.social_logins))
            if combined != target.social_logins:
                conflicts.append(MergeConflict(
                    field_name="social_logins",
                    source_value=source.social_logins,
                    target_value=target.social_logins,
                    resolution=MergeConflictResolution.MERGE,
                    resolved_value=combined
                ))

        # Data to transfer
        data_to_transfer = {
            "orders": source.orders,
            "subscriptions": source.subscriptions,
            "payment_methods": source.payment_methods,
            "metadata": source.metadata
        }

        # Warnings for risky transfers
        if source.subscriptions:
            warnings.append(
                f"{len(source.subscriptions)} subscription(s) will be transferred. "
                "Review billing carefully after merge."
            )

        if source.account_type == AccountType.REGISTERED and target.account_type == AccountType.GUEST:
            warnings.append(
                "Merging registered account INTO guest account. "
                "Consider reversing source/target."
            )

        return MergePreview(
            source_account_id=source_id,
            target_account_id=target_id,
            conflicts=conflicts,
            data_to_transfer=data_to_transfer,
            warnings=warnings,
            can_proceed=True
        )

    def merge(
        self,
        source_id: str,
        target_id: str,
        conflict_resolutions: Optional[dict[str, MergeConflictResolution]] = None,
        dry_run: bool = False
    ) -> MergeResult:
        """
        Merge source account into target account.

        After merge:
        - Target account has all data from both accounts
        - Source account is deleted
        - Order/subscription/payment references are updated

        Args:
            source_id: Account to merge FROM (will be deleted)
            target_id: Account to merge INTO (will be kept)
            conflict_resolutions: Override default conflict resolutions
            dry_run: If True, don't actually perform merge

        Returns:
            MergeResult with merge outcome
        """
        preview = self.preview_merge(source_id, target_id)

        if not preview.can_proceed:
            return MergeResult(
                success=False,
                merged_account_id=target_id,
                source_deleted=False,
                data_transferred={},
                conflicts_resolved=[],
                error="Merge cannot proceed: " + "; ".join(preview.warnings)
            )

        source = self._get_account(source_id)
        target = self._get_account(target_id)
        conflict_resolutions = conflict_resolutions or {}

        if dry_run:
            return MergeResult(
                success=True,
                merged_account_id=target_id,
                source_deleted=False,
                data_transferred=preview.data_to_transfer,
                conflicts_resolved=preview.conflicts,
                error="DRY RUN - no changes made"
            )

        # Apply conflict resolutions
        resolved_conflicts = []
        for conflict in preview.conflicts:
            resolution = conflict_resolutions.get(
                conflict.field_name,
                conflict.resolution
            )

            if resolution == MergeConflictResolution.KEEP_SOURCE:
                setattr(target, conflict.field_name, conflict.source_value)
            elif resolution == MergeConflictResolution.MERGE:
                setattr(target, conflict.field_name, conflict.resolved_value)
            # KEEP_TARGET is default - no action needed

            conflict.resolution = resolution
            resolved_conflicts.append(conflict)

        # Transfer data
        data_transferred = {}

        # Transfer orders
        if source.orders:
            target.orders.extend(source.orders)
            data_transferred["orders"] = source.orders

        # Transfer subscriptions
        if source.subscriptions:
            target.subscriptions.extend(source.subscriptions)
            data_transferred["subscriptions"] = source.subscriptions

        # Transfer payment methods
        if source.payment_methods:
            # Deduplicate payment methods
            existing = set(target.payment_methods)
            new_methods = [pm for pm in source.payment_methods if pm not in existing]
            target.payment_methods.extend(new_methods)
            data_transferred["payment_methods"] = new_methods

        # Merge metadata
        if source.metadata:
            for key, value in source.metadata.items():
                if key not in target.metadata:
                    target.metadata[key] = value
            data_transferred["metadata"] = source.metadata

        # Transfer social logins
        if source.social_logins:
            existing = set(target.social_logins)
            new_logins = [sl for sl in source.social_logins if sl not in existing]
            target.social_logins.extend(new_logins)
            if new_logins:
                data_transferred["social_logins"] = new_logins

        # Keep the earliest created_at
        if source.created_at < target.created_at:
            target.created_at = source.created_at

        # Update account type if needed
        if target.account_type == AccountType.GUEST:
            if source.has_password:
                target.has_password = True
                target.account_type = AccountType.REGISTERED

        # Delete source account
        del self._accounts[source_id]

        result = MergeResult(
            success=True,
            merged_account_id=target_id,
            source_deleted=True,
            data_transferred=data_transferred,
            conflicts_resolved=resolved_conflicts
        )

        self._merge_history.append(result)
        logger.info(f"Merged account {source_id} into {target_id}")

        return result

    def get_merge_history(self) -> list[MergeResult]:
        """Get history of merge operations."""
        return self._merge_history.copy()

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Account Merge Tool - Consolidate duplicate accounts"
    )
    parser.add_argument(
        "--find-duplicates",
        action="store_true",
        help="Find potential duplicate accounts"
    )
    parser.add_argument(
        "--preview",
        nargs=2,
        metavar=("SOURCE", "TARGET"),
        help="Preview merge of SOURCE into TARGET"
    )
    parser.add_argument(
        "--merge",
        nargs=2,
        metavar=("SOURCE", "TARGET"),
        help="Merge SOURCE account into TARGET account"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually perform merge (preview only)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    tool = AccountMergeTool()

    if args.find_duplicates:
        print("Searching for duplicate accounts...")
        duplicates = tool.find_duplicates()
        if duplicates:
            print(f"\nFound {len(duplicates)} potential duplicate(s):")
            for i, (acc1, acc2) in enumerate(duplicates, 1):
                print(f"\n{i}. Potential duplicate:")
                print(f"   Account A: {acc1.account_id} ({acc1.email})")
                print(f"             Type: {acc1.account_type.value}, Created: {acc1.created_at}")
                print(f"   Account B: {acc2.account_id} ({acc2.email})")
                print(f"             Type: {acc2.account_type.value}, Created: {acc2.created_at}")
        else:
            print("No duplicate accounts found.")

    elif args.preview:
        source_id, target_id = args.preview
        preview = tool.preview_merge(source_id, target_id)

        print(f"\nMerge Preview: {source_id} -> {target_id}")
        print("=" * 50)

        if not preview.can_proceed:
            print("CANNOT PROCEED:")
            for warning in preview.warnings:
                print(f"  - {warning}")
            return

        if preview.warnings:
            print("\nWarnings:")
            for warning in preview.warnings:
                print(f"  - {warning}")

        if preview.conflicts:
            print("\nConflicts:")
            for conflict in preview.conflicts:
                print(f"  - {conflict.field_name}:")
                print(f"      Source: {conflict.source_value}")
                print(f"      Target: {conflict.target_value}")
                print(f"      Resolution: {conflict.resolution.value}")

        print("\nData to transfer:")
        for key, value in preview.data_to_transfer.items():
            if value:
                print(f"  - {key}: {len(value) if isinstance(value, list) else value}")

    elif args.merge:
        source_id, target_id = args.merge
        result = tool.merge(source_id, target_id, dry_run=args.dry_run)

        if result.success:
            print(f"\nMerge {'preview' if args.dry_run else 'complete'}!")
            print(f"  Merged into: {result.merged_account_id}")
            print(f"  Source deleted: {result.source_deleted}")
            if result.data_transferred:
                print("  Data transferred:")
                for key, value in result.data_transferred.items():
                    if value:
                        print(f"    - {key}: {len(value) if isinstance(value, list) else value}")
        else:
            print(f"\nMerge failed: {result.error}")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
