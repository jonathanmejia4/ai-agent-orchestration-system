#!/bin/bash
# tools/send_notification.sh
#
# Notification System with Retry Logic
#
# Sends notifications to Teams webhook with exponential backoff retry strategy.
# Handles network failures, rate limits, and webhook downtime gracefully.
#
# Usage:
#     tools/send_notification.sh "Your notification message"
#
# Exit Codes:
#     0 - Notification sent successfully
#     1 - Failed after 3 retry attempts
#     2 - Error (missing argument, invalid config, etc.)
#
# References:
#     - .claude/guidelines/edge-cases-and-recovery.md - Section 3: Notification Failure Handling
#     - integration/config/saf.integration.yaml - Webhook configuration
#
# Author: Framework System
# Created: 2025-12-23

set -euo pipefail

# Check for required argument
if [ $# -eq 0 ]; then
    echo "Usage: $0 <message>"
    echo
    echo "Examples:"
    echo "  $0 'Task 3.2 completed successfully'"
    echo "  $0 'Critical: Build failed on main branch'"
    exit 2
fi

MESSAGE="$1"

# Check if yq is available
if ! command -v yq &> /dev/null; then
    echo "❌ ERROR: yq is required but not installed"
    echo "Install: brew install yq"
    exit 2
fi

# Check if config file exists
CONFIG_FILE="integration/config/saf.integration.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ ERROR: Config file not found: $CONFIG_FILE"
    exit 2
fi

# Read webhook URL from config
WEBHOOK_URL=$(yq '.teams.webhook_url' "$CONFIG_FILE")

if [ -z "$WEBHOOK_URL" ] || [ "$WEBHOOK_URL" = "null" ]; then
    echo "❌ ERROR: No webhook URL configured in $CONFIG_FILE"
    echo "Expected: teams.webhook_url field"
    exit 2
fi

# Retry loop: 3 attempts with exponential backoff
for attempt in 1 2 3; do
    echo "Notification attempt $attempt/3"

    # Send notification and capture HTTP status code
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Content-Type: application/json" \
        -d "{\"text\":\"$MESSAGE\"}" \
        "$WEBHOOK_URL")

    # Check if successful
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✅ Notification sent successfully"
        exit 0
    fi

    # If this was the last attempt, don't sleep
    if [ $attempt -eq 3 ]; then
        echo "❌ HTTP $HTTP_CODE (final attempt failed)"
        break
    fi

    # Calculate backoff delay: 5s, 10s, 20s
    DELAY=$((5 * 2 ** (attempt - 1)))
    echo "❌ HTTP $HTTP_CODE, retrying in ${DELAY}s..."
    sleep "$DELAY"
done

# All attempts failed
echo "🔴 FAILED after 3 attempts, using fallback"
exit 1
