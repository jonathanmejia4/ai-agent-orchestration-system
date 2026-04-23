import subprocess, sys
from pathlib import Path

def test_add_issue_creates_file(real_repo_root, tmp_path, monkeypatch):
    """add_issue.py --path creates issue with affected_paths populated."""
    # Use a temporary working dir to avoid polluting real repo
    monkeypatch.chdir(real_repo_root)
    # Create a test issue in a test lane letter we'll clean up
    test_id = "TEST_AUTO-99"
    test_lane_dir = real_repo_root / "issues" / "Z"
    existing_files = set(test_lane_dir.glob("*.md")) if test_lane_dir.exists() else set()
    try:
        result = subprocess.run([
            sys.executable, "tools/add_issue.py", "Z", "pytest test issue", "--severity", "3", "--path", "CLAUDE.md"
        ], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, f"add_issue failed: {result.stderr}"
        # Find the new issue file
        new_files = set(test_lane_dir.glob("*.md")) - existing_files
        assert len(new_files) == 1, f"Expected 1 new file, got {len(new_files)}"
        issue_file = new_files.pop()
        content = issue_file.read_text()
        assert "affected_paths:" in content
        assert "CLAUDE.md" in content
        # Cleanup
        issue_file.unlink()
    finally:
        # Ensure catalog re-syncs to clean state
        subprocess.run([sys.executable, "tools/sync_catalog_stats.py"], capture_output=True)
