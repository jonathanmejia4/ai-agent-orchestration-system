import sys
from pathlib import Path
import pytest
import tempfile
import os

# Put repo root on sys.path so tests can import `tools.*`
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

@pytest.fixture
def temp_repo(tmp_path):
    """Provide a tmp directory simulating minimal repo structure."""
    issues_dir = tmp_path / "issues" / "G"
    issues_dir.mkdir(parents=True)
    logbook = tmp_path / "LogBook" / "issue-fixing" / "locks"
    logbook.mkdir(parents=True)
    yield tmp_path

@pytest.fixture
def real_repo_root():
    """Actual repo root for tests that need real tool paths."""
    return REPO_ROOT
