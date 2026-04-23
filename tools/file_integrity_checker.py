#!/usr/bin/env python3
"""
file_integrity_checker.py - File Integrity Verification Tool

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Integrity Validation Tool

Purpose:
    Verifies file integrity using checksums.
    Detects unauthorized modifications to critical files.
    Maintains baseline checksums for comparison.

Usage:
    python3 file_integrity_checker.py baseline --path src/ --output checksums.json
    python3 file_integrity_checker.py verify --baseline checksums.json
    python3 file_integrity_checker.py check --file src/main.py
"""

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

@dataclass
class FileChecksum:
    """Checksum information for a file."""
    path: str
    sha256: str
    size: int
    modified: str

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size": self.size,
            "modified": self.modified
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileChecksum":
        return cls(
            path=data["path"],
            sha256=data["sha256"],
            size=data["size"],
            modified=data["modified"]
        )

@dataclass
class IntegrityViolation:
    """Represents an integrity violation."""
    path: str
    violation_type: str  # "modified", "added", "removed", "corrupted"
    expected_hash: Optional[str] = None
    actual_hash: Optional[str] = None
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "type": self.violation_type,
            "expected_hash": self.expected_hash,
            "actual_hash": self.actual_hash,
            "message": self.message
        }

@dataclass
class VerificationResult:
    """Result of integrity verification."""
    status: str  # "pass", "fail"
    timestamp: str
    files_checked: int
    violations: List[IntegrityViolation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "timestamp": self.timestamp,
            "files_checked": self.files_checked,
            "violation_count": len(self.violations),
            "violations": [v.to_dict() for v in self.violations]
        }

