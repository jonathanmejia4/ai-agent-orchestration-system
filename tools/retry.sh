#!/bin/bash
#
# Retry Script with Exponential Backoff for SAF
#
# Wraps commands with automatic retry logic to handle transient failures
# like network issues, temporary service unavailability, etc.
#
# Usage:
#     tools/retry.sh <command>
#
# Exit Codes:
#     0-123 - Command's exit code (propagated from successful execution)
#     124   - Max retries exceeded (command failed all attempts)
#     125   - Error (invalid arguments)
#
# Examples:
#     # Retry git push (network issues)
#     tools/retry.sh "git push origin main"
#
#     # Retry API call
#     tools/retry.sh "curl -f https://api.example.com/status"
#
#     # Retry with error handling
#     if tools/retry.sh "git push origin main"; then
#       echo "Push succeeded"
#     else
#       echo "Push failed after retries"
#       exit 1
#     fi
#
# Referenced in:
#     - agent-coordination-protocol.md:461 (Transient failure handling)
#
# Author: SAF System
# Created: 2025-12-23
#

set -u  # Exit on undefined variable

# Configuration
MAX_RETRIES=5
INITIAL_BACKOFF=1  # seconds
MAX_BACKOFF=16     # seconds

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -eq 0 ]; then
    echo -e "${RED}❌ Error: No command provided${NC}" >&2
    echo "Usage: $0 <command>" >&2
    echo "" >&2
    echo "Examples:" >&2
    echo "  $0 'git push origin main'" >&2
    echo "  $0 'curl -f https://api.example.com/status'" >&2
    exit 125
fi

COMMAND="$*"

# Function: Calculate backoff delay (exponential with jitter)
calculate_backoff() {
    local attempt=$1
    local backoff=$((INITIAL_BACKOFF * (2 ** (attempt - 1))))

    # Cap backoff at MAX_BACKOFF
    if [ $backoff -gt $MAX_BACKOFF ]; then
        backoff=$MAX_BACKOFF
    fi

    # Add jitter (random 0-20% of backoff)
    local jitter=$((RANDOM % (backoff / 5 + 1)))
    backoff=$((backoff + jitter))

    echo $backoff
}

# Function: Execute command with retries
retry_command() {
    local attempt=1
    local exit_code=0

    echo -e "${BLUE}ℹ️  Running command with retry logic (max $MAX_RETRIES attempts)${NC}" >&2
    echo -e "${BLUE}ℹ️  Command: $COMMAND${NC}" >&2
    echo "" >&2

    while [ $attempt -le $MAX_RETRIES ]; do
        echo -e "${BLUE}▶ Attempt $attempt/$MAX_RETRIES${NC}" >&2

        # Execute command
        if eval "$COMMAND"; then
            echo "" >&2
            echo -e "${GREEN}✅ Command succeeded on attempt $attempt${NC}" >&2
            return 0
        else
            exit_code=$?
            echo "" >&2
            echo -e "${YELLOW}⚠️  Command failed with exit code $exit_code${NC}" >&2

            # Check if we should retry
            if [ $attempt -lt $MAX_RETRIES ]; then
                local backoff=$(calculate_backoff $attempt)
                echo -e "${YELLOW}⏳ Retrying in $backoff seconds...${NC}" >&2
                sleep $backoff
                attempt=$((attempt + 1))
                echo "" >&2
            else
                echo "" >&2
                echo -e "${RED}❌ Max retries ($MAX_RETRIES) exceeded${NC}" >&2
                echo -e "${RED}❌ Command failed with exit code: $exit_code${NC}" >&2
                return 124  # Custom exit code for max retries exceeded
            fi
        fi
    done
}

# Main execution
retry_command
exit $?
