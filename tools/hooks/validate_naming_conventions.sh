#!/usr/bin/env bash
#
# Validate Naming Conventions Hook
# Enforces file and ID naming patterns
#

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"

# Get staged files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR)

if [ -z "${STAGED_FILES}" ]; then
    exit 0
fi

WARNINGS=()

# Patterns
UUID_PATTERN="^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
TASK_FILE_PATTERN="^task\.(yaml|yml)$"
POLICY_FILE_PATTERN="^[A-Z][A-Z0-9_]*_POLICY\.md$"
SCHEMA_FILE_PATTERN="^[a-z][a-z0-9_]*_schema\.yaml$"

while IFS= read -r file; do
    [ -z "${file}" ] && continue

    filename=$(basename "${file}")
    dirname=$(dirname "${file}")

    # Check task.yaml files for UUID task IDs
    if [[ "${filename}" =~ ^task\.(yaml|yml)$ ]]; then
        if [ -f "${REPO_ROOT}/${file}" ]; then
            # Try to extract task ID
            brick_id=$(grep -E "^id:" "${REPO_ROOT}/${file}" | head -1 | sed 's/id: *//' | tr -d '"' | tr -d "'" || true)
            if [ -n "${brick_id}" ]; then
                if ! echo "${brick_id}" | grep -qE "${UUID_PATTERN}"; then
                    WARNINGS+=("${file}: Task ID '${brick_id}' is not a valid UUID format")
                fi
            fi
        fi
    fi

    # Check PLANNING/ policy files
    if [[ "${dirname}" == "PLANNING" || "${dirname}" == "./PLANNING" ]]; then
        if [[ "${filename}" == *_POLICY.md ]]; then
            if ! echo "${filename}" | grep -qE "${POLICY_FILE_PATTERN}"; then
                WARNINGS+=("${file}: Policy filename should be UPPERCASE_POLICY.md")
            fi
        fi
    fi

    # Check schema files
    if [[ "${dirname}" == *schemas* ]]; then
        if [[ "${filename}" == *_schema.yaml ]]; then
            if ! echo "${filename}" | grep -qE "${SCHEMA_FILE_PATTERN}"; then
                WARNINGS+=("${file}: Schema filename should be lowercase_schema.yaml")
            fi
        fi
    fi

    # Check for spaces in filenames
    if echo "${file}" | grep -q " "; then
        WARNINGS+=("${file}: Filename contains spaces (use hyphens or underscores)")
    fi

    # Check for uppercase extensions
    extension="${filename##*.}"
    if echo "${extension}" | grep -q "[A-Z]"; then
        WARNINGS+=("${file}: File extension should be lowercase")
    fi

done <<< "${STAGED_FILES}"

if [ ${#WARNINGS[@]} -gt 0 ]; then
    echo "Naming convention warnings:"
    for w in "${WARNINGS[@]}"; do
        echo "  - ${w}"
    done
    echo ""
    echo "These are warnings and won't block the commit."
    echo "Consider fixing them for consistency."
    # Return 0 since these are just warnings
    exit 0
fi

exit 0
