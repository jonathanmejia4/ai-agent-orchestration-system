#!/usr/bin/env bash
set -euo pipefail

python3 tools/eod_summary.py

# Optionally auto-commit the EOD entry if changes exist
if ! git diff --quiet habits/HABITS.md; then
  git config user.name "github-actions[bot]" || true
  git config user.email "github-actions[bot]@users.noreply.github.com" || true
  git add habits/HABITS.md
  git commit -m "chore(habits): EOD summary appended"
  echo "Committed EOD summary."
else
  echo "No changes to HABITS.md"
fi
