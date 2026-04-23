#!/usr/bin/env bash
#
# Validate Policy Versions Hook
# Ensures PLANNING/*_POLICY.md files have version headers and changelogs
#

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"

# Check if any policy files are staged
STAGED_POLICIES=$(git diff --cached --name-only --diff-filter=ACMR | grep -E "^PLANNING/.*_POLICY\.md$" || true)

if [ -z "${STAGED_POLICIES}" ]; then
    # No policy files staged, skip
    exit 0
fi

WARNINGS=()

while IFS= read -r policy_file; do
    [ -z "${policy_file}" ] && continue

    full_path="${REPO_ROOT}/${policy_file}"
    [ ! -f "${full_path}" ] && continue

    filename=$(basename "${policy_file}")

    # Check for version header
    if ! grep -qE "^\*\*Version:\*\*|^Version:" "${full_path}"; then
        WARNINGS+=("${policy_file}: Missing version header")
    fi

    # Check for changelog section
    if ! grep -qiE "^## Change ?[Ll]og|^## Version History|^\*\*Change ?[Ll]og:\*\*" "${full_path}"; then
        WARNINGS+=("${policy_file}: Missing changelog section")
    fi

    # Check for last updated date
    if ! grep -qE "Last Updated:|Updated:|Date:" "${full_path}"; then
        WARNINGS+=("${policy_file}: Missing last updated date")
    fi

    # Check first line is a title
    first_line=$(head -1 "${full_path}")
    if ! echo "${first_line}" | grep -qE "^#[^#]"; then
        WARNINGS+=("${policy_file}: First line should be a markdown title (# Title)")
    fi

done <<< "${STAGED_POLICIES}"

if [ ${#WARNINGS[@]} -gt 0 ]; then
    echo "Policy version warnings:"
    for w in "${WARNINGS[@]}"; do
        echo "  - ${w}"
    done
    echo ""
    echo "Recommended policy file structure:"
    echo "  # POLICY_NAME"
    echo "  **Version:** X.Y.Z"
    echo "  **Last Updated:** YYYY-MM-DD"
    echo "  ..."
    echo "  ## Change Log"
    echo "  - vX.Y.Z (YYYY-MM-DD): Description"
    echo ""
    # These are warnings, not blockers
    exit 0
fi

exit 0
