#!/usr/bin/env bash
#
# Generate LogBook Entries Hook
# Auto-generates LogBook entries for significant changes
# (Disabled by default - enable in .githooks/config.yaml)
#

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
LOGBOOK_DIR="${REPO_ROOT}/LogBook"
AUDIT_DIR="${LOGBOOK_DIR}/audit"

# Get staged files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR)

if [ -z "${STAGED_FILES}" ]; then
    exit 0
fi

# Ensure audit directory exists
mkdir -p "${AUDIT_DIR}"

# Track what needs logging
LOG_STATE_CHANGE=false
LOG_POLICY_CHANGE=false
LOG_ESCALATION=false

# Check for significant changes
while IFS= read -r file; do
    [ -z "${file}" ] && continue

    case "${file}" in
        LogBook/pm/STATE.md)
            LOG_STATE_CHANGE=true
            ;;
        PLANNING/*_POLICY.md)
            LOG_POLICY_CHANGE=true
            ;;
        LogBook/pm/escalations/*)
            LOG_ESCALATION=true
            ;;
    esac
done <<< "${STAGED_FILES}"

TIMESTAMP=$(date -Iseconds)
COMMIT_USER=$(git config user.name 2>/dev/null || echo "unknown")

# Generate audit log entries
if [ "${LOG_STATE_CHANGE}" = true ]; then
    echo "${TIMESTAMP} | STATE_CHANGE | ${COMMIT_USER} | LogBook/pm/STATE.md modified" >> "${AUDIT_DIR}/state-changes.log"
fi

if [ "${LOG_POLICY_CHANGE}" = true ]; then
    POLICY_FILES=$(echo "${STAGED_FILES}" | grep "PLANNING/.*_POLICY.md" | tr '\n' ', ')
    echo "${TIMESTAMP} | POLICY_CHANGE | ${COMMIT_USER} | ${POLICY_FILES}" >> "${AUDIT_DIR}/policy-changes.log"
fi

if [ "${LOG_ESCALATION}" = true ]; then
    echo "${TIMESTAMP} | ESCALATION | ${COMMIT_USER} | New escalation committed" >> "${AUDIT_DIR}/escalations.log"
fi

# This hook doesn't block commits, just logs
exit 0
