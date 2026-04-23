#!/bin/bash
#
# LogBook Monthly Rollup Script
#
# Aggregates LogBook data from a specified month into summary reports and
# archives the detailed entries. Used for monthly log maintenance to prevent
# file count bloat.
#
# Usage:
#     tools/logbook_rollup.sh --month YYYY-MM
#
# Exit Codes:
#     0 - Rollup completed successfully
#     1 - Rollup failed
#     2 - Error (invalid parameters, missing directories, etc.)
#
# Examples:
#     # Rollup last month's data
#     tools/logbook_rollup.sh --month $(date -d "last month" +%Y-%m)
#
#     # Rollup specific month
#     tools/logbook_rollup.sh --month 2025-12
#
# Output:
#     - LogBook/rollups/monthly/YYYY-MM.md (human-readable summary)
#     - LogBook/rollups/monthly/YYYY-MM.json (machine-readable metrics)
#     - Moves original files to LogBook/archive/YYYY-MM/
#
# References:
#     - .claude/guidelines/quality-standards.md - Section 11.3: LogBook File Count Limits
#     - ISSUE_CATALOG.md - Issue A39
#
# Author: SAF System
# Created: 2025-12-23
#

set -euo pipefail

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
MONTH=""
LOGBOOK_DIR="LogBook"
ROLLUP_DIR="${LOGBOOK_DIR}/rollups/monthly"
ARCHIVE_DIR="${LOGBOOK_DIR}/archive"

# Usage function
usage() {
    cat <<USAGE
Usage: $0 --month YYYY-MM

Monthly LogBook aggregation and archival script.

Options:
    --month YYYY-MM     Month to roll up (e.g., 2025-12)
    --help             Show this help message

Examples:
    $0 --month 2025-12
    $0 --month \$(date -d "last month" +%Y-%m)

USAGE
    exit 2
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --month)
            MONTH="$2"
            shift 2
            ;;
        --help)
            usage
            ;;
        *)
            echo -e "${RED}ERROR${NC}: Unknown argument: $1"
            usage
            ;;
    esac
done

# Validate month parameter
if [[ -z "$MONTH" ]]; then
    echo -e "${RED}ERROR${NC}: --month parameter is required"
    usage
fi

# Validate month format (YYYY-MM)
if ! [[ "$MONTH" =~ ^[0-9]{4}-[0-9]{2}$ ]]; then
    echo -e "${RED}ERROR${NC}: Invalid month format. Expected YYYY-MM (e.g., 2025-12)"
    exit 2
fi

# Validate LogBook directory exists
if [[ ! -d "$LOGBOOK_DIR" ]]; then
    echo -e "${RED}ERROR${NC}: LogBook directory not found: $LOGBOOK_DIR"
    exit 2
fi

echo -e "${BLUE}LogBook Monthly Rollup${NC}"
echo "Month: $MONTH"
echo

# Create rollup and archive directories
mkdir -p "$ROLLUP_DIR"
mkdir -p "${ARCHIVE_DIR}/${MONTH}"

# Initialize counters
total_bricks=0
approved_count=0
conditional_count=0
blocked_count=0
rejected_count=0
rollback_count=0

# Arrays for categories
declare -A category_counts

# Find all LogBook entries from the specified month
# Look for files with timestamps matching YYYY-MM pattern
echo -e "${BLUE}Scanning LogBook entries for $MONTH...${NC}"

# Scan progress/bricks directory
if [[ -d "${LOGBOOK_DIR}/progress/bricks" ]]; then
    while IFS= read -r -d '' brick_file; do
        # Check if file timestamp matches month
        file_date=$(stat -f "%Sm" -t "%Y-%m" "$brick_file" 2>/dev/null || stat -c "%y" "$brick_file" 2>/dev/null | cut -d'-' -f1-2)
        
        if [[ "$file_date" == "$MONTH" ]]; then
            ((total_bricks++))
            
            # Extract status and category from file if possible
            if grep -q "status: approved" "$brick_file" 2>/dev/null; then
                ((approved_count++))
            elif grep -q "status: conditional" "$brick_file" 2>/dev/null; then
                ((conditional_count++))
            elif grep -q "status: blocked" "$brick_file" 2>/dev/null; then
                ((blocked_count++))
            elif grep -q "status: rejected" "$brick_file" 2>/dev/null; then
                ((rejected_count++))
            fi
            
            # Move to archive
            mkdir -p "${ARCHIVE_DIR}/${MONTH}/bricks"
            mv "$brick_file" "${ARCHIVE_DIR}/${MONTH}/bricks/"
        fi
    done < <(find "${LOGBOOK_DIR}/progress/bricks" -type f -print0 2>/dev/null || true)
fi

