#!/usr/bin/env bash
#
# Validate YAML Schemas Hook
# Validates YAML files against their corresponding schemas
#

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
SCHEMAS_DIR="${REPO_ROOT}/PLANNING/schemas"

# Get staged YAML files
STAGED_YAML=$(git diff --cached --name-only --diff-filter=ACMR | grep -E '\.(yaml|yml)$' || true)

if [ -z "${STAGED_YAML}" ]; then
    # No YAML files staged, skip
    exit 0
fi

ERRORS=()

# Check each staged YAML file
while IFS= read -r yaml_file; do
    [ -z "${yaml_file}" ] && continue

    full_path="${REPO_ROOT}/${yaml_file}"

    # Skip if file doesn't exist
    [ ! -f "${full_path}" ] && continue

    # Basic YAML syntax check using python
    if command -v python3 &> /dev/null; then
        if ! python3 -c "import yaml; yaml.safe_load(open('${full_path}'))" 2>/dev/null; then
            ERRORS+=("${yaml_file}: Invalid YAML syntax")
            continue
        fi
    fi

    # Determine which schema to use based on filename/path
    SCHEMA=""

    case "${yaml_file}" in
        .brick/brick.yaml|*/.brick/brick.yaml)
            # Brick manifest files use manifest schema
            SCHEMA="${SCHEMAS_DIR}/brick_manifest_schema.yaml"
            ;;
        *_spec.yaml|*_spec.yml|*-spec.yaml|*-spec.yml)
            # Specification files use specification schema
            SCHEMA="${SCHEMAS_DIR}/brick_specification_schema.yaml"
            ;;
        *brick.yaml|*brick.yml)
            # Other brick files default to manifest schema
            SCHEMA="${SCHEMAS_DIR}/brick_manifest_schema.yaml"
            ;;
        *wiring.yaml|*wiring.yml)
            SCHEMA="${SCHEMAS_DIR}/ssot_wiring_schema.yaml"
            ;;
        *verdict*.yaml|*verdict*.yml)
            SCHEMA="${SCHEMAS_DIR}/critic_verdict_schema.yaml"
            ;;
        *work_order*.yaml|*work_order*.yml|*work-order*.yaml)
            SCHEMA="${SCHEMAS_DIR}/work_order_schema.yaml"
            ;;
        .githooks/config.yaml)
            # Config file - just check syntax (already done above)
            ;;
    esac

    # If we have a schema and it exists, validate against it
    if [ -n "${SCHEMA}" ] && [ -f "${SCHEMA}" ]; then
        # Try to validate with jsonschema if available
        if command -v python3 &> /dev/null && python3 -c "import jsonschema" 2>/dev/null; then
            if ! python3 -c "
import yaml
import jsonschema
import sys

try:
    with open('${full_path}') as f:
        data = yaml.safe_load(f)
    with open('${SCHEMA}') as f:
        schema = yaml.safe_load(f)
    jsonschema.validate(data, schema)
except jsonschema.ValidationError as e:
    print(f'Schema validation failed: {e.message}')
    sys.exit(1)
except Exception as e:
    # Schema might not be in jsonschema format, skip
    pass
" 2>/dev/null; then
                ERRORS+=("${yaml_file}: Schema validation failed")
            fi
        fi
    fi

done <<< "${STAGED_YAML}"

if [ ${#ERRORS[@]} -gt 0 ]; then
    echo "YAML validation errors:"
    for err in "${ERRORS[@]}"; do
        echo "  - ${err}"
    done
    echo ""
    echo "FIX: Correct the YAML syntax or schema violations"
    exit 1
fi

exit 0
