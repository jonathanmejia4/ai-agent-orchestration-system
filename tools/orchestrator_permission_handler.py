#!/usr/bin/env python3
"""
Orchestrator Permission Handler

Polls for permission requests and handles user interaction.

Usage:
    from tools.orchestrator_permission_handler import handle_permission_request

    # Process a single request
    handle_permission_request("LogBook/permissions/E.request")

    # Or use the polling loop
    poll_for_permission_requests(timeout_seconds=600)
"""

import os
import yaml
import glob
import time
from datetime import datetime
from typing import Optional, Dict


def display_request_to_user(request: Dict) -> None:
    """Display permission request to user in formatted way"""
    print(f"\n{'='*60}")
    print(f"PERMISSION REQUEST - Lane {request['lane']}")
    print(f"{'='*60}")
    print(f"Agent: {request['agent']}")
    print(f"Issue: {request.get('issue_id', 'N/A')}")
    print(f"\nOperation: {request['operation']['type']}")
    print(f"Target: {request['operation']['target']}")
    print(f"Reason: {request['operation']['reason']}")

    # Display verification if present
    if "context" in request and "verification_performed" in request["context"]:
        print(f"\nVerification performed:")
        for verification in request["context"]["verification_performed"]:
            print(f"  - {verification}")

    print(f"\nOptions:")
    for opt in request['options']:
        print(f"\n  {opt['option_id']}: {opt['label']}")
        print(f"     {opt['description']}")
        if opt.get('pros'):
            print(f"     Pros: {', '.join(opt['pros'])}")
        if opt.get('cons'):
            print(f"     Cons: {', '.join(opt['cons'])}")

    if request.get('recommended'):
        print(f"\nRecommended: Option {request['recommended']}")


def get_user_decision(request: Dict) -> Dict:
    """
    Get user decision on permission request

    Returns approval dict with decision and chosen option
    """
    valid_options = [opt['option_id'] for opt in request['options']]

    while True:
        options_str = '/'.join(valid_options)
        decision_input = input(f"\nYour decision ({options_str}/reject): ").strip().upper()

        if decision_input == "REJECT":
            return {
                "request_id": request['request_id'],
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "decision": "REJECTED",
                "chosen_option": None,
                "approval_metadata": {
                    "approved_by": "User",
                    "approval_timestamp": datetime.utcnow().isoformat() + "Z",
                    "notes": "Rejected by user"
                }
            }

        if decision_input in valid_options:
            # Ask for optional notes
            notes = input("Optional notes (press Enter to skip): ").strip()

            approval = {
                "request_id": request['request_id'],
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "decision": "APPROVED",
                "chosen_option": decision_input,
                "approval_metadata": {
                    "approved_by": "User",
                    "approval_timestamp": datetime.utcnow().isoformat() + "Z"
                }
            }

            if notes:
                approval["approval_metadata"]["notes"] = notes

            return approval

        print(f"Invalid choice. Options: {options_str}, REJECT")


def write_approval_file(lane: str, approval: Dict) -> str:
    """
    Write approval file for the given lane

    Returns path to approval file
    """
    approval_file = f"LogBook/permissions/{lane}.approval"

    with open(approval_file, 'w') as f:
        yaml.dump(approval, f, default_flow_style=False, sort_keys=False)

    return approval_file


def handle_permission_request(request_file: str) -> bool:
    """
    Process a single permission request file

    Args:
        request_file: Path to .request file

    Returns:
        True if handled successfully, False if error
    """
    try:
        # Parse request
        with open(request_file, 'r') as f:
            request = yaml.safe_load(f)

        # Validate required fields
        required_fields = ['request_id', 'lane', 'agent', 'operation', 'options']
        missing = [f for f in required_fields if f not in request]
        if missing:
            print(f"ERROR: Request {request_file} missing fields: {missing}")
            return False

        # Display to user
        display_request_to_user(request)

        # Get decision
        approval = get_user_decision(request)

        # Write approval
        lane = request['lane']
        approval_file = write_approval_file(lane, approval)

        print(f"\nApproval written to {approval_file}")
        print(f"Lane {lane} will continue based on your decision.\n")

        return True

    except yaml.YAMLError as e:
        print(f"ERROR: Malformed request file {request_file}: {e}")

        # Mark lane as error
        lane = os.path.basename(request_file).replace('.request', '')
        error_file = f"LogBook/issue-fixing/signals/{lane}.status"
        with open(error_file, 'w') as f:
            f.write(f"ERROR: Malformed permission request")

        return False

    except Exception as e:
        print(f"ERROR: Failed to process {request_file}: {e}")
        return False


def poll_for_permission_requests(
    timeout_seconds: int = 600,
    poll_interval: int = 30
) -> None:
    """
    Poll for permission requests and handle them as they arrive

    Args:
        timeout_seconds: Total time to poll (default 10 min)
        poll_interval: Check every N seconds (default 30s)
    """
    print("Starting permission request polling...")
    print(f"Checking every {poll_interval}s for up to {timeout_seconds}s")

    start_time = time.time()
    processed_requests = set()

    while time.time() - start_time < timeout_seconds:
        # Find all .request files
        request_files = glob.glob("LogBook/permissions/*.request")

        # Process new requests
        for request_file in request_files:
            if request_file not in processed_requests:
                print(f"\n[{datetime.utcnow().strftime('%H:%M:%S')}] New permission request detected")

                if handle_permission_request(request_file):
                    processed_requests.add(request_file)
                else:
                    print(f"Failed to process {request_file}")

        time.sleep(poll_interval)

    print(f"\nPolling complete. Processed {len(processed_requests)} requests.")


def main():
    """Test harness and CLI interface"""
    import sys

    if "--test" in sys.argv:
        print("Testing Orchestrator Permission Handler...")
        print("=" * 60)

        # Create test request
        test_request = {
            "request_id": "PERM-TEST-001",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "lane": "TEST",
            "agent": "IF-Lane-TEST",
            "operation": {
                "type": "delete_file",
                "target": "test.py",
                "reason": "Test file cleanup"
            },
            "options": [
                {
                    "option_id": "A",
                    "label": "Delete",
                    "description": "Remove the file",
                    "pros": ["Clean"],
                    "cons": ["Permanent"]
                },
                {
                    "option_id": "B",
                    "label": "Archive",
                    "description": "Move to archive",
                    "pros": ["Recoverable"],
                    "cons": ["Takes space"]
                }
            ],
            "recommended": "B",
            "status": "PENDING"
        }

        # Write test request
        os.makedirs("LogBook/permissions", exist_ok=True)
        request_file = "LogBook/permissions/TEST.request"
        with open(request_file, 'w') as f:
            yaml.dump(test_request, f, default_flow_style=False, sort_keys=False)

        print(f"✓ PASS: Test request file created at {request_file}")
        print("\nTo complete the test:")
        print(f"  python3 tools/orchestrator_permission_handler.py --process {request_file}")
        print("\nOr to test polling:")
        print("  python3 tools/orchestrator_permission_handler.py --poll")

        return 0

    elif "--process" in sys.argv and len(sys.argv) > 2:
        request_file = sys.argv[2]
        success = handle_permission_request(request_file)
        return 0 if success else 1

    elif "--poll" in sys.argv:
        poll_for_permission_requests()
        return 0

    else:
        print("Usage:")
        print("  python3 orchestrator_permission_handler.py --test")
        print("  python3 orchestrator_permission_handler.py --process <request_file>")
        print("  python3 orchestrator_permission_handler.py --poll")
        return 1


if __name__ == "__main__":
    exit(main())
