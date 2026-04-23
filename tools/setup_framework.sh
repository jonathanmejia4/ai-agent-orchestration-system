#!/bin/bash
#
# setup_saf.sh - Framework Development Environment Setup
#
# Initializes the Framework development environment by creating required
# directories, installing dependencies, and validating prerequisites.
#
# Usage:
#   ./tools/setup_saf.sh
#   ./tools/setup_saf.sh --minimal     # Skip optional dependencies
#   ./tools/setup_saf.sh --validate    # Only validate existing setup
#   ./tools/setup_saf.sh --help
#
# Exit Codes:
#   0 - Setup completed successfully
#   1 - Prerequisites not met
#   2 - Setup failed
#
# Referenced in:
#   - PLANNING/future/enforcement_roadmap.md:320
#
# Author: The Framework
# Created: 2025-12-23

set -euo pipefail

# Script version
VERSION="1.0.0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
MINIMAL=false
VALIDATE_ONLY=false
VERBOSE=false
FORCE=false

# Counters
CREATED_COUNT=0
SKIPPED_COUNT=0
ERROR_COUNT=0

usage() {
    cat << EOF
Framework Setup Script v${VERSION}

Usage: $(basename "$0") [OPTIONS]

Options:
    -h, --help          Show this help message
    -m, --minimal       Skip optional dependencies (pip packages)
    -v, --validate      Only validate existing setup, don't modify
    --verbose           Verbose output
    -f, --force         Force recreation of existing directories
    --version           Show version

Examples:
    $(basename "$0")                    # Full setup
    $(basename "$0") --minimal          # Skip Python packages
    $(basename "$0") --validate         # Check existing setup

This script will:
  1. Check prerequisites (Python, git, bash)
  2. Create required directory structure
  3. Install Python dependencies (unless --minimal)
  4. Initialize configuration files
  5. Validate setup completion
EOF
}

log() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}  ✅${NC} $*"
}

log_error() {
    echo -e "${RED}  ❌${NC} $*" >&2
}

log_warning() {
    echo -e "${YELLOW}  ⚠️ ${NC} $*"
}

log_skip() {
    echo -e "${CYAN}  ⏭️ ${NC} $*"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -m|--minimal)
            MINIMAL=true
            shift
            ;;
        -v|--validate)
            VALIDATE_ONLY=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        --version)
            echo "Framework Setup Script v${VERSION}"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 2
            ;;
    esac
done

echo ""
echo -e "${BLUE}Framework Setup Script v${VERSION}${NC}"
echo "===================="
echo ""

# Change to repo root
cd "$REPO_ROOT"

# =============================================================================
# Prerequisites Check
# =============================================================================

log "Checking prerequisites..."

# Check Python
PYTHON_OK=false
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 9 ]; then
        log_success "Python ${PYTHON_VERSION} found"
        PYTHON_OK=true
    else
        log_warning "Python ${PYTHON_VERSION} found (3.9+ recommended)"
        PYTHON_OK=true  # Still usable
    fi
else
    log_error "Python 3 not found"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi

# Check git
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | awk '{print $3}')
    log_success "git ${GIT_VERSION} found"
else
    log_error "git not found"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi

# Check bash version
BASH_VERSION_NUM="${BASH_VERSION%%(*}"
BASH_MAJOR=$(echo "$BASH_VERSION_NUM" | cut -d. -f1)
if [ "$BASH_MAJOR" -ge 4 ]; then
    log_success "bash ${BASH_VERSION_NUM} found"
else
    log_warning "bash ${BASH_VERSION_NUM} found (4.0+ recommended)"
fi

# Check for optional tools
if command -v jq &> /dev/null; then
    log_success "jq found (optional)"
else
    log_skip "jq not found (optional, install for JSON processing)"
fi

if command -v yq &> /dev/null; then
    log_success "yq found (optional)"
else
    log_skip "yq not found (optional, install for YAML processing)"
fi

echo ""

# Exit if validate only
if [ "$VALIDATE_ONLY" = true ]; then
    log "Validating existing setup..."
    echo ""
fi

# Exit if prerequisites failed
if [ "$ERROR_COUNT" -gt 0 ]; then
    log_error "Prerequisites check failed. Please install missing tools."
    exit 1
fi

# =============================================================================
# Directory Structure
# =============================================================================

