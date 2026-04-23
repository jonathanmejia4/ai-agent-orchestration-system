import subprocess, sys
from pathlib import Path

def test_validator_accepts_valid(real_repo_root):
    """Validator passes valid issue files."""
    result = subprocess.run([
        sys.executable, "tools/validate_issue_file.py",
        str(real_repo_root / "issues/X/X-01.md")
    ], capture_output=True, text=True)
    assert result.returncode == 0, f"PASS file failed: {result.stdout} {result.stderr}"

def test_validator_rejects_sensitive_paths(real_repo_root, tmp_path):
    """Validator rejects issues with sensitive paths."""
    evil = tmp_path / "evil.md"
    evil.write_text("""---
issue_id: EVIL-1
lane: X
severity: 5
status: OPEN
affected_paths:
  - .env
---

## Description
Evil issue
""")
    result = subprocess.run([
        sys.executable, str(real_repo_root / "tools/validate_issue_file.py"),
        str(evil)
    ], capture_output=True, text=True, cwd=real_repo_root)
    assert result.returncode == 1, f"Validator should have rejected .env; output: {result.stdout}"
    assert "Sensitive" in result.stdout or "sensitive" in result.stdout.lower()

def test_validator_rejects_unknown_fields(real_repo_root, tmp_path):
    """Validator rejects unknown YAML fields."""
    evil = tmp_path / "evil.md"
    evil.write_text("""---
issue_id: EVIL-2
lane: X
severity: 5
status: OPEN
evil_field: payload
---

## Description
Unknown field test
""")
    result = subprocess.run([
        sys.executable, str(real_repo_root / "tools/validate_issue_file.py"),
        str(evil)
    ], capture_output=True, text=True, cwd=real_repo_root)
    assert result.returncode == 1
    assert "Unknown" in result.stdout or "evil_field" in result.stdout
