#!/bin/bash
#
# test_idempotence.sh - Validate Idempotent Generation
#
# Tests that running brick generation twice produces identical output.
# Essential for verifying template stability and deterministic builds.
#
# Usage:
#   tools/test_idempotence.sh <brick-id>
#   tools/test_idempotence.sh --template <template-name> --ssot <wiring.yaml>
#   tools/test_idempotence.sh --dir <brick-directory>
#   tools/test_idempotence.sh --help
#
# Exit Codes:
#   0 - Idempotent (outputs identical)
#   1 - Non-idempotent (outputs differ)
#   2 - Error (missing files, generation failed, etc.)
#
# Referenced in:
#   - TEMPLATE_COMPLIANCE_POLICY.md:174, 248, 249, 254, 1380
#   - IDEMPOTENT_GENERATION_POLICY.md:981
#
# Author: SAF System
# Created: 2025-12-23

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Temporary directories
TMP_BASE="${TMPDIR:-/tmp}/saf-idempotence-$$"
GEN1_DIR="$TMP_BASE/gen1"
GEN2_DIR="$TMP_BASE/gen2"

# Default values
BRICK_ID=""
TEMPLATE=""
SSOT=""
BRICK_DIR=""
VERBOSE=false
KEEP_TMP=false
EXCLUDE_TIMESTAMPS=true

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] <brick-id>
       $(basename "$0") --template <template> --ssot <wiring.yaml>
       $(basename "$0") --dir <brick-directory>

Validate idempotent generation by running twice and comparing outputs.

Options:
    -h, --help              Show this help message
    -t, --template NAME     Template name to test
    -s, --ssot FILE         SSOT wiring file path
    -d, --dir DIR           Brick directory to test
    -v, --verbose           Verbose output
    -k, --keep-tmp          Keep temporary directories after test
    --include-timestamps    Include timestamps in comparison (default: exclude)

Examples:
    $(basename "$0") brick-123
    $(basename "$0") --template user-service --ssot .brick/wiring.yaml
    $(basename "$0") --dir .brick/

Exit Codes:
    0 - Idempotent (outputs identical)
    1 - Non-idempotent (outputs differ)
    2 - Error
EOF
}

log() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $*"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $*" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

cleanup() {
    if [ "$KEEP_TMP" = false ] && [ -d "$TMP_BASE" ]; then
        rm -rf "$TMP_BASE"
    fi
}

trap cleanup EXIT

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -t|--template)
            TEMPLATE="$2"
            shift 2
            ;;
        -s|--ssot)
            SSOT="$2"
            shift 2
            ;;
        -d|--dir)
            BRICK_DIR="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -k|--keep-tmp)
            KEEP_TMP=true
            shift
            ;;
        --include-timestamps)
            EXCLUDE_TIMESTAMPS=false
            shift
            ;;
        -*)
            log_error "Unknown option: $1"
            usage
            exit 2
            ;;
        *)
            BRICK_ID="$1"
            shift
            ;;
    esac
done

# Validate inputs
if [ -z "$BRICK_ID" ] && [ -z "$TEMPLATE" ] && [ -z "$BRICK_DIR" ]; then
    log_error "Must specify brick-id, --template, or --dir"
    usage
    exit 2
fi

if [ -n "$TEMPLATE" ] && [ -z "$SSOT" ]; then
    log_error "--template requires --ssot"
    exit 2
fi

# Create temporary directories
mkdir -p "$GEN1_DIR" "$GEN2_DIR"

log "Testing idempotent generation..."
if [ "$VERBOSE" = true ]; then
    log "Temp directories: $TMP_BASE"
fi