log "Creating directory structure..."

create_dir() {
    local dir="$1"
    local desc="${2:-}"

    if [ -d "$dir" ]; then
        if [ "$FORCE" = true ]; then
            log_warning "Recreating $dir"
        else
            if [ "$VERBOSE" = true ]; then
                log_skip "$dir (exists)"
            fi
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
            return 0
        fi
    fi

    if [ "$VALIDATE_ONLY" = true ]; then
        log_error "$dir (missing)"
        ERROR_COUNT=$((ERROR_COUNT + 1))
        return 1
    fi

    mkdir -p "$dir"
    log_success "Created $dir"
    CREATED_COUNT=$((CREATED_COUNT + 1))
}

# LogBook directories
create_dir "LogBook/critic/verdicts"
create_dir "LogBook/pm/decisions"
create_dir "LogBook/pm/escalations"
create_dir "LogBook/progress/bricks"
create_dir "LogBook/progress/plans"
create_dir "LogBook/work-orders"
create_dir "LogBook/rollback"

# PLANNING directories
create_dir "PLANNING/specs"
create_dir "PLANNING/bricks"
create_dir "PLANNING/future"
create_dir "PLANNING/schemas"
create_dir "PLANNING/policy"

# Development directories
create_dir "tools"
create_dir ".task"
create_dir "templates"
create_dir "archives"
create_dir "docs"
create_dir "docs/api"

# GitHub directories
create_dir ".github/workflows"
create_dir ".github/ISSUE_TEMPLATE"

echo ""

# =============================================================================
# Index Files
# =============================================================================

log "Creating index files..."

create_index() {
    local file="$1"
    local title="$2"
    local desc="$3"

    if [ -f "$file" ]; then
        log_skip "$file (exists)"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        return 0
    fi

    if [ "$VALIDATE_ONLY" = true ]; then
        log_warning "$file (missing, optional)"
        return 0
    fi

    cat > "$file" << EOF
# ${title}

${desc}

## Contents

_This directory is currently empty._

---
Created by Framework Setup Script v${VERSION}
EOF

    log_success "Created $file"
    CREATED_COUNT=$((CREATED_COUNT + 1))
}

# Create INDEX.md files for key directories
create_index "LogBook/INDEX.md" "LogBook Index" \
    "Operational logs, work orders, and decision records."

create_index "LogBook/critic/INDEX.md" "Critic Logs" \
    "Critic agent verdicts and code review records."

create_index "LogBook/pm/INDEX.md" "PM Logs" \
    "Project Manager decisions, escalations, and state tracking."

create_index "LogBook/work-orders/INDEX.md" "Work Orders" \
    "Active and completed work orders for Builder agents."

create_index "PLANNING/specs/INDEX.md" "Specifications" \
    "Feature specifications and requirements documents."

create_index "PLANNING/tasks/INDEX.md" "Task Plans" \
    "Task generation plans and templates."

create_index "archives/INDEX.md" "Archives" \
    "Archived bricks, logs, and historical records."

create_index "templates/INDEX.md" "Templates" \
    "Code generation templates for various frameworks."

echo ""

# =============================================================================
# Python Dependencies
# =============================================================================

if [ "$MINIMAL" = false ] && [ "$VALIDATE_ONLY" = false ]; then
    log "Installing Python dependencies..."

    # Core dependencies
    CORE_DEPS=(
        "pyyaml"
        "jinja2"
    )

    for pkg in "${CORE_DEPS[@]}"; do
        if python3 -c "import ${pkg//-/_}" 2>/dev/null; then
            log_skip "$pkg (already installed)"
        else
            if pip3 install --quiet "$pkg" 2>/dev/null; then
                log_success "Installed $pkg"
                CREATED_COUNT=$((CREATED_COUNT + 1))
            else
                log_warning "Failed to install $pkg"
            fi
        fi
    done

    echo ""
elif [ "$VALIDATE_ONLY" = true ]; then
    log "Checking Python dependencies..."

    CORE_DEPS=("yaml" "jinja2")

    for pkg in "${CORE_DEPS[@]}"; do
        if python3 -c "import $pkg" 2>/dev/null; then
            log_success "$pkg available"
        else
            log_warning "$pkg not installed"
        fi
    done

    echo ""
else
    log_skip "Skipping Python dependencies (--minimal)"
    echo ""
