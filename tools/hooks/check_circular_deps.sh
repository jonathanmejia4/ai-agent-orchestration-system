#!/usr/bin/env bash
#
# Check Circular Dependencies Hook
# Runs circular dependency detector on DAG/wiring files
#

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
DETECTOR="${REPO_ROOT}/tools/circular_dep_detector.py"
DAG_VALIDATOR="${REPO_ROOT}/tools/dag_validator.py"

# Check if any DAG-related files are staged
STAGED_DAG=$(git diff --cached --name-only --diff-filter=ACMR | grep -E "(wiring\.yaml|dependencies\.yaml|task\.yaml|dag.*\.yaml)" || true)

if [ -z "${STAGED_DAG}" ]; then
    # No DAG files staged, skip
    exit 0
fi

# Try circular_dep_detector.py first
if [ -x "${DETECTOR}" ]; then
    if command -v python3 &> /dev/null; then
        result=$(python3 "${DETECTOR}" 2>&1) || {
            echo "Circular dependency detected!"
            echo "${result}"
            echo ""
            echo "FIX: Remove the circular dependency before committing"
            exit 1
        }
    fi
# Fall back to dag_validator.py
elif [ -x "${DAG_VALIDATOR}" ]; then
    if command -v python3 &> /dev/null; then
        result=$(python3 "${DAG_VALIDATOR}" 2>&1) || {
            echo "DAG validation failed!"
            echo "${result}"
            echo ""
            echo "FIX: Fix the DAG structure before committing"
            exit 1
        }
    fi
else
    # No detector available, check manually for obvious issues
    for file in ${STAGED_DAG}; do
        full_path="${REPO_ROOT}/${file}"
        [ ! -f "${full_path}" ] && continue

        # Simple check: look for self-references
        if command -v python3 &> /dev/null; then
            python3 -c "
import yaml
import sys

try:
    with open('${full_path}') as f:
        data = yaml.safe_load(f)

    if not data:
        sys.exit(0)

    # Check for self-references in dependencies
    if isinstance(data, dict):
        deps = data.get('dependencies', {})
        if isinstance(deps, dict):
            for key, value in deps.items():
                if isinstance(value, list) and key in value:
                    print(f'Self-reference detected: {key} depends on itself')
                    sys.exit(1)
except:
    pass
" 2>/dev/null || {
                echo "Possible circular dependency in ${file}"
                exit 1
            }
        fi
    done
fi

exit 0
