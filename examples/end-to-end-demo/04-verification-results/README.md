# 04 — Verification Results

This directory captures the output of two independent verification runs against the single fixed issue (`X-01`).

## Files

- `verification-output.txt` — concatenated raw terminal output of:
  1. `python3 tools/verify_issue.py X-01 --verbose` — the framework's automated verifier.
  2. The issue's three embedded `Verification Commands` run directly from bash.

## Result

Both runs agree: **X-01 PASSES** with `Checks: 3/3 passed` and `Confidence: 100%`.

## Why two runs?

Verification in this framework happens at two layers:

1. **Embedded commands** (what the hunter wrote into the issue file) — these are the ground truth and anyone can run them by hand.
2. **`verify_issue.py`** — inspects the issue's `affected_paths` and runs pattern-based checks (file existence, not-empty, git-tracked) derived from the verification-patterns catalog.

Both must agree before an issue can legitimately be called "verified".

## Interpreting the output

`verify_issue.py` line-by-line:

- `✅ X-01: PASS` — overall verdict
- `Pattern: embedded_commands` — which verification pattern was matched
- `Depth: STANDARD` — standard checks (not `--quick` or `--deep`)
- `Checks: 3/3 passed` — three underlying checks all succeeded
- `Confidence: 100%` — verifier is fully confident in the PASS
- Per-check lines — each shows the command run, expected exit code, and actual exit code

If any single check failed, the overall status would flip to `FAIL` and `sync_catalog_stats.py` would refuse to mark the issue as `Verified` in `ISSUE_CATALOG.md`.
