#!/bin/bash
# PM Boundary Check Hook
# Version: 1.0.0
# Last Updated: 2025-12-25
# Owner: PM
# Classification: CRITICAL - Access Control Enforcement
#
# This hook validates that agents respect PM-exclusive write boundaries.
# PM owns: LogBook/pm/, .claude/agents/, archives/golden/, integration/config/
#
# Usage:
#   hooks/pm_boundary_check.sh [--strict] [--agent <name>]
#   hooks/pm_boundary_check.sh --check-staged
#   hooks/pm_boundary_check.sh --check-file <path>

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# PM-exclusive paths (only PM can write)
PM_EXCLUSIVE_PATHS=(
    "LogBook/pm/"
    ".claude/agents/"
    "archives/golden/"
    "integration/config/"
    ".github/workflows/"
    "PLANNING/"
    ".claude/guidelines/"
)

# Agent write boundaries
declare -A AGENT_BOUNDARIES
AGENT_BOUNDARIES["builder"]="src/ tests/ .brick/logbook.yaml .brick/wiring.yaml"
AGENT_BOUNDARIES["planner"]="PLANNING/work_orders/ LogBook/planner/ .brick/action_plan.yaml .brick/deps.yaml"
AGENT_BOUNDARIES["critic"]=".brick/verdict.yaml LogBook/critic/ LogBook/progress/verdicts/"

# Configuration
STRICT_MODE=false
CURRENT_AGENT=""
CHECK_STAGED=false
CHECK_FILE=""

# =============================================================================
# Helper Functions
# =============================================================================

print_status() {
    local status=$1
    local message=$2

    case $status in
        PASS)
            echo -e "${GREEN}✓${NC} $message"
            ;;
        FAIL)
            echo -e "${RED}✗${NC} $message"
            ;;
        WARN)
            echo -e "${YELLOW}!${NC} $message"
            ;;
        INFO)
            echo -e "${BLUE}i${NC} $message"
            ;;
    esac
}

is_pm_exclusive() {
    local path=$1

    for exclusive in "${PM_EXCLUSIVE_PATHS[@]}"; do
        if [[ "$path" == "$exclusive"* ]]; then
            return 0
        fi
    done
    return 1
}

is_within_boundary() {
    local agent=$1
    local path=$2

    local boundaries="${AGENT_BOUNDARIES[$agent]}"
    if [ -z "$boundaries" ]; then
        # Unknown agent - deny by default
        return 1
    fi

    for boundary in $boundaries; do
        if [[ "$path" == "$boundary"* ]]; then
            return 0
        fi
    done
    return 1
}

check_file_permission() {
    local agent=$1
    local path=$2

    # Check if path is PM-exclusive
    if is_pm_exclusive "$path"; then
        if [ "$agent" = "pm" ]; then
            print_status PASS "PM can write to: $path"
            return 0
        else
            print_status FAIL "VIOLATION: $agent cannot write to PM-exclusive path: $path"
            return 1
        fi
    fi

    # Check agent-specific boundaries
    if [ -n "$agent" ] && [ "$agent" != "pm" ]; then
        if is_within_boundary "$agent" "$path"; then
            print_status PASS "$agent can write to: $path"
            return 0
        else
            print_status FAIL "VIOLATION: $agent outside write boundary: $path"
            return 1
        fi
    fi

    # Default: allow if not PM-exclusive
    print_status PASS "Path not restricted: $path"
    return 0
}

# =============================================================================
# Check Functions
# =============================================================================

check_staged_files() {
    echo ""
    echo "Checking staged files for boundary violations..."
    echo "================================================"

    local violations=0
    local staged_files=$(git diff --cached --name-only 2>/dev/null)

    if [ -z "$staged_files" ]; then
        print_status INFO "No staged files to check"
        return 0
    fi

    for file in $staged_files; do
        if is_pm_exclusive "$file"; then
            if [ -n "$CURRENT_AGENT" ] && [ "$CURRENT_AGENT" != "pm" ]; then
                print_status FAIL "Staged file in PM-exclusive path: $file"
                ((violations++))
            else
                print_status WARN "Staged file in PM-exclusive path: $file (verify PM is author)"
            fi
        fi
    done

    echo ""
    if [ $violations -gt 0 ]; then
        print_status FAIL "Found $violations boundary violations"
        return 1
    fi

    print_status PASS "All staged files within boundaries"
    return 0
}

check_single_file() {
    local path=$1
    local agent=${CURRENT_AGENT:-"unknown"}

    echo ""
    echo "Checking file: $path"
    echo "Agent: $agent"
    echo "================================"

    check_file_permission "$agent" "$path"
    return $?
}

show_boundaries() {
    echo ""
    echo "PM-Exclusive Paths (only PM can write):"
    echo "========================================"
    for path in "${PM_EXCLUSIVE_PATHS[@]}"; do
        echo "  - $path"
    done

    echo ""
    echo "Agent Write Boundaries:"
    echo "======================="
    for agent in "${!AGENT_BOUNDARIES[@]}"; do
        echo "  $agent:"
        for boundary in ${AGENT_BOUNDARIES[$agent]}; do
            echo "    - $boundary"
        done
    done
}

# =============================================================================
# Main
# =============================================================================

show_usage() {
    echo "PM Boundary Check Hook"
    echo ""
    echo "Usage:"
    echo "  $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --strict            Enable strict mode (fail on warnings)"
    echo "  --agent <name>      Specify agent (builder, planner, critic, pm)"
    echo "  --check-staged      Check git staged files"
    echo "  --check-file <path> Check specific file"
    echo "  --show-boundaries   Display boundary configuration"
    echo "  --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --check-staged --agent builder"
    echo "  $0 --check-file src/api/users.py --agent builder"
    echo "  $0 --show-boundaries"
}

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --strict)
                STRICT_MODE=true
                shift
                ;;
            --agent)
                CURRENT_AGENT="$2"
                shift 2
                ;;
            --check-staged)
                CHECK_STAGED=true
                shift
                ;;
            --check-file)
                CHECK_FILE="$2"
                shift 2
                ;;
            --show-boundaries)
                show_boundaries
                exit 0
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    echo "========================================"
    echo "PM Boundary Check"
    echo "========================================"

    if [ -n "$CURRENT_AGENT" ]; then
        print_status INFO "Agent: $CURRENT_AGENT"
    fi

    if [ "$STRICT_MODE" = true ]; then
        print_status INFO "Mode: Strict"
    fi

    local exit_code=0

    if [ "$CHECK_STAGED" = true ]; then
        check_staged_files || exit_code=1
    elif [ -n "$CHECK_FILE" ]; then
        check_single_file "$CHECK_FILE" || exit_code=1
    else
        # Default: check staged files
        check_staged_files || exit_code=1
    fi

    echo ""
    echo "========================================"
    if [ $exit_code -eq 0 ]; then
        print_status PASS "Boundary check passed"
    else
        print_status FAIL "Boundary check failed"
        if [ "$STRICT_MODE" = true ]; then
            echo "Strict mode: Blocking operation"
        fi
    fi
    echo "========================================"

    exit $exit_code
}

main "$@"
