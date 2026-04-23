#!/bin/bash
#
# Tool Validation Script for SAF
#
# Validates that a tool exists and is executable before agent workflows attempt to use it.
# Used as a pre-flight check to prevent runtime errors from missing dependencies.
#
# Usage:
#     tools/validate_tool.sh <tool_path>
#
# Exit Codes:
#     0 - Tool is valid and ready to use
#     1 - Tool is invalid (missing, not executable, dependencies missing)
#     2 - Error (invalid arguments, permissions issues)
#
# Examples:
#     # Validate Python script
#     if tools/validate_tool.sh tools/security_scanner.py; then
#       python3 tools/security_scanner.py scan --path .
#     fi
#
#     # Validate bash script
#     if tools/validate_tool.sh tools/retry.sh; then
#       tools/retry.sh "git push origin main"
#     fi
#
#     # Validate with error handling
#     if ! tools/validate_tool.sh tools/metric_aggregator.py; then
#       echo "metric_aggregator.py not available, skipping metrics"
#       exit 0
#     fi
#
# Referenced in:
#     - edge-cases-and-recovery.md:309 (Tool existence check)
#     - edge-cases-and-recovery.md:351 (security_scanner.py validation)
#     - edge-cases-and-recovery.md:358 (metric_aggregator.py validation)
#
# Author: SAF System
# Created: 2025-12-23
#

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -ne 1 ]; then
    echo -e "${RED}❌ Error: Invalid arguments${NC}" >&2
    echo "Usage: $0 <tool_path>" >&2
    echo "" >&2
    echo "Examples:" >&2
    echo "  $0 tools/security_scanner.py" >&2
    echo "  $0 tools/retry.sh" >&2
    exit 2
fi

TOOL_PATH="$1"

# Function: Check if file exists
check_file_exists() {
    if [ ! -f "$TOOL_PATH" ]; then
        echo -e "${RED}❌ Tool not found: $TOOL_PATH${NC}" >&2
        return 1
    fi
    return 0
}

# Function: Check if file is readable
check_file_readable() {
    if [ ! -r "$TOOL_PATH" ]; then
        echo -e "${RED}❌ Tool not readable (permission denied): $TOOL_PATH${NC}" >&2
        return 1
    fi
    return 0
}

# Function: Check Python script
check_python_script() {
    # Check if Python is installed
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is not installed${NC}" >&2
        return 1
    fi

    # Check if script is executable (optional for .py files)
    if [ -x "$TOOL_PATH" ]; then
        echo -e "${GREEN}✅ Python script valid and executable: $TOOL_PATH${NC}" >&2
    else
        echo -e "${YELLOW}⚠️  Python script exists but not executable (will use 'python3 $TOOL_PATH')${NC}" >&2
    fi

    # Check if file has valid Python syntax (basic check)
    if ! python3 -m py_compile "$TOOL_PATH" 2>/dev/null; then
        echo -e "${RED}❌ Python script has syntax errors: $TOOL_PATH${NC}" >&2
        return 1
    fi

    return 0
}

# Function: Check bash script
check_bash_script() {
    # Check if script is executable
    if [ ! -x "$TOOL_PATH" ]; then
        echo -e "${RED}❌ Bash script is not executable: $TOOL_PATH${NC}" >&2
        echo -e "${YELLOW}💡 Fix: chmod +x $TOOL_PATH${NC}" >&2
        return 1
    fi

    # Check if file has shebang
    if ! head -n 1 "$TOOL_PATH" | grep -q '^#!/bin/bash\|^#!/usr/bin/env bash'; then
        echo -e "${YELLOW}⚠️  Warning: Bash script missing shebang (#!/bin/bash)${NC}" >&2
    fi

    echo -e "${GREEN}✅ Bash script valid and executable: $TOOL_PATH${NC}" >&2
    return 0
}

# Function: Check generic executable
check_generic_executable() {
    if [ ! -x "$TOOL_PATH" ]; then
        echo -e "${RED}❌ Tool is not executable: $TOOL_PATH${NC}" >&2
        echo -e "${YELLOW}💡 Fix: chmod +x $TOOL_PATH${NC}" >&2
        return 1
    fi

    echo -e "${GREEN}✅ Tool is executable: $TOOL_PATH${NC}" >&2
    return 0
}

# Main validation logic
main() {
    # Check file exists
    if ! check_file_exists; then
        return 1
    fi

    # Check file is readable
    if ! check_file_readable; then
        return 1
    fi

    # Determine tool type and validate accordingly
    case "$TOOL_PATH" in
        *.py)
            check_python_script
            return $?
            ;;
        *.sh)
            check_bash_script
            return $?
            ;;
        *)
            # Generic executable check
            check_generic_executable
            return $?
            ;;
    esac
}

# Run main validation
main
exit $?
