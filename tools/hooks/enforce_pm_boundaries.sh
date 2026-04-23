#!/usr/bin/env bash
#
# Enforce PM Write Boundaries Hook
# Prevents Project Manager from committing to implementation directories
#

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
LOG_FILE="${REPO_ROOT}/LogBook/audit/pm-boundary-violations.log"

# Get current user from git config
GIT_USER=$(git config user.name 2>/dev/null || echo "unknown")

# Check if user is PM (case-insensitive check)
IS_PM=false
PM_IDENTIFIERS=("SAF-Project-Manager" "PM" "project-manager" "Project Manager")

for id in "${PM_IDENTIFIERS[@]}"; do
    if echo "${GIT_USER}" | grep -iq "${id}"; then
        IS_PM=true
        break
    fi
done

# If not PM, allow all commits
if [ "${IS_PM}" = false ]; then
    exit 0
fi

# PM detected - check staged files against boundaries
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR)

if [ -z "${STAGED_FILES}" ]; then
    exit 0
fi

# Forbidden paths for PM
FORBIDDEN_PATTERNS=(
    "^bricks/"
    "^src/"
    "^tests/"
    "^tools/"
)

# Allowed exceptions within forbidden paths
ALLOWED_EXCEPTIONS=(
    "^tools/hooks/"  # PM can modify hook configs
)

VIOLATIONS=()

while IFS= read -r file; do
    [ -z "${file}" ] && continue

    # Check if file matches forbidden pattern
    for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
        if echo "${file}" | grep -qE "${pattern}"; then
            # Check if it's an allowed exception
            IS_EXCEPTION=false
            for exception in "${ALLOWED_EXCEPTIONS[@]}"; do
                if echo "${file}" | grep -qE "${exception}"; then
                    IS_EXCEPTION=true
                    break
                fi
            done

            if [ "${IS_EXCEPTION}" = false ]; then
                VIOLATIONS+=("${file}")
            fi
            break
        fi
    done
done <<< "${STAGED_FILES}"

if [ ${#VIOLATIONS[@]} -gt 0 ]; then
    echo "PM WRITE BOUNDARY VIOLATION"
    echo "=========================="
    echo ""
    echo "User '${GIT_USER}' detected as Project Manager."
    echo "PM is not allowed to modify implementation files."
    echo ""
    echo "Forbidden files in commit:"
    for v in "${VIOLATIONS[@]}"; do
        echo "  - ${v}"
    done
    echo ""
    echo "ALLOWED paths for PM:"
    echo "  - LogBook/**"
    echo "  - PLANNING/**"
    echo "  - docs/**"
    echo "  - .claude/guidelines/**"
    echo "  - ISSUE_CATALOG.md"
    echo "  - .github/workflows/**"
    echo ""
    echo "FIX: Remove forbidden files from commit using:"
    echo "     git reset HEAD <file>"
    echo ""
    echo "Or delegate implementation changes to SAF-Builder."

    # Log violation
    mkdir -p "$(dirname "${LOG_FILE}")"
    echo "$(date -Iseconds) | ${GIT_USER} | VIOLATION | ${VIOLATIONS[*]}" >> "${LOG_FILE}"

    exit 1
fi

exit 0
