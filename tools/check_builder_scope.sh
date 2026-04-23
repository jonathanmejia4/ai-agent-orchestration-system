#!/bin/bash
# SAF Builder Scope Enforcement Hook
# Purpose: Verify brick scope compliance before commit
# Referenced by: .claude/guidelines/builder-scope-enforcement.md:316-318
# Version: 1.0.0

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}[SAF] Checking Builder scope compliance...${NC}"

# Get staged files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR)

if [ -z "$STAGED_FILES" ]; then
    echo -e "${GREEN}[SAF] No staged files to check${NC}"
    exit 0
fi

ERRORS=0
WARNINGS=0

# Check for brick scope violations
# Builder can only modify files within their assigned brick scope
check_brick_scope() {
    local file="$1"

    # If file is in bricks/ directory, verify it matches assigned brick
    if [[ "$file" == bricks/* ]]; then
        # Extract brick ID from path (e.g., bricks/brick-auth-001/file.py -> brick-auth-001)
        BRICK_ID=$(echo "$file" | cut -d'/' -f2)

        # Check if there's an active work order for this brick
        if [ -f ".brick/current_assignment.yaml" ]; then
            ASSIGNED_BRICK=$(grep "brick_id:" .brick/current_assignment.yaml 2>/dev/null | awk '{print $2}' | tr -d '"')
            if [ -n "$ASSIGNED_BRICK" ] && [ "$BRICK_ID" != "$ASSIGNED_BRICK" ]; then
                echo -e "${RED}[SAF] ERROR: Modifying $BRICK_ID but assigned to $ASSIGNED_BRICK${NC}"
                return 1
            fi
        fi
    fi

    return 0
}

# Check for PM-exclusive path violations
check_pm_exclusive() {
    local file="$1"

    # PM-exclusive paths that Builder cannot modify
    PM_EXCLUSIVE_PATTERNS=(
        "^PLANNING/"
        "^LogBook/pm/"
        "^\.claude/agents/"
        "^\.claude/guidelines/"
        "^ISSUE_CATALOG\.md$"
    )

    for pattern in "${PM_EXCLUSIVE_PATTERNS[@]}"; do
        if echo "$file" | grep -qE "$pattern"; then
            echo -e "${RED}[SAF] ERROR: $file is PM-exclusive, Builder cannot modify${NC}"
            return 1
        fi
    done

    return 0
}

# Check for cross-brick dependencies
check_cross_brick() {
    local file="$1"

    if [[ "$file" == bricks/*/imports.py ]] || [[ "$file" == bricks/*/__init__.py ]]; then
        # Check for imports from other bricks
        if git show ":$file" 2>/dev/null | grep -qE "from bricks\.[^.]+\." ; then
            IMPORTED=$(git show ":$file" | grep -oE "from bricks\.[^.]+" | sort -u)
            echo -e "${YELLOW}[SAF] WARNING: $file imports from other bricks: $IMPORTED${NC}"
            return 2  # Warning, not error
        fi
    fi

    return 0
}

# Process each staged file
for file in $STAGED_FILES; do
    # Skip if file was deleted
    if [ ! -f "$file" ]; then
        continue
    fi

    # Run scope checks
    if ! check_pm_exclusive "$file"; then
        ERRORS=$((ERRORS + 1))
    fi

    if ! check_brick_scope "$file"; then
        ERRORS=$((ERRORS + 1))
    fi

    result=$(check_cross_brick "$file"; echo $?)
    if [ "$result" = "2" ]; then
        WARNINGS=$((WARNINGS + 1))
    elif [ "$result" = "1" ]; then
        ERRORS=$((ERRORS + 1))
    fi
done

# Summary
echo ""
if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}[SAF] Scope check failed: $ERRORS error(s), $WARNINGS warning(s)${NC}"
    echo -e "${YELLOW}[SAF] Builder agents must stay within assigned brick scope${NC}"
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}[SAF] Scope check passed with $WARNINGS warning(s)${NC}"
    exit 0
else
    echo -e "${GREEN}[SAF] Scope check passed${NC}"
    exit 0
fi