fi

# =============================================================================
# Configuration Files
# =============================================================================

log "Initializing configuration..."

# Create .saf directory for local config
if [ ! -d ".saf" ]; then
    if [ "$VALIDATE_ONLY" = false ]; then
        mkdir -p ".saf"
        log_success "Created .saf/"
        CREATED_COUNT=$((CREATED_COUNT + 1))
    else
        log_warning ".saf/ directory missing"
    fi
else
    log_skip ".saf/ (exists)"
fi

# Create config.yaml
CONFIG_FILE=".saf/config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    if [ "$VALIDATE_ONLY" = false ]; then
        cat > "$CONFIG_FILE" << EOF
# Framework Configuration
# Generated by setup_saf.sh v${VERSION}

version: "1.0"
project:
  name: "Framework Project"
  created: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

paths:
  logbook: "LogBook"
  planning: "PLANNING"
  tools: "tools"
  templates: "templates"
  archives: "archives"

agents:
  pm:
    enabled: true
  builder:
    enabled: true
  critic:
    enabled: true
  planner:
    enabled: true

validation:
  strict_mode: false
  enforce_schemas: true

logging:
  level: "INFO"
  format: "text"
EOF
        log_success "Created $CONFIG_FILE"
        CREATED_COUNT=$((CREATED_COUNT + 1))
    else
        log_warning "$CONFIG_FILE missing"
    fi
else
    log_skip "$CONFIG_FILE (exists)"
fi

# Add .saf to .gitignore if not present
GITIGNORE=".gitignore"
if [ -f "$GITIGNORE" ]; then
    if ! grep -q "^\.saf/$" "$GITIGNORE" 2>/dev/null; then
        if [ "$VALIDATE_ONLY" = false ]; then
            echo ".saf/" >> "$GITIGNORE"
            log_success "Added .saf/ to .gitignore"
        fi
    else
        log_skip ".saf/ already in .gitignore"
    fi
fi

echo ""

# =============================================================================
# Git Hooks (Optional)
# =============================================================================

if [ "$VALIDATE_ONLY" = false ] && [ -d ".git" ]; then
    log "Checking git hooks..."

    HOOKS_DIR=".git/hooks"

    # Check if install_hooks.sh exists and offer to run it
    if [ -f "tools/install_hooks.sh" ]; then
        log_skip "Git hooks installer available (run tools/install_hooks.sh)"
    else
        log_skip "Git hooks installer not found (optional)"
    fi

    echo ""
fi

# =============================================================================
# Validation
# =============================================================================

log "Validating setup..."

VALIDATION_ERRORS=0

# Check critical directories
CRITICAL_DIRS=(
    "LogBook"
    "PLANNING"
    "tools"
)

for dir in "${CRITICAL_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        log_success "$dir/ exists"
    else
        log_error "$dir/ missing"
        VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
    fi
done

# Check for critical tools
CRITICAL_TOOLS=(
    "tools/validate_work_order.py"
    "tools/logbook_append.sh"
)

for tool in "${CRITICAL_TOOLS[@]}"; do
    if [ -f "$tool" ]; then
        log_success "$tool exists"
    else
        log_warning "$tool missing (may need to be created)"
    fi
done

echo ""

# =============================================================================
# Summary
# =============================================================================

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Setup Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ "$VALIDATE_ONLY" = true ]; then
    echo "  Mode:       Validation only"
else
    echo "  Mode:       Full setup"
fi

echo "  Created:    $CREATED_COUNT items"
echo "  Skipped:    $SKIPPED_COUNT items (already exist)"
echo "  Errors:     $ERROR_COUNT"
echo ""

if [ "$ERROR_COUNT" -gt 0 ] || [ "$VALIDATION_ERRORS" -gt 0 ]; then
    echo -e "${RED}Setup completed with errors.${NC}"
    echo "Please review the errors above and fix manually."
    exit 2
fi

echo -e "${GREEN}Setup complete!${NC}"
echo ""

if [ "$VALIDATE_ONLY" = false ]; then
    echo "Next steps:"
    echo "  1. Review PLANNING/GETTING_STARTED.md (if exists)"
    echo "  2. Run: python3 tools/validate_environment.py (if exists)"
    echo "  3. Run: ./tools/install_hooks.sh (if exists)"
    echo ""
fi

exit 0