# Scan work-orders directory
work_order_count=0
if [[ -d "${LOGBOOK_DIR}/work-orders" ]]; then
    while IFS= read -r -d '' wo_file; do
        file_date=$(stat -f "%Sm" -t "%Y-%m" "$wo_file" 2>/dev/null || stat -c "%y" "$wo_file" 2>/dev/null | cut -d'-' -f1-2)
        
        if [[ "$file_date" == "$MONTH" ]]; then
            ((work_order_count++))
            
            # Move to archive
            mkdir -p "${ARCHIVE_DIR}/${MONTH}/work-orders"
            mv "$wo_file" "${ARCHIVE_DIR}/${MONTH}/work-orders/"
        fi
    done < <(find "${LOGBOOK_DIR}/work-orders" -type f -name "*.yaml" -print0 2>/dev/null || true)
fi

# Scan rollback directory
if [[ -d "${LOGBOOK_DIR}/rollback" ]]; then
    while IFS= read -r -d '' rollback_file; do
        file_date=$(stat -f "%Sm" -t "%Y-%m" "$rollback_file" 2>/dev/null || stat -c "%y" "$rollback_file" 2>/dev/null | cut -d'-' -f1-2)
        
        if [[ "$file_date" == "$MONTH" ]]; then
            ((rollback_count++))
            
            # Move to archive
            mkdir -p "${ARCHIVE_DIR}/${MONTH}/rollback"
            mv "$rollback_file" "${ARCHIVE_DIR}/${MONTH}/rollback/"
        fi
    done < <(find "${LOGBOOK_DIR}/rollback" -type f -print0 2>/dev/null || true)
fi

echo -e "${GREEN}✓${NC} Found $total_bricks bricks, $work_order_count work orders, $rollback_count rollbacks"

# Generate human-readable summary (Markdown)
echo -e "${BLUE}Generating ${ROLLUP_DIR}/${MONTH}.md...${NC}"

cat > "${ROLLUP_DIR}/${MONTH}.md" <<MARKDOWN
# LogBook Monthly Rollup - $MONTH

**Generated:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")

## Summary

- **Total Bricks:** $total_bricks
- **Work Orders:** $work_order_count
- **Rollbacks:** $rollback_count

## Brick Status Breakdown

- **Approved:** $approved_count
- **Conditional:** $conditional_count
- **Blocked:** $blocked_count
- **Rejected:** $rejected_count

## Archive Location

Detailed entries archived to: \`${ARCHIVE_DIR}/${MONTH}/\`

### Archived Directories
- \`${ARCHIVE_DIR}/${MONTH}/bricks/\` - Brick completion records
- \`${ARCHIVE_DIR}/${MONTH}/work-orders/\` - Work order files
- \`${ARCHIVE_DIR}/${MONTH}/rollback/\` - Rollback records

## Retention Policy

- **Detailed logs:** Kept for 3 months
- **Monthly rollups:** Kept for 12 months
- **Older than 12 months:** Archived to cold storage (optional)

---

**Maintained By:** SAF-Project-Manager  
**Archive Date:** $(date -u +"%Y-%m-%d")

MARKDOWN

echo -e "${GREEN}✓${NC} Created ${ROLLUP_DIR}/${MONTH}.md"

# Generate machine-readable metrics (JSON)
echo -e "${BLUE}Generating ${ROLLUP_DIR}/${MONTH}.json...${NC}"

cat > "${ROLLUP_DIR}/${MONTH}.json" <<JSON
{
  "month": "$MONTH",
  "generated_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "summary": {
    "total_bricks": $total_bricks,
    "work_orders": $work_order_count,
    "rollbacks": $rollback_count
  },
  "brick_status": {
    "approved": $approved_count,
    "conditional": $conditional_count,
    "blocked": $blocked_count,
    "rejected": $rejected_count
  },
  "archive_location": "${ARCHIVE_DIR}/${MONTH}",
  "archive_directories": {
    "bricks": "${ARCHIVE_DIR}/${MONTH}/bricks",
    "work_orders": "${ARCHIVE_DIR}/${MONTH}/work-orders",
    "rollback": "${ARCHIVE_DIR}/${MONTH}/rollback"
  }
}
JSON

echo -e "${GREEN}✓${NC} Created ${ROLLUP_DIR}/${MONTH}.json"

# Summary
echo
echo -e "${GREEN}✓ Monthly rollup completed successfully${NC}"
echo
echo "Summary:"
echo "  - Archived $total_bricks bricks"
echo "  - Archived $work_order_count work orders"
echo "  - Archived $rollback_count rollbacks"
echo "  - Reports: ${ROLLUP_DIR}/${MONTH}.md and ${ROLLUP_DIR}/${MONTH}.json"
echo "  - Archive: ${ARCHIVE_DIR}/${MONTH}/"

exit 0
