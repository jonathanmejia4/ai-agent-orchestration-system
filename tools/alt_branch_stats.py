from __future__ import annotations

"""Utility to collect statistics about alternative branches.

This scans ``LogBook/<category>/alt/*/INDEX.md`` files for status markers
indicating success, failure or pending state of a branch.
"""

from pathlib import Path
from typing import Dict

# Mapping of known status markers to result names.
#
# The mapping intentionally keeps the union of markers extremely small so
# future additions require an explicit review.  Unknown markers are handled
# later in the traversal and treated as ``pending`` to avoid skewing totals
# or dropping branches altogether.
_MARKERS = {
    "✅": "success",
    "🟥": "failure",
    "🟨": "pending",
}

def alt_branch_stats(logbook_path: str | Path = "LogBook") -> Dict[str, int]:
    """Return counts of alternative branch statuses.

    Parameters
    ----------
    logbook_path: str or Path
        Path to the ``LogBook`` directory.  By default it is assumed to be
        located in the current working directory.

    Returns
    -------
    dict
        Dictionary with keys ``total``, ``success``, ``failure`` and
        ``pending`` representing branch counts.
    """

    base = Path(logbook_path)
    counts = {"total": 0, "success": 0, "failure": 0, "pending": 0}

    if not base.exists() or not base.is_dir():
        return counts

    for category in base.iterdir():
        if not category.is_dir():
            continue
        alt_dir = category / "alt"
        if not alt_dir.is_dir():
            continue

        for branch in alt_dir.iterdir():
            if not branch.is_dir():
                continue
            index_file = branch / "INDEX.md"
            if not index_file.is_file():
                continue

            counts["total"] += 1
            content = index_file.read_text(encoding="utf-8", errors="ignore")

            for marker, key in _MARKERS.items():
                if marker in content:
                    counts[key] += 1
                    break
            else:
                # Marker missing or unrecognised: treat as pending
                counts["pending"] += 1

    return counts

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Compute alt branch statistics")
    parser.add_argument(
        "logbook",
        nargs="?",
        default="LogBook",
        help="Path to the LogBook directory (default: LogBook)",
    )
    args = parser.parse_args()

    stats = alt_branch_stats(args.logbook)
    print(json.dumps(stats))
