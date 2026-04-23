import subprocess, sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).parent.parent

# Sample of core tools that should respond to --help without crashing
CORE_TOOLS = [
    "add_issue.py",
    "issue_stats.py",
    "issue_lock.py",
    "sync_catalog_stats.py",
    "sync_tools_catalog.py",
    "verify_issue.py",
    "validate_issue_file.py",
    "security_scanner.py",
    "pii_scanner.py",
    "markdown_link_checker.py",
    "dependency_analyzer.py",
    "code_quality_analyzer.py",
    "schema_validator.py",
]

@pytest.mark.parametrize("tool", CORE_TOOLS)
def test_tool_help_responds(tool):
    """Tool responds to --help without crashing."""
    tool_path = REPO_ROOT / "tools" / tool
    if not tool_path.exists():
        pytest.skip(f"{tool} not present")
    result = subprocess.run(
        [sys.executable, str(tool_path), "--help"],
        capture_output=True, text=True, timeout=10
    )
    # Some tools may not have --help and exit non-zero; that's ok
    # What's not ok is a crash/traceback
    assert "Traceback" not in result.stderr, f"{tool} traceback: {result.stderr}"
