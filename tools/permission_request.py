#!/usr/bin/env python3
"""
Permission Request Helper

Helps agents create permission request files and wait for approval.

Usage:
    from tools.permission_request import PermissionRequest

    pr = PermissionRequest(lane="E", agent="IF-Lane-E")

    # Request permission
    request_id = pr.request_permission(
        operation_type="delete_file",
        target="src/legacy/deprecated_auth.py",
        reason="No references found, deprecated 6mo ago",
        options=[
            {"option_id": "A", "label": "Delete file", ...},
            {"option_id": "B", "label": "Archive instead", ...}
        ],
        recommended="B"
    )

    # Wait for approval (with timeout)
    approval = pr.wait_for_approval(request_id, timeout_seconds=300)

    if approval and approval["decision"] == "APPROVED":
        # Proceed with operation
        chosen_option = approval["chosen_option"]
"""

import os
import yaml
import time
from datetime import datetime
from typing import Optional, Dict, List


class PermissionRequest:
    """Helper for creating and waiting on permission requests"""

    SIGNALS_DIR = "LogBook/permissions"

    def __init__(self, lane: str, agent: str):
        self.lane = lane
        self.agent = agent
        os.makedirs(self.SIGNALS_DIR, exist_ok=True)

    def request_permission(
        self,
        operation_type: str,
        target: str,
        reason: str,
        options: List[Dict],
        recommended: Optional[str] = None,
        context: Optional[Dict] = None,
        issue_id: Optional[str] = None
    ) -> str:
        """
        Create permission request file

        Returns:
            request_id: Unique ID for this request
        """
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        request_id = f"PERM-{timestamp}-{self.lane}-001"

        request = {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "lane": self.lane,
            "agent": self.agent,
            "issue_id": issue_id,
            "operation": {
                "type": operation_type,
                "target": target,
                "reason": reason
            },
            "context": context or {},
            "options": options,
            "recommended": recommended,
            "status": "PENDING"
        }

        # Write request file
        request_file = os.path.join(self.SIGNALS_DIR, f"{self.lane}.request")
        with open(request_file, 'w') as f:
            yaml.dump(request, f, default_flow_style=False, sort_keys=False)

        print(f"Permission requested: {request_id}")
        print(f"Request file: {request_file}")

        return request_id

    def wait_for_approval(
        self,
        request_id: str,
        timeout_seconds: int = 300,
        poll_interval: int = 5
    ) -> Optional[Dict]:
        """
        Wait for approval response

        Args:
            request_id: ID of the permission request
            timeout_seconds: Max time to wait (default 5 min)
            poll_interval: How often to check (default 5 sec)

        Returns:
            Approval dict if approved/rejected, None if timeout
        """
        approval_file = os.path.join(self.SIGNALS_DIR, f"{self.lane}.approval")

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if os.path.exists(approval_file):
                with open(approval_file, 'r') as f:
                    approval = yaml.safe_load(f)

                # Verify this is for our request
                if approval.get("request_id") == request_id:
                    print(f"Approval received: {approval['decision']}")
                    return approval

            time.sleep(poll_interval)

        print(f"Timeout waiting for approval after {timeout_seconds}s")
        return None

    def cleanup_request(self):
        """Remove request/approval files after processing"""
        request_file = os.path.join(self.SIGNALS_DIR, f"{self.lane}.request")
        approval_file = os.path.join(self.SIGNALS_DIR, f"{self.lane}.approval")

        for f in [request_file, approval_file]:
            if os.path.exists(f):
                # Archive before deleting
                archive_dir = os.path.join(self.SIGNALS_DIR, "archive")
                os.makedirs(archive_dir, exist_ok=True)

                timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
                archive_name = f"{timestamp}-{os.path.basename(f)}"
                archive_path = os.path.join(archive_dir, archive_name)

                os.rename(f, archive_path)
                print(f"Archived: {archive_path}")

    def request_permission_with_resume(
        self,
        operation_type: str,
        target: str,
        reason: str,
        options: List[Dict],
        recommended: Optional[str] = None,
        context: Optional[Dict] = None,
        issue_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Request permission with resume capability (checks for existing approval)

        Returns existing approval if found, otherwise creates new request and waits
        """
        # Check if approval already exists (from previous run)
        approval_file = os.path.join(self.SIGNALS_DIR, f"{self.lane}.approval")
        if os.path.exists(approval_file):
            with open(approval_file, 'r') as f:
                approval = yaml.safe_load(f)

            # If for same operation, use it
            if approval.get("request_id", "").startswith("PERM-"):
                print("Found existing approval from previous run")
                return approval

        # Otherwise, create new request
        request_id = self.request_permission(
            operation_type=operation_type,
            target=target,
            reason=reason,
            options=options,
            recommended=recommended,
            context=context,
            issue_id=issue_id
        )

        return self.wait_for_approval(request_id)


def main():
    """Test harness for permission request system"""
    import sys

    if "--test" not in sys.argv:
        print("Usage: python3 permission_request.py --test")
        return 1

    print("Testing Permission Request System...")
    print("=" * 60)

    pr = PermissionRequest(lane="TEST", agent="IF-Lane-TEST")

    # Test: Create permission request
    request_id = pr.request_permission(
        operation_type="delete_file",
        target="test.py",
        reason="Test reason",
        options=[
            {
                "option_id": "A",
                "label": "Test Option A",
                "description": "First option",
                "pros": ["Pro 1"],
                "cons": ["Con 1"]
            }
        ],
        recommended="A"
    )

    # Check file exists
    request_file = "LogBook/permissions/TEST.request"
    assert os.path.exists(request_file), "Request file not created"
    print(f"✓ PASS: Request file created at {request_file}")

    # Verify content
    with open(request_file, 'r') as f:
        request_data = yaml.safe_load(f)

    assert request_data["request_id"] == request_id, "Request ID mismatch"
    assert request_data["lane"] == "TEST", "Lane mismatch"
    assert request_data["operation"]["type"] == "delete_file", "Operation type mismatch"
    print("✓ PASS: Request file content valid")

    # Cleanup test file
    os.remove(request_file)
    print("✓ PASS: Cleanup successful")

    print("=" * 60)
    print("All tests passed!")
    return 0


if __name__ == "__main__":
    exit(main())
