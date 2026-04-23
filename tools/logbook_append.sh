#!/bin/bash
#
# LogBook Atomic Append Script for SAF
#
# Atomically appends data to LogBook JSON/text files with retry logic
# and file locking to prevent race conditions and data corruption.
#
# Usage:
#     tools/logbook_append.sh <file_path> <data>
#
# Exit Codes:
#     0 - Success (data appended)
#     1 - Failure (max retries exceeded, validation failed)
#     2 - Error (invalid arguments, permissions issues)
#
# Examples:
#     # Append to JSON array
#     tools/logbook_append.sh LogBook/metrics/history.json '{"timestamp": "2025-12-23T10:00:00Z", "metric": "build_time", "value": 45}'
#
#     # Append to text log
#     tools/logbook_append.sh LogBook/pm/sessions/session.log "Session started at $(date)"
#
#     # Append with error handling
#     if tools/logbook_append.sh LogBook/metrics/history.json "$NEW_METRIC"; then
#       echo "Metric recorded successfully"
#     else
#       echo "Failed to record metric after retries"
#       exit 1
#     fi
#
# Referenced in:
#     - agent-coordination-protocol.md:766 (Designated writer pattern)
#     - agent-coordination-protocol.md:804 (Atomic LogBook updates)
#     - agent-coordination-protocol.md:886 (Retry logic example)
#
# Author: SAF System
# Created: 2025-12-23
#

set -u  # Exit on undefined variable

# Configuration
MAX_RETRIES=5
INITIAL_BACKOFF=0.1  # seconds (100ms)
MAX_BACKOFF=2        # seconds
LOCK_TIMEOUT=10      # seconds

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -ne 2 ]; then
    echo -e "${RED}❌ Error: Invalid arguments${NC}" >&2
    echo "Usage: $0 <file_path> <data>" >&2
    echo "" >&2
    echo "Examples:" >&2
    echo "  $0 LogBook/metrics/history.json '{\"metric\": \"value\"}'" >&2
    echo "  $0 LogBook/pm/sessions/log.txt 'Log entry'" >&2
    exit 2
fi

FILE_PATH="$1"
DATA="$2"
LOCK_FILE="${FILE_PATH}.lock"

# Function: Acquire file lock with timeout
acquire_lock() {
    local timeout=$1
    local start_time=$(date +%s)

    while true; do
        # Try to create lock file atomically
        if mkdir "$LOCK_FILE" 2>/dev/null; then
            # Lock acquired
            echo $$ > "$LOCK_FILE/pid"
            return 0
        fi

        # Check timeout
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [ $elapsed -ge $timeout ]; then
            echo -e "${RED}❌ Lock timeout: Could not acquire lock after ${timeout}s${NC}" >&2
            return 1
        fi

        # Wait before retry
        sleep 0.1
    done
}

# Function: Release file lock
release_lock() {
    if [ -d "$LOCK_FILE" ]; then
        rm -rf "$LOCK_FILE"
    fi
}

# Function: Ensure lock is released on exit
cleanup() {
    release_lock
}
trap cleanup EXIT INT TERM

# Function: Validate JSON syntax
validate_json() {
    local json_string="$1"

    if command -v python3 &> /dev/null; then
        echo "$json_string" | python3 -m json.tool &> /dev/null
        return $?
    else
        # Fallback: basic validation (check for balanced braces/brackets)
        local open_braces=$(echo "$json_string" | grep -o '{' | wc -l)
        local close_braces=$(echo "$json_string" | grep -o '}' | wc -l)
        local open_brackets=$(echo "$json_string" | grep -o '\[' | wc -l)
        local close_brackets=$(echo "$json_string" | grep -o '\]' | wc -l)

        if [ "$open_braces" -eq "$close_braces" ] && [ "$open_brackets" -eq "$close_brackets" ]; then
            return 0
        else
            return 1
        fi
    fi
}

# Function: Detect file type
detect_file_type() {
    local file="$1"

    if [[ "$file" == *.json ]]; then
        echo "json"
    else
        echo "text"
    fi
}

