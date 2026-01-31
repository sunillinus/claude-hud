#!/bin/bash
#
# Claude HUD - Remote Installer
#
# One-liner installation:
#   curl -sSL https://raw.githubusercontent.com/sunillinus/claude-hud/main/install-remote.sh | bash
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

REPO_URL="https://github.com/sunillinus/claude-hud.git"
TEMP_DIR=$(mktemp -d)

cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════╗"
echo "║     Claude HUD Remote Installer       ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}"

# Check for git
if ! command -v git &> /dev/null; then
    echo -e "${RED}Error: git is required but not installed.${NC}"
    exit 1
fi

# Clone repo
echo -e "${YELLOW}Downloading Claude HUD...${NC}"
git clone --depth 1 "$REPO_URL" "$TEMP_DIR" 2>/dev/null
echo -e "  ${GREEN}✓${NC} Downloaded"

# Run installer
echo ""
cd "$TEMP_DIR"
bash ./install.sh

echo ""
echo -e "${GREEN}Cleanup complete. Claude HUD is installed!${NC}"
