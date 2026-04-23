#!/usr/bin/env python3
"""Generate appendix pages for the the system documentation site."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"
APP_ROOT = DOCS_ROOT / "appendices" / "repo"
MANIFEST_PATH = DOCS_ROOT / "appendices" / "metadata.json"
DEFAULT_EXCLUDES = {".git", "docs/_build", "__pycache__"}

def iter_files(root: Path, excludes: Iterable[str]) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in excludes for part in rel.parts):
            continue
        if path.is_relative_to(APP_ROOT.parent):
            continue
        yield path

def emit_page(source: Path, destination_root: Path) -> dict:
    text = source.read_text(encoding="utf-8", errors="replace")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    rel = source.relative_to(REPO_ROOT).as_posix()
    page = destination_root / f"{rel}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "---\n"
        f"path: {rel}\n"
        f"hash: {digest}\n"
        "---\n\n"
        "```text\n"
        f"{text}\n"
        "```\n",
        encoding="utf-8",
    )
    return {
        "path": rel,
        "hash": digest,
        "bytes": len(text.encode("utf-8")),
        "volume": "appendix",
    }

def build_manifest(excludes: Iterable[str]) -> list[dict]:
    APP_ROOT.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    for file_path in iter_files(REPO_ROOT, set(excludes) | DEFAULT_EXCLUDES):
        if file_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf"}:
            continue
        try:
            manifest.append(emit_page(file_path, APP_ROOT))
        except (UnicodeDecodeError, OSError):
            continue
    return manifest

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate appendix pages for the system docs")
    parser.add_argument("--exclude", action="append", default=[], help="Relative paths to exclude")
    args = parser.parse_args()

    manifest = build_manifest(args.exclude)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