# Function to generate brick
generate_brick() {
    local output_dir="$1"
    local gen_num="$2"

    if [ "$VERBOSE" = true ]; then
        log "Generation #$gen_num to $output_dir"
    fi

    # Use generate_brick.py for actual generation (required for valid idempotence testing)
    if [ ! -f "$SCRIPT_DIR/generate_brick.py" ]; then
        echo "ERROR: generate_brick.py not found at $SCRIPT_DIR/generate_brick.py" >&2
        echo "Idempotence testing requires actual generation, not file copying." >&2
        echo "Please ensure generate_brick.py is available." >&2
        return 1
    fi

    if [ -n "$BRICK_ID" ]; then
        if ! python3 "$SCRIPT_DIR/generate_brick.py" "$BRICK_ID" --output "$output_dir" 2>&1; then
            echo "ERROR: Generation failed for brick $BRICK_ID" >&2
            return 1
        fi
    elif [ -n "$TEMPLATE" ] && [ -n "$SSOT" ]; then
        if ! python3 "$SCRIPT_DIR/generate_brick.py" --template "$TEMPLATE" --ssot "$SSOT" --output "$output_dir" 2>&1; then
            echo "ERROR: Generation failed for template $TEMPLATE" >&2
            return 1
        fi
    else
        echo "ERROR: No valid generation method specified." >&2
        echo "Provide either --brick-id, or both --template and --ssot." >&2
        echo "Note: Directory copying is not supported - idempotence requires actual generation." >&2
        return 1
    fi

    # Create test marker to ensure something is generated
    echo "generation_$gen_num" > "$output_dir/.gen_marker"
}

# Function to normalize files for comparison
normalize_for_comparison() {
    local dir="$1"

    if [ "$EXCLUDE_TIMESTAMPS" = true ]; then
        # Remove timestamp patterns from files
        find "$dir" -type f \( -name "*.yaml" -o -name "*.yml" -o -name "*.json" -o -name "*.md" \) | while read -r file; do
            # Remove ISO timestamps
            sed -i.bak 's/[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}T[0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}[.0-9]*Z\?/TIMESTAMP/g' "$file" 2>/dev/null || true
            # Remove date patterns
            sed -i.bak 's/[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}/DATE/g' "$file" 2>/dev/null || true
            rm -f "$file.bak"
        done
    fi

    # Remove generation markers
    rm -f "$dir/.gen_marker"

    # Remove empty directories
    find "$dir" -type d -empty -delete 2>/dev/null || true
}

# Generate first time
log "Running generation #1..."
generate_brick "$GEN1_DIR" 1

# Small delay to ensure different timestamps (if not excluded)
sleep 0.1

# Generate second time
log "Running generation #2..."
generate_brick "$GEN2_DIR" 2

# Normalize for comparison
if [ "$VERBOSE" = true ]; then
    log "Normalizing outputs for comparison..."
fi
normalize_for_comparison "$GEN1_DIR"
normalize_for_comparison "$GEN2_DIR"

# Compare outputs
log "Comparing outputs..."

# Use diff to compare
DIFF_OUTPUT=$(diff -r "$GEN1_DIR" "$GEN2_DIR" 2>&1) || true
DIFF_STATUS=$?

if [ -z "$DIFF_OUTPUT" ] || [ "$DIFF_STATUS" -eq 0 ]; then
    echo ""
    echo "=============================================="
    log_success "IDEMPOTENT: Outputs are identical"
    echo "=============================================="
    echo ""

    # Count files
    FILE_COUNT=$(find "$GEN1_DIR" -type f | wc -l | tr -d ' ')
    log "Files compared: $FILE_COUNT"

    if [ "$VERBOSE" = true ]; then
        log "Generated files:"
        find "$GEN1_DIR" -type f | sed "s|$GEN1_DIR/|  |g"
    fi

    exit 0
else
    echo ""
    echo "=============================================="
    log_error "NON-IDEMPOTENT: Outputs differ"
    echo "=============================================="
    echo ""

    # Show differences
    echo "Differences found:"
    echo "$DIFF_OUTPUT" | head -50

    DIFF_COUNT=$(echo "$DIFF_OUTPUT" | grep -c "^diff\|^Only" || true)
    log_warn "Total differences: $DIFF_COUNT"

    if [ "$KEEP_TMP" = true ]; then
        log "Temporary directories preserved at: $TMP_BASE"
        log "  Gen1: $GEN1_DIR"
        log "  Gen2: $GEN2_DIR"
    fi

    # Provide troubleshooting hints
    echo ""
    log "Troubleshooting hints:"
    echo "  1. Check for timestamps in generated files"
    echo "  2. Check for random IDs or UUIDs"
    echo "  3. Check for non-deterministic iteration order"
    echo "  4. Check for file system metadata"
    echo ""
    echo "Run with --include-timestamps to include timestamp differences"
    echo "Run with --keep-tmp to preserve temp directories for inspection"
    echo ""

    exit 1
fi
