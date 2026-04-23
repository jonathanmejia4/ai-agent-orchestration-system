#!/bin/bash
# SAF Git Hooks Installer
# Version: 1.0.0
# Last Updated: 2025-12-24
# Owner: PM
# Classification: HIGH - Development Tool
#
# This script installs SAF git hooks into the local repository.
# Run from the project root: bash tools/hooks/install_hooks.sh
#
# Hooks installed:
# - pre-commit: Validates code quality and policy compliance
# - commit-msg: Validates commit message format
# - pre-push: Final validation before pushing

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get script and project directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"

if [ -z "$PROJECT_ROOT" ]; then
    echo -e "${RED}Error: Not in a git repository.${NC}"
    exit 1
fi

# Hooks source and destination
HOOKS_SOURCE="$PROJECT_ROOT/.githooks"
HOOKS_DEST="$PROJECT_ROOT/.git/hooks"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}SAF Git Hooks Installer${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Project root: $PROJECT_ROOT"
echo "Hooks source: $HOOKS_SOURCE"
echo "Hooks destination: $HOOKS_DEST"
echo ""

# Check if .githooks directory exists
if [ ! -d "$HOOKS_SOURCE" ]; then
    echo -e "${YELLOW}Creating .githooks directory...${NC}"
    mkdir -p "$HOOKS_SOURCE"
fi

# Ensure .git/hooks exists
if [ ! -d "$HOOKS_DEST" ]; then
    echo -e "${RED}Error: .git/hooks directory not found.${NC}"
    echo "Make sure you're in a git repository."
    exit 1
fi

# Function to install a hook
install_hook() {
    local hook_name=$1
    local source_file="$HOOKS_SOURCE/$hook_name"
    local dest_file="$HOOKS_DEST/$hook_name"

    if [ -f "$source_file" ]; then
        # Backup existing hook if it exists and isn't a symlink
        if [ -f "$dest_file" ] && [ ! -L "$dest_file" ]; then
            local backup_file="${dest_file}.backup.$(date +%Y%m%d%H%M%S)"
            echo -e "${YELLOW}Backing up existing $hook_name to $backup_file${NC}"
            mv "$dest_file" "$backup_file"
        fi

        # Remove existing symlink or file
        rm -f "$dest_file"

        # Create symlink
        ln -s "$source_file" "$dest_file"

        # Make executable
        chmod +x "$source_file"

        echo -e "${GREEN}✓ Installed: $hook_name${NC}"
        return 0
    else
        echo -e "${YELLOW}- Skipped: $hook_name (source not found)${NC}"
        return 1
    fi
}

# Install pre-commit hook
echo ""
echo "Installing hooks..."

install_hook "pre-commit"

# Create commit-msg hook if it doesn't exist
if [ ! -f "$HOOKS_SOURCE/commit-msg" ]; then
    echo -e "${BLUE}Creating commit-msg hook...${NC}"
    cat > "$HOOKS_SOURCE/commit-msg" << 'EOF'
#!/bin/bash
# SAF Commit Message Hook
# Validates commit message format

COMMIT_MSG_FILE=$1
COMMIT_MSG=$(cat "$COMMIT_MSG_FILE")

# Minimum length check
if [ ${#COMMIT_MSG} -lt 10 ]; then
    echo "Error: Commit message too short (minimum 10 characters)."
    exit 1
fi

# Check for conventional commit format (optional but recommended)
CONVENTIONAL_PATTERN="^(feat|fix|docs|style|refactor|test|chore|build|ci|perf|revert)(\(.+\))?: .+"
if ! echo "$COMMIT_MSG" | head -1 | grep -qE "$CONVENTIONAL_PATTERN"; then
    echo "Warning: Commit message doesn't follow conventional format."
    echo "Recommended: type(scope): description"
    echo "Types: feat, fix, docs, style, refactor, test, chore, build, ci, perf, revert"
    # Warning only, don't block
fi

exit 0
EOF
    chmod +x "$HOOKS_SOURCE/commit-msg"
fi
install_hook "commit-msg"

# Create pre-push hook if it doesn't exist
if [ ! -f "$HOOKS_SOURCE/pre-push" ]; then
    echo -e "${BLUE}Creating pre-push hook...${NC}"
    cat > "$HOOKS_SOURCE/pre-push" << 'EOF'
#!/bin/bash
# SAF Pre-Push Hook
# Final validation before pushing to remote

set -e

echo "Running pre-push checks..."

# Check for force push to protected branches
PROTECTED_BRANCHES="main master develop"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

for branch in $PROTECTED_BRANCHES; do
    if [ "$CURRENT_BRANCH" = "$branch" ]; then
        # Check if this is a force push
        while read local_ref local_sha remote_ref remote_sha; do
            if [ "$local_sha" = "0000000000000000000000000000000000000000" ]; then
                continue  # Branch deletion, allow
            fi

            if [ "$remote_sha" != "0000000000000000000000000000000000000000" ]; then
                # Check if local is ancestor of remote (would need force push)
                if ! git merge-base --is-ancestor "$remote_sha" "$local_sha" 2>/dev/null; then
                    echo "Error: Force push to $branch branch detected!"
                    echo "This requires explicit --force flag and is not recommended."
                    exit 1
                fi
            fi
        done
        break
    fi
done

echo "Pre-push checks passed."
exit 0
EOF
    chmod +x "$HOOKS_SOURCE/pre-push"
fi
install_hook "pre-push"

# Configure git to use hooks from .githooks
echo ""
echo -e "${BLUE}Configuring git hooks path...${NC}"

# Option 1: Use core.hooksPath (Git 2.9+)
GIT_VERSION=$(git --version | awk '{print $3}')
MAJOR_VERSION=$(echo "$GIT_VERSION" | cut -d. -f1)
MINOR_VERSION=$(echo "$GIT_VERSION" | cut -d. -f2)

if [ "$MAJOR_VERSION" -gt 2 ] || ([ "$MAJOR_VERSION" -eq 2 ] && [ "$MINOR_VERSION" -ge 9 ]); then
    echo "Git version $GIT_VERSION supports core.hooksPath"
    echo -e "${YELLOW}You can also use: git config core.hooksPath .githooks${NC}"
else
    echo "Git version $GIT_VERSION - using symlinks for hooks"
fi

# Verify installation
echo ""
echo -e "${BLUE}Verifying installation...${NC}"

INSTALLED_COUNT=0
for hook in pre-commit commit-msg pre-push; do
    if [ -L "$HOOKS_DEST/$hook" ] || [ -x "$HOOKS_DEST/$hook" ]; then
        echo -e "${GREEN}✓ $hook is installed and executable${NC}"
        INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
    else
        echo -e "${RED}✗ $hook is not properly installed${NC}"
    fi
done

echo ""
echo -e "${BLUE}========================================${NC}"
if [ $INSTALLED_COUNT -eq 3 ]; then
    echo -e "${GREEN}All hooks installed successfully!${NC}"
else
    echo -e "${YELLOW}Some hooks may need manual attention.${NC}"
fi
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Usage:"
echo "  - Hooks run automatically on git operations"
echo "  - To bypass (not recommended): git commit --no-verify"
echo "  - To update hooks: re-run this script"
echo ""
echo "Hooks location: $HOOKS_SOURCE"
echo ""

# Create .gitattributes entry to keep hooks executable
if [ ! -f "$PROJECT_ROOT/.gitattributes" ]; then
    echo "# Git attributes for SAF" > "$PROJECT_ROOT/.gitattributes"
fi

if ! grep -q ".githooks" "$PROJECT_ROOT/.gitattributes" 2>/dev/null; then
    echo "" >> "$PROJECT_ROOT/.gitattributes"
    echo "# Keep hooks executable" >> "$PROJECT_ROOT/.gitattributes"
    echo ".githooks/* text eol=lf" >> "$PROJECT_ROOT/.gitattributes"
    echo -e "${GREEN}Updated .gitattributes${NC}"
fi

exit 0
