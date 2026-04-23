import subprocess, sys
from pathlib import Path

def test_sync_runs_cleanly(real_repo_root):
    """sync_catalog_stats.py runs without error."""
    result = subprocess.run([
        sys.executable, str(real_repo_root / "tools/sync_catalog_stats.py")
    ], capture_output=True, text=True, cwd=real_repo_root, timeout=60)
    assert result.returncode == 0, f"sync failed: {result.stderr}"
    assert "Catalog updated" in result.stdout or "issues" in result.stdout.lower()

def test_catalog_has_26_lanes(real_repo_root):
    """ISSUE_CATALOG.md references all 26 lanes."""
    catalog = (real_repo_root / "ISSUE_CATALOG.md").read_text()
    for lane in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        # Look for | A | or | B | etc. in the lane completion table
        assert f"| {lane} |" in catalog, f"Lane {lane} not in catalog"
