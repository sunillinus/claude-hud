#!/bin/bash
#
# Claude HUD - Uninstaller
#
# Removes Claude HUD components:
# - Dynamic Profile for iTerm2
# - Python daemon
# - CLI tools
# - State files (optional)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════╗"
echo "║        Claude HUD Uninstaller         ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}"

# Parse arguments
REMOVE_STATE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --remove-state)
            REMOVE_STATE=true
            shift
            ;;
        --help)
            echo "Usage: uninstall.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --remove-state  Also remove state files (~/.claude-hud)"
            echo "  --help          Show this help"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

# Paths
ITERM_PROFILES_DIR="$HOME/Library/Application Support/iTerm2/DynamicProfiles"
ITERM_SCRIPTS_DIR="$HOME/Library/Application Support/iTerm2/Scripts/AutoLaunch"
BIN_DIR="$HOME/.local/bin"
STATE_DIR="$HOME/.claude-hud"

echo -e "${YELLOW}Removing Claude HUD components...${NC}"
echo ""

# Remove Dynamic Profile
if [ -f "$ITERM_PROFILES_DIR/ClaudeHUD.json" ]; then
    rm "$ITERM_PROFILES_DIR/ClaudeHUD.json"
    echo -e "  ${GREEN}✓${NC} Removed Dynamic Profile"
else
    echo -e "  ${YELLOW}-${NC} Dynamic Profile not found (already removed?)"
fi

# Remove Python scripts
PYTHON_SCRIPTS=(
    "claude_hud_daemon.py"
    "state_detector.py"
    "session_manager.py"
    "socket_listener.py"
    "window_manager.py"
)

for script in "${PYTHON_SCRIPTS[@]}"; do
    if [ -f "$ITERM_SCRIPTS_DIR/$script" ]; then
        rm "$ITERM_SCRIPTS_DIR/$script"
        echo -e "  ${GREEN}✓${NC} Removed $script"
    fi
done

# Remove CLI tools
CLI_TOOLS=("claude-hud" "hud" "hud-status")

for tool in "${CLI_TOOLS[@]}"; do
    if [ -f "$BIN_DIR/$tool" ]; then
        rm "$BIN_DIR/$tool"
        echo -e "  ${GREEN}✓${NC} Removed $tool"
    fi
done

# Remove state files if requested
if [ "$REMOVE_STATE" = true ]; then
    if [ -d "$STATE_DIR" ]; then
        rm -rf "$STATE_DIR"
        echo -e "  ${GREEN}✓${NC} Removed state directory"
    fi
else
    echo ""
    echo -e "${YELLOW}Note:${NC} State files preserved at ~/.claude-hud"
    echo "  Run with --remove-state to also remove state files"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${GREEN}Uninstallation complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""
echo "Restart iTerm2 to complete the removal."