class FileIntegrityChecker:
    """Checks file integrity using checksums."""

    # File extensions to include by default
    DEFAULT_EXTENSIONS = {
        ".py", ".ts", ".tsx", ".js", ".jsx", ".yaml", ".yml",
        ".json", ".md", ".sh", ".bash", ".sql", ".html", ".css"
    }

    # Directories to skip
    SKIP_DIRS = {
        ".git", "node_modules", "__pycache__", ".venv", "venv",
        "dist", "build", ".snapshots", ".pytest_cache"
    }

    def __init__(self, extensions: Optional[Set[str]] = None):
        self.extensions = extensions or self.DEFAULT_EXTENSIONS

    def calculate_checksum(self, file_path: Path) -> FileChecksum:
        """Calculate checksum for a single file."""
        content = file_path.read_bytes()
        sha256 = hashlib.sha256(content).hexdigest()
        stat = file_path.stat()

        return FileChecksum(
            path=str(file_path),
            sha256=sha256,
            size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime).isoformat()
        )

    def should_check_file(self, file_path: Path) -> bool:
        """Determine if file should be checked."""
        # Skip excluded directories
        if any(d in file_path.parts for d in self.SKIP_DIRS):
            return False

        # Check extension
        if self.extensions and file_path.suffix not in self.extensions:
            return False

        return True

    def create_baseline(self, path: str) -> Dict[str, FileChecksum]:
        """Create baseline checksums for all files in path."""
        target = Path(path)
        checksums = {}

        for file_path in target.rglob("*"):
            if file_path.is_file() and self.should_check_file(file_path):
                try:
                    checksum = self.calculate_checksum(file_path)
                    checksums[str(file_path)] = checksum
                except Exception as e:
                    print(f"Warning: Could not checksum {file_path}: {e}", file=sys.stderr)

        return checksums

    def save_baseline(self, checksums: Dict[str, FileChecksum], output_path: str):
        """Save baseline checksums to file."""
        data = {
            "version": "1.0",
            "created": datetime.utcnow().isoformat() + "Z",
            "file_count": len(checksums),
            "files": {path: cs.to_dict() for path, cs in checksums.items()}
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

    def load_baseline(self, baseline_path: str) -> Dict[str, FileChecksum]:
        """Load baseline checksums from file."""
        with open(baseline_path, 'r') as f:
            data = json.load(f)

        return {
            path: FileChecksum.from_dict(cs_data)
            for path, cs_data in data["files"].items()
        }

    def verify_integrity(
        self,
        baseline: Dict[str, FileChecksum],
        check_path: Optional[str] = None
    ) -> VerificationResult:
        """Verify file integrity against baseline."""
        violations = []
        files_checked = 0

        # Get current files
        if check_path:
            current_files = set()
            for file_path in Path(check_path).rglob("*"):
                if file_path.is_file() and self.should_check_file(file_path):
                    current_files.add(str(file_path))
        else:
            current_files = set()
            for path in baseline.keys():
                if Path(path).exists():
                    current_files.add(path)

        baseline_files = set(baseline.keys())

        # Check for removed files
        for path in baseline_files - current_files:
            violations.append(IntegrityViolation(
                path=path,
                violation_type="removed",
                expected_hash=baseline[path].sha256,
                message=f"File was removed: {path}"
            ))

        # Check for added files (only if check_path specified)
        if check_path:
            for path in current_files - baseline_files:
                violations.append(IntegrityViolation(
                    path=path,
                    violation_type="added",
                    message=f"New file detected: {path}"
                ))

        # Check for modified files
        for path in current_files & baseline_files:
            files_checked += 1
            file_path = Path(path)

            try:
                current = self.calculate_checksum(file_path)
                expected = baseline[path]

                if current.sha256 != expected.sha256:
                    violations.append(IntegrityViolation(
                        path=path,
                        violation_type="modified",
                        expected_hash=expected.sha256,
                        actual_hash=current.sha256,
                        message=f"File was modified: {path}"
                    ))
            except Exception as e:
                violations.append(IntegrityViolation(
                    path=path,
                    violation_type="corrupted",
                    message=f"Could not verify file: {e}"
                ))

        status = "pass" if not violations else "fail"

        return VerificationResult(
            status=status,
            timestamp=datetime.utcnow().isoformat() + "Z",
            files_checked=files_checked,
            violations=violations
        )

    def check_single_file(
        self,
        file_path: str,
        expected_hash: Optional[str] = None
    ) -> VerificationResult:
        """Check integrity of a single file."""
        path = Path(file_path)
        violations = []

        if not path.exists():
            violations.append(IntegrityViolation(
                path=file_path,
                violation_type="removed",
                message=f"File does not exist: {file_path}"
            ))
        else:
            try:
                current = self.calculate_checksum(path)

                if expected_hash and current.sha256 != expected_hash:
                    violations.append(IntegrityViolation(
                        path=file_path,
                        violation_type="modified",
                        expected_hash=expected_hash,
                        actual_hash=current.sha256,
                        message=f"Hash mismatch for {file_path}"
                    ))
            except Exception as e:
                violations.append(IntegrityViolation(
                    path=file_path,
                    violation_type="corrupted",
                    message=f"Could not verify file: {e}"
                ))

        status = "pass" if not violations else "fail"

        return VerificationResult(
            status=status,
            timestamp=datetime.utcnow().isoformat() + "Z",
            files_checked=1 if path.exists() else 0,
            violations=violations
        )

def main():
    parser = argparse.ArgumentParser(
        description="File integrity verification tool"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Baseline command
    baseline_parser = subparsers.add_parser("baseline", help="Create baseline checksums")
    baseline_parser.add_argument("--path", "-p", required=True, help="Path to scan")
    baseline_parser.add_argument("--output", "-o", required=True, help="Output file")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify against baseline")
    verify_parser.add_argument("--baseline", "-b", required=True, help="Baseline file")
    verify_parser.add_argument("--path", "-p", help="Path to verify (optional)")

    # Check command
    check_parser = subparsers.add_parser("check", help="Check single file")
    check_parser.add_argument("--file", "-f", required=True, help="File to check")
    check_parser.add_argument("--hash", help="Expected hash (optional)")

    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    checker = FileIntegrityChecker()

    if args.command == "baseline":
        checksums = checker.create_baseline(args.path)
        checker.save_baseline(checksums, args.output)
        print(f"Created baseline with {len(checksums)} files: {args.output}")
        return 0

    elif args.command == "verify":
        baseline = checker.load_baseline(args.baseline)
        result = checker.verify_integrity(baseline, args.path)

        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            if result.status == "pass":
                print(f"\u2705 Integrity verification PASSED")
                print(f"   Files checked: {result.files_checked}")
            else:
                print(f"\u274c Integrity verification FAILED")
                print(f"   Files checked: {result.files_checked}")
                print(f"   Violations: {len(result.violations)}")
                for v in result.violations:
                    print(f"     [{v.violation_type.upper()}] {v.path}")

        return 0 if result.status == "pass" else 1

    elif args.command == "check":
        result = checker.check_single_file(args.file, args.hash)

        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            if result.status == "pass":
                checksum = checker.calculate_checksum(Path(args.file))
                print(f"\u2705 File integrity OK: {args.file}")
                print(f"   SHA256: {checksum.sha256}")
            else:
                print(f"\u274c File integrity FAILED: {args.file}")
                for v in result.violations:
                    print(f"   {v.message}")

        return 0 if result.status == "pass" else 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
