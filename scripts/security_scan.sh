#!/bin/bash
#
# Security Scan Script
# Scans repository for potential secrets, tokens, and local paths
#
# Usage: ./scripts/security_scan.sh
# Exit code: 0 if clean, 1 if findings detected
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "============================================================"
echo "               SECURITY SCAN"
echo "============================================================"
echo ""
echo "Scanning for secrets, tokens, and local paths..."
echo "Repository: $REPO_ROOT"
echo ""

FINDINGS=0

# Patterns to scan for
declare -a PATTERNS=(
    "AKIA[0-9A-Z]{16}"           # AWS Access Key ID
    "ghp_[0-9a-zA-Z]{36}"        # GitHub Personal Access Token
    "gho_[0-9a-zA-Z]{36}"        # GitHub OAuth Token
    "sk-[0-9a-zA-Z]{48}"         # OpenAI/Anthropic API Key
    "-----BEGIN PRIVATE KEY"     # Private key header
    "-----BEGIN RSA PRIVATE"     # RSA private key
    "/Users/[a-zA-Z]"            # macOS local paths
    "C:\\\\Users\\\\"            # Windows local paths
)

declare -a PATTERN_NAMES=(
    "AWS Access Key ID"
    "GitHub Personal Access Token"
    "GitHub OAuth Token"
    "API Key (OpenAI/Anthropic style)"
    "Private Key"
    "RSA Private Key"
    "macOS Local Path"
    "Windows Local Path"
)

# Files/dirs to exclude
EXCLUDE_PATTERNS="--exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules --exclude=*.pyc --exclude=security_scan.sh"

echo "Scanning for sensitive patterns..."
echo ""

for i in "${!PATTERNS[@]}"; do
    PATTERN="${PATTERNS[$i]}"
    NAME="${PATTERN_NAMES[$i]}"

    # Use grep with extended regex
    MATCHES=$(grep -rE $EXCLUDE_PATTERNS "$PATTERN" "$REPO_ROOT" 2>/dev/null || true)

    if [ -n "$MATCHES" ]; then
        echo "[FOUND] $NAME"
        echo "$MATCHES" | head -5
        echo ""
        FINDINGS=$((FINDINGS + 1))
    fi
done

echo "============================================================"

if [ $FINDINGS -gt 0 ]; then
    echo "[FAIL] Found $FINDINGS potential security issues"
    echo ""
    echo "Please review and remove sensitive data before committing."
    exit 1
else
    echo "[PASS] No secrets or local paths detected"
    echo ""
    echo "Repository appears clean for public sharing."
    exit 0
fi