# Function: Append to JSON file
append_to_json() {
    local file="$1"
    local data="$2"

    # Validate input JSON
    if ! validate_json "$data"; then
        echo -e "${RED}❌ Invalid JSON data provided${NC}" >&2
        return 1
    fi

    # Create file if it doesn't exist (empty JSON array)
    if [ ! -f "$file" ]; then
        echo "[]" > "$file"
    fi

    # Read existing content
    local existing_content
    existing_content=$(cat "$file")

    # Validate existing content
    if ! validate_json "$existing_content"; then
        echo -e "${RED}❌ Existing file contains invalid JSON${NC}" >&2
        return 1
    fi

    # Determine if existing content is array or object
    local first_char
    first_char=$(echo "$existing_content" | tr -d '[:space:]' | head -c 1)

    if [ "$first_char" = "[" ]; then
        # Append to JSON array
        local new_content
        if command -v python3 &> /dev/null; then
            new_content=$(python3 -c "
import json
import sys

existing = json.loads('''$existing_content''')
new_item = json.loads('''$data''')

if not isinstance(existing, list):
    existing = [existing]

existing.append(new_item)
print(json.dumps(existing, indent=2))
")
        else
            # Fallback: manual array append (less robust)
            local trimmed_existing
            trimmed_existing=$(echo "$existing_content" | sed 's/^[[:space:]]*\[//' | sed 's/\][[:space:]]*$//')

            if [ -z "$trimmed_existing" ] || [ "$trimmed_existing" = "[]" ]; then
                new_content="[$data]"
            else
                new_content="[$trimmed_existing,$data]"
            fi
        fi

        echo "$new_content" > "$file"
        return $?

    else
        echo -e "${YELLOW}⚠️  Warning: File contains JSON object, not array. Appending as new array item.${NC}" >&2
        # Convert object to array with new item
        if command -v python3 &> /dev/null; then
            new_content=$(python3 -c "
import json
existing = json.loads('''$existing_content''')
new_item = json.loads('''$data''')
print(json.dumps([existing, new_item], indent=2))
")
            echo "$new_content" > "$file"
            return $?
        else
            echo -e "${RED}❌ Cannot append to JSON object without Python${NC}" >&2
            return 1
        fi
    fi
}

# Function: Append to text file
append_to_text() {
    local file="$1"
    local data="$2"

    # Create file if it doesn't exist
    if [ ! -f "$file" ]; then
        touch "$file"
    fi

    # Append with newline
    echo "$data" >> "$file"
    return $?
}

# Function: Calculate backoff delay (exponential with jitter)
calculate_backoff() {
    local attempt=$1
    local backoff=$(awk "BEGIN {print $INITIAL_BACKOFF * (2 ^ ($attempt - 1))}")

    # Cap backoff at MAX_BACKOFF
    backoff=$(awk "BEGIN {print ($backoff > $MAX_BACKOFF) ? $MAX_BACKOFF : $backoff}")

    # Add jitter (random 0-20% of backoff)
    local jitter=$(awk "BEGIN {print $backoff * 0.2 * $RANDOM / 32767}")
    backoff=$(awk "BEGIN {print $backoff + $jitter}")

    echo "$backoff"
}

# Function: Atomic append with retries
atomic_append() {
    local file="$1"
    local data="$2"
    local file_type
    file_type=$(detect_file_type "$file")

    local attempt=1

    while [ $attempt -le $MAX_RETRIES ]; do
        # Acquire lock
        if ! acquire_lock $LOCK_TIMEOUT; then
            if [ $attempt -lt $MAX_RETRIES ]; then
                local backoff
                backoff=$(calculate_backoff $attempt)
                echo -e "${YELLOW}⚠️  Retry $attempt/$MAX_RETRIES: Waiting ${backoff}s...${NC}" >&2
                sleep "$backoff"
                attempt=$((attempt + 1))
                continue
            else
                echo -e "${RED}❌ Max retries ($MAX_RETRIES) exceeded${NC}" >&2
                return 1
            fi
        fi

        # Perform append based on file type
        local append_result=0
        if [ "$file_type" = "json" ]; then
            append_to_json "$file" "$data"
            append_result=$?
        else
            append_to_text "$file" "$data"
            append_result=$?
        fi

        # Release lock
        release_lock

        # Check result
        if [ $append_result -eq 0 ]; then
            echo -e "${GREEN}✅ Successfully appended to $file${NC}" >&2
            return 0
        else
            if [ $attempt -lt $MAX_RETRIES ]; then
                local backoff
                backoff=$(calculate_backoff $attempt)
                echo -e "${YELLOW}⚠️  Append failed, retry $attempt/$MAX_RETRIES: Waiting ${backoff}s...${NC}" >&2
                sleep "$backoff"
                attempt=$((attempt + 1))
            else
                echo -e "${RED}❌ Append failed after $MAX_RETRIES attempts${NC}" >&2
                return 1
            fi
        fi
    done

    return 1
}

# Main execution
echo -e "${BLUE}ℹ️  Appending to LogBook file: $FILE_PATH${NC}" >&2

# Ensure parent directory exists
PARENT_DIR=$(dirname "$FILE_PATH")
if [ ! -d "$PARENT_DIR" ]; then
    echo -e "${YELLOW}⚠️  Parent directory does not exist: $PARENT_DIR${NC}" >&2
    echo -e "${BLUE}ℹ️  Creating directory...${NC}" >&2
    mkdir -p "$PARENT_DIR"
fi

# Perform atomic append
atomic_append "$FILE_PATH" "$DATA"
exit $?
