#!/usr/bin/env bash
#
# Validate STATE.md Hook
# Validates LogBook/pm/STATE.md against schema to prevent PM amnesia
#

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
STATE_FILE="${REPO_ROOT}/LogBook/pm/STATE.md"
SCHEMA_FILE="${REPO_ROOT}/PLANNING/schemas/pm_state_schema.yaml"

# Check if STATE.md is in staged files
STAGED=$(git diff --cached --name-only | grep -E "^LogBook/pm/STATE\.md$" || true)

if [ -z "${STAGED}" ]; then
    # STATE.md not being modified, skip validation
    exit 0
fi

# Check if STATE.md exists
if [ ! -f "${STATE_FILE}" ]; then
    echo "ERROR: LogBook/pm/STATE.md not found"
    exit 1
fi

# Basic structure validation (check for required sections)
REQUIRED_SECTIONS=(
    "## Current Brick"
    "## Agent States"
    "## Pending Work Orders"
    "## Recent Decisions"
)

MISSING=()
for section in "${REQUIRED_SECTIONS[@]}"; do
    if ! grep -q "^${section}" "${STATE_FILE}"; then
        MISSING+=("${section}")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "ERROR: STATE.md missing required sections:"
    for m in "${MISSING[@]}"; do
        echo "  - ${m}"
    done
    echo ""
    echo "FIX: Add the missing sections to LogBook/pm/STATE.md"
    echo "     See PLANNING/schemas/pm_state_schema.yaml for structure"
    exit 1
fi

# Check for timestamp
if ! grep -qE "^Last Updated: [0-9]{4}-[0-9]{2}-[0-9]{2}" "${STATE_FILE}"; then
    echo "WARNING: STATE.md missing 'Last Updated' timestamp"
    echo "FIX: Add 'Last Updated: YYYY-MM-DD HH:MM' at the top"
fi

# Validate version format if present
if grep -q "^Version:" "${STATE_FILE}"; then
    VERSION_LINE=$(grep "^Version:" "${STATE_FILE}")
    if ! echo "${VERSION_LINE}" | grep -qE "Version: [0-9]+\.[0-9]+"; then
        echo "ERROR: Invalid version format in STATE.md"
        echo "FIX: Use format 'Version: X.Y' (e.g., Version: 1.5)"
        exit 1
    fi
fi

# All checks passed
exit 0
