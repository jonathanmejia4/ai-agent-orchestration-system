import pytest
import sys
from pathlib import Path

def test_lock_acquire_release(real_repo_root, monkeypatch):
    """Lock can be acquired, checked, and released."""
    monkeypatch.chdir(real_repo_root)
    from tools.issue_lock import acquire, release, is_locked
    test_id = "TEST-LOCK-99"
    try:
        assert acquire(test_id, "pytest_agent") is True
        assert is_locked(test_id) is True
        # Second acquire should fail
        assert acquire(test_id, "another_agent") is False
    finally:
        release(test_id)
        assert is_locked(test_id) is False
