#!/usr/bin/env python3
"""
Update PLANNING/future/INDEX.md with current directory contents
"""
import os
from pathlib import Path
from datetime import datetime

FUTURE_DIR = Path("PLANNING/future")
INDEX_FILE = FUTURE_DIR / "INDEX.md"

def scan_future_files():
    """Scan PLANNING/future/ for files and extract metadata"""
    files = []

    for file_path in FUTURE_DIR.glob("*.md"):
        if file_path.name == "INDEX.md":
            continue

        # Read frontmatter if present
        with open(file_path) as f:
            content = f.read()

        # Simple frontmatter extraction (between --- markers)
        metadata = {
            "filename": file_path.name,
            "title": file_path.stem,
            "date": "unknown",
            "category": "unknown",
            "status": "unknown"
        }

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 2:
                frontmatter = parts[1]
                for line in frontmatter.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        key = key.strip().lower()
                        value = value.strip()
                        if key in metadata:
                            metadata[key] = value

        files.append(metadata)

    return sorted(files, key=lambda x: x["filename"])

def generate_index_content(files):
    """Generate index content from file metadata"""
    if not files:
        return "\n*No files indexed yet. Add files to PLANNING/future/ and run `python3 tools/update_future_index.py` to update.*\n"

    lines = []

    # Group by category
    categories = {}
    for f in files:
        cat = f["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f)

    # Generate index
    for category, category_files in sorted(categories.items()):
        lines.append(f"\n### {category.title()}\n")
        for f in category_files:
            status_emoji = {"idea": "💡", "researching": "🔬", "deferred": "⏸️", "abandoned": "❌"}.get(f["status"], "❓")
            lines.append(f"- {status_emoji} **{f['title']}** (`{f['filename']}`) - {f['date']}")

    return "\n".join(lines)

def update_index():
    """Update INDEX.md with current directory contents"""
    if not INDEX_FILE.exists():
        print(f"❌ INDEX.md not found at {INDEX_FILE}")
        return

    files = scan_future_files()

    # Read current index
    with open(INDEX_FILE) as f:
        content = f.read()

    # Generate new index section
    new_index = generate_index_content(files)

    # Replace between INDEX_START and INDEX_END
    if "<!-- INDEX_START -->" in content and "<!-- INDEX_END -->" in content:
        before = content.split("<!-- INDEX_START -->")[0]
        after = content.split("<!-- INDEX_END -->")[1]

        updated_content = before + "<!-- INDEX_START -->" + new_index + "\n<!-- INDEX_END -->" + after

        # Update statistics
        stats = {
            "total": len(files),
            "features": sum(1 for f in files if f["category"] == "feature"),
            "enhancements": sum(1 for f in files if f["category"] == "enhancement"),
            "research": sum(1 for f in files if f["category"] == "research"),
            "brainstorms": sum(1 for f in files if f["category"] == "brainstorm"),
            "ideas": sum(1 for f in files if f["status"] == "idea"),
            "researching": sum(1 for f in files if f["status"] == "researching"),
            "deferred": sum(1 for f in files if f["status"] == "deferred"),
            "abandoned": sum(1 for f in files if f["status"] == "abandoned"),
        }

        # Update last scanned date
        updated_content = updated_content.replace(
            "Last scanned: 2025-12-23",
            f"Last scanned: {datetime.now().strftime('%Y-%m-%d')}"
        )

        # Write updated index
        with open(INDEX_FILE, "w") as f:
            f.write(updated_content)

        print(f"✅ Index updated: {stats['total']} files indexed")
    else:
        print("❌ INDEX_START/INDEX_END markers not found in INDEX.md")

if __name__ == "__main__":
    update_index()
