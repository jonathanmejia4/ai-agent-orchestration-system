#!/usr/bin/env python3
"""
Validate Issue File

Security validator for issue markdown files. Rejects issue files that contain
any of the following:

  1. Unknown top-level YAML frontmatter fields (strict allowlist).
  2. Sensitive paths in ``affected_paths`` (``.env``, ``*.pem``, ``credentials.*``,
     ``*_token*``, ``*_secret*``, etc.).
  3. Dangerous shell patterns inside ``## Verification Commands`` blocks
     (piped-to-shell, ``rm -rf``, bash-TCP reverse shells, ``eval``/``exec``).
  4. Basic type-checking failures (e.g. ``affected_paths`` not a list).

Intended to be run:

  - Locally before ``/fix-all``.
  - As a pre-commit hook on any change to ``issues/**.md``.
  - In CI against every PR that touches ``issues/``.

Usage::

    python3 tools/validate_issue_file.py issues/G/G-01.md
    python3 tools/validate_issue_file.py issues/

Exit codes:
  0 = every file passed
  1 = at least one file failed
  2 = invocation error (missing argument, file not found, unreadable)

See ``SECURITY.md`` for the threat model this validator defends against.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    print(f"error: PyYAML is required ({exc}). Install with: pip install pyyaml",
          file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Every top-level YAML key that the hunter agents, ``add_issue.py``, and
# ``add_frontmatter.py`` are known to emit. Anything outside this set is
# rejected. Keeping this list narrow is the point: adding a new schema field
# should be a deliberate, reviewed change.
ALLOWED_FIELDS = frozenset({
    # Core identity
    "issue_id",
    "lane",
    "title",
    # Classification
    "severity",
    "severity_level",
    "type_tags",
    "category",
    "category_desc",
    # Lifecycle
    "status",
    "approval_status",
    "user_approval_required",
    # Paths / scope
    "affected_paths",
    "file_paths",
    # Verification / pattern library
    "verification_pattern",
    "verification_depth",
    "pattern_vars",
    # Dates (multiple naming conventions seen in the wild)
    "created_at",
    "resolved_at",
    "verified_at",
    "date_created",
    "date_discovered",
    "date_resolved",
    "resolved_date",
    "discovered_date",
    "last_modified",
    # Cross-references
    "related",
    "related_issues",
    "depends_on",
    "blocks",
})

# ``affected_paths`` entries matching any of these patterns are rejected.
# Patterns are matched against each path with ``re.fullmatch``.
SENSITIVE_PATH_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p) for p in (
        r"\.env(\..*)?",
        r".*\.pem",
        r".*\.key",
        r"credentials\..*",
        r"\.?secrets\..*",
        r"\.secrets(/.*)?",
        r".*_token.*",
        r".*_secret.*",
        r".*_api_key.*",
    )
)

# Verification-command blocks are scanned for these patterns (re.search).
# Each entry is (compiled_pattern, human_label).
DANGEROUS_VERIFICATION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pat), label) for pat, label in (
        (r"curl\s+[^|]*\|", "curl piped to another command (possible exfiltration)"),
        (r"wget\s+[^|]*\|", "wget piped to another command (possible exfiltration)"),
        (r"\|\s*(bash|sh|zsh)\b", "pipe-to-shell"),
        (r"\brm\s+-rf\b", "rm -rf"),
        (r">\s*/dev/tcp/", "bash-TCP reverse shell"),
        (r"\b(eval|exec)\s*\(", "eval/exec invocation"),
    )
)


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------


def _split_frontmatter(content: str) -> tuple[dict | None, str, list[str]]:
    """Return (metadata, body, errors).

    ``metadata`` is None if the frontmatter is missing or unparseable; in that
    case, at least one error string will be populated.
    """
    errors: list[str] = []
    if not content.startswith("---"):
        return None, content, ["No YAML frontmatter (file must start with '---')"]

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content, ["Malformed frontmatter (missing closing '---')"]

    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        return None, parts[2], [f"YAML parse error: {exc}"]

    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        return None, parts[2], [
            f"Frontmatter must be a mapping, got {type(meta).__name__}"
        ]

    return meta, parts[2], errors


def _check_unknown_fields(meta: dict) -> list[str]:
    unknown = sorted(set(meta.keys()) - ALLOWED_FIELDS)
    if not unknown:
        return []
    return [f"Unknown top-level field(s): {', '.join(unknown)}"]


def _check_affected_paths(meta: dict) -> list[str]:
    errors: list[str] = []
    paths = meta.get("affected_paths")
    if paths is None:
        return errors

    if not isinstance(paths, list):
        return [
            f"'affected_paths' must be a list, got {type(paths).__name__}"
        ]

    for idx, path in enumerate(paths):
        if not isinstance(path, str):
            errors.append(
                f"affected_paths[{idx}] must be a string, got {type(path).__name__}"
            )
            continue
        for pattern in SENSITIVE_PATH_PATTERNS:
            if pattern.fullmatch(path):
                errors.append(
                    f"Sensitive path in affected_paths: '{path}' "
                    f"(matches blocklist pattern '{pattern.pattern}')"
                )
                break
    return errors


def _extract_verification_block(body: str) -> str | None:
    """Pull the text beneath a ``## Verification Commands`` heading, up to the
    next heading at the same or higher level. Returns None if absent.
    """
    match = re.search(
        r"(?im)^\#{1,6}\s*Verification\s+Commands?\s*\n"
        r"(.+?)"
        r"(?=^\#{1,6}\s|\Z)",
        body,
        flags=re.DOTALL | re.MULTILINE,
    )
    if not match:
        return None
    return match.group(1)


def _check_verification_commands(body: str) -> list[str]:
    block = _extract_verification_block(body)
    if block is None:
        return []
    errors: list[str] = []
    for pattern, label in DANGEROUS_VERIFICATION_PATTERNS:
        if pattern.search(block):
            errors.append(
                f"Dangerous verification pattern: {label} "
                f"(regex: {pattern.pattern})"
            )
    return errors


def _check_basic_types(meta: dict) -> list[str]:
    """Minimal type-checks for high-signal fields."""
    errors: list[str] = []

    list_fields = ("type_tags", "file_paths", "related", "related_issues",
                   "depends_on", "blocks")
    for field in list_fields:
        if field in meta and not isinstance(meta[field], list):
            errors.append(
                f"'{field}' must be a list, got {type(meta[field]).__name__}"
            )

    string_fields = ("issue_id", "lane", "severity_level", "status", "title",
                     "category", "verification_pattern", "verification_depth")
    for field in string_fields:
        if field in meta and meta[field] is not None and not isinstance(
                meta[field], str):
            errors.append(
                f"'{field}' must be a string, got {type(meta[field]).__name__}"
            )

    if "severity" in meta and meta["severity"] is not None and not isinstance(
            meta["severity"], int):
        errors.append(
            f"'severity' must be an integer, got {type(meta['severity']).__name__}"
        )

    return errors


def validate_file(path: Path) -> list[str]:
    """Return a list of human-readable error strings. Empty list == PASS."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Could not read file: {exc}"]
    except UnicodeDecodeError as exc:
        return [f"File is not valid UTF-8: {exc}"]

    meta, body, errors = _split_frontmatter(content)
    if meta is None:
        return errors

    errors.extend(_check_unknown_fields(meta))
    errors.extend(_check_basic_types(meta))
    errors.extend(_check_affected_paths(meta))
    errors.extend(_check_verification_commands(body))
    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _gather_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted(p for p in target.rglob("*.md") if p.is_file())
    raise FileNotFoundError(target)


def _print_result(path: Path, errors: Iterable[str]) -> None:
    errs = list(errors)
    if errs:
        print(f"FAIL {path}")
        for err in errs:
            print(f"  - {err}")
    else:
        print(f"PASS {path}")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("Usage: validate_issue_file.py <issue.md | issues-dir>",
              file=sys.stderr)
        return 2

    target = Path(argv[0])
    try:
        files = _gather_files(target)
    except FileNotFoundError:
        print(f"error: not found: {target}", file=sys.stderr)
        return 2

    if not files:
        print(f"error: no .md files under {target}", file=sys.stderr)
        return 2

    any_failed = False
    for f in files:
        errs = validate_file(f)
        _print_result(f, errs)
        if errs:
            any_failed = True

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
