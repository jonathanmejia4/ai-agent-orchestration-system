#!/usr/bin/env python3
"""
Path validation utility for the system tools.
Purpose: Prevent path traversal attacks by validating paths stay within repo bounds.
Usage: from tools.utils.path_validator import validate_path
"""

from pathlib import Path
from typing import Optional

def validate_path(user_path: str, repo_root: Optional[Path] = None) -> Path:
    """Validate path is within repository bounds.

    Prevents path traversal attacks by ensuring user-provided paths
    resolve to locations within the repository root.

    Args:
        user_path: Path from user input (CLI arg, config file, etc.)
        repo_root: Repository root directory. Defaults to current working directory.

    Returns:
        Validated, resolved Path object

    Raises:
        ValueError: If path is outside repository bounds or contains invalid characters

    Examples:
        >>> validate_path("src/main.py")
        PosixPath('/repo/src/main.py')

        >>> validate_path("../../../etc/passwd")
        ValueError: Path '../../../etc/passwd' is outside repository bounds.
    """
    if repo_root is None:
        repo_root = Path.cwd()

    # Convert to Path and resolve (handles .., symlinks, etc.)
    try:
        resolved = Path(user_path).resolve()
    except (OSError, RuntimeError) as e:
        raise ValueError(f"Invalid path '{user_path}': {e}")

    repo_resolved = repo_root.resolve()

    # Check if resolved path is within repo bounds
    try:
        resolved.relative_to(repo_resolved)
    except ValueError:
        raise ValueError(
            f"Path '{user_path}' is outside repository bounds.\n"
            f"Resolved to: {resolved}\n"
            f"Repo root: {repo_resolved}"
        )

    return resolved

def is_safe_path(user_path: str, repo_root: Optional[Path] = None) -> bool:
    """Check if path is safe (within repo bounds) without raising exception.

    Args:
        user_path: Path from user input
        repo_root: Repository root directory. Defaults to current working directory.

    Returns:
        True if path is safe, False otherwise
    """
    try:
        validate_path(user_path, repo_root)
        return True
    except ValueError:
        return False

def sanitize_path(user_path: str, repo_root: Optional[Path] = None) -> Optional[Path]:
    """Attempt to sanitize and validate path.

    Returns validated path if safe, None if unsafe.

    Args:
        user_path: Path from user input
        repo_root: Repository root directory. Defaults to current working directory.

    Returns:
        Validated Path if safe, None if path is outside bounds
    """
    try:
        return validate_path(user_path, repo_root)
    except ValueError:
        return None
