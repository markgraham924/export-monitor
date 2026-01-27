#!/bin/bash
# Export Monitor - Git Workflow Script (Bash)
# Follows Semantic Versioning 2.0.0 (https://semver.org/)
# Usage: ./tag.sh ["commit message"] [--skip-sync]

set -e  # Exit on error

MANIFEST_PATH="custom_components/export_monitor/manifest.json"
REMOTE_HOST="192.168.0.202"

# Parse arguments
COMMIT_MSG="$1"
SKIP_SYNC=false
if [[ "$2" == "--skip-sync" ]] || [[ "$1" == "--skip-sync" ]]; then
    SKIP_SYNC=true
    if [[ "$1" == "--skip-sync" ]]; then
        COMMIT_MSG=""
    fi
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

# Validate SemVer format (MAJOR.MINOR.PATCH)
validate_semver() {
    local version=$1
    if [[ ! $version =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
        echo -e "${RED}Error: Invalid SemVer format: $version${NC}"
        echo "Must be MAJOR.MINOR.PATCH (e.g., 1.0.1)"
        exit 1
    fi
}

echo -e "${CYAN}======================================"
echo "Export Monitor - Git Workflow (SemVer)"
echo -e "======================================${NC}\n"

# Step 1: Pull latest changes
echo -e "${CYAN}Pulling latest changes...${NC}"
git fetch --all --tags --prune

LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse '@{u}' 2>/dev/null || echo "")

if [ -n "$REMOTE" ] && [ "$LOCAL" != "$REMOTE" ]; then
    BASE=$(git merge-base @ '@{u}')
    
    if [ "$LOCAL" = "$BASE" ]; then
        echo -e "${YELLOW}Behind remote, pulling changes...${NC}"
        git pull --rebase
    elif [ "$REMOTE" = "$BASE" ]; then
        echo -e "${GREEN}Local ahead of remote (will push later)${NC}"
    else
        echo -e "${RED}Error: Branches have diverged. Manual intervention required.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}Already up to date${NC}"
fi
echo ""

# Step 2: Commit changes if any
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo -e "${YELLOW}Changes detected:${NC}"
    git status --short
    echo ""
    
    if [ -z "$COMMIT_MSG" ]; then
        echo -e "${CYAN}Enter commit message:${NC}"
        read -r COMMIT_MSG
    fi
    
    if [ -z "$COMMIT_MSG" ]; then
        echo -e "${RED}Error: Commit message required${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Committing changes...${NC}"
    git add .
    git commit -m "$COMMIT_MSG"
    COMMITTED=true
else
    echo -e "${GREEN}No changes to commit (working tree clean)${NC}"
    COMMITTED=false
fi
echo ""

# Step 3: Extract and validate version
if [ ! -f "$MANIFEST_PATH" ]; then
    echo -e "${RED}Error: manifest.json not found!${NC}"
    exit 1
fi

VERSION=$(grep '"version"' "$MANIFEST_PATH" | sed 's/.*"version": "\([^"]*\)".*/\1/')

if [ -z "$VERSION" ]; then
    echo -e "${RED}Error: Could not extract version from manifest.json${NC}"
    exit 1
fi

echo -e "${GREEN}Manifest version: $VERSION${NC}"
validate_semver "$VERSION"

# Step 4: Create tag if it doesn't exist
TAG_NAME="v$VERSION"
TAG_CREATED=false

if git rev-parse "$TAG_NAME" >/dev/null 2>&1 || git ls-remote --tags origin "$TAG_NAME" 2>/dev/null | grep -q "$TAG_NAME"; then
    echo -e "${YELLOW}Tag $TAG_NAME already exists${NC}"
else
    echo -e "${GREEN}Creating annotated tag $TAG_NAME...${NC}"
    git tag -a "$TAG_NAME" -m "Release version $VERSION"
    TAG_CREATED=true
fi
echo ""

# Step 5: Push commits and tags
if [ "$COMMITTED" = true ] || [ "$TAG_CREATED" = true ]; then
    echo -e "${CYAN}Pushing to remote...${NC}"
    git push
    git push --tags
    echo -e "${GREEN}Successfully pushed to remote${NC}"
else
    echo -e "${YELLOW}Nothing to push (no new commits or tags)${NC}"
fi
echo ""

# Step 6: Sync to Home Assistant (optional)
if [ "$SKIP_SYNC" = false ]; then
    echo -e "${CYAN}Syncing to Home Assistant at $REMOTE_HOST...${NC}"
    
    # Uncomment and configure if using SSH/rsync:
    # rsync -avz --delete \
    #     --exclude='.git' \
    #     --exclude='__pycache__' \
    #     ./custom_components/export_monitor/ \
    #     root@$REMOTE_HOST:/config/custom_components/export_monitor/
    
    echo -e "${YELLOW}Sync method not configured. Edit script to enable SSH sync.${NC}"
else
    echo -e "${YELLOW}Skipping HA sync (--skip-sync)${NC}"
fi

echo ""
echo -e "${GREEN}✓ Done! Version $VERSION is published.${NC}\n"
echo -e "${CYAN}Semantic Versioning Guide:${NC}"
echo -e "${GRAY}  MAJOR (X.0.0) - Breaking changes to config or services${NC}"
echo -e "${GRAY}  MINOR (0.X.0) - New features, backward compatible${NC}"
echo -e "${GRAY}  PATCH (0.0.X) - Bug fixes, backward compatible${NC}"
