#!/bin/bash
#
# Claude HUD - Installer
#
# Installs Claude HUD components:
# - Dynamic Profile for iTerm2
# - Python daemon for session monitoring
# - CLI tools (claude-hud, claude-hud-grid, hud-status)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════╗"
echo "║         Claude HUD Installer          ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Python 3 found"

# Check iTerm2
if [ ! -d "/Applications/iTerm.app" ]; then
    echo -e "${RED}Error: iTerm2 is required but not found.${NC}"
    echo "  Install from: https://iterm2.com/"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} iTerm2 found"

# Check Claude Code
if ! command -v claude &> /dev/null; then
    echo -e "${YELLOW}Warning: Claude Code CLI not found in PATH.${NC}"
    echo "  Claude HUD will still install, but you'll need Claude Code to use it."
fi

echo ""

# Install iterm2 Python package
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip3 install --user iterm2 2>/dev/null || {
    echo -e "${YELLOW}Note: Could not install iterm2 package automatically.${NC}"
    echo "  You may need to run: pip3 install iterm2"
}
echo -e "  ${GREEN}✓${NC} Python dependencies ready"

echo ""

# Create directories
echo -e "${YELLOW}Creating directories...${NC}"

ITERM_PROFILES_DIR="$HOME/Library/Application Support/iTerm2/DynamicProfiles"
ITERM_SCRIPTS_DIR="$HOME/Library/Application Support/iTerm2/Scripts/AutoLaunch"
BIN_DIR="$HOME/.local/bin"
STATE_DIR="$HOME/.claude-hud"

mkdir -p "$ITERM_PROFILES_DIR"
mkdir -p "$ITERM_SCRIPTS_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$STATE_DIR"

echo -e "  ${GREEN}✓${NC} Directories created"

echo ""

# Copy Dynamic Profile
echo -e "${YELLOW}Installing iTerm2 Dynamic Profile...${NC}"
cp "$SCRIPT_DIR/profiles/ClaudeHUD.json" "$ITERM_PROFILES_DIR/"
echo -e "  ${GREEN}✓${NC} Dynamic Profile installed"

# Copy Python daemon
echo -e "${YELLOW}Installing Python daemon...${NC}"
cp "$SCRIPT_DIR/scripts/"*.py "$ITERM_SCRIPTS_DIR/"
echo -e "  ${GREEN}✓${NC} Python daemon installed"

# Copy and make CLI tools executable
echo -e "${YELLOW}Installing CLI tools...${NC}"
cp "$SCRIPT_DIR/bin/"* "$BIN_DIR/"
chmod +x "$BIN_DIR/claude-hud"
chmod +x "$BIN_DIR/claude-hud-grid"
chmod +x "$BIN_DIR/hud-status"
echo -e "  ${GREEN}✓${NC} CLI tools installed"

# Install hook script for state detection
echo -e "${YELLOW}Installing Claude Code hooks...${NC}"
HOOKS_DIR="$STATE_DIR/hooks"
mkdir -p "$HOOKS_DIR"
cp "$SCRIPT_DIR/hooks/state-reporter.sh" "$HOOKS_DIR/"
chmod +x "$HOOKS_DIR/state-reporter.sh"
echo -e "  ${GREEN}✓${NC} Hook script installed"

# Configure Claude Code hooks in settings.json
echo -e "${YELLOW}Configuring Claude Code hooks...${NC}"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"

# Create backup if exists
if [ -f "$CLAUDE_SETTINGS" ]; then
    cp "$CLAUDE_SETTINGS" "$CLAUDE_SETTINGS.backup.$(date +%s)"
fi

# Ensure .claude directory exists
mkdir -p "$HOME/.claude"

# Merge hooks into settings.json using Python
python3 << 'PYEOF'
import json
from pathlib import Path

settings_path = Path.home() / ".claude" / "settings.json"
settings = {}

# Load existing settings
if settings_path.exists():
    try:
        with open(settings_path) as f:
            settings = json.load(f)
    except (json.JSONDecodeError, IOError):
        settings = {}

# Define HUD hooks
hook_command = "bash $HOME/.claude-hud/hooks/state-reporter.sh"
hud_hook = {"matcher": "*", "hooks": [{"type": "command", "command": hook_command, "timeout": 1}]}

hook_events = ["UserPromptSubmit", "PreToolUse", "Stop", "Notification", "SessionStart"]

# Ensure hooks section exists
if "hooks" not in settings:
    settings["hooks"] = {}

# Add HUD hooks for each event (avoid duplicates)
for event in hook_events:
    if event not in settings["hooks"]:
        settings["hooks"][event] = []

    # Check if HUD hook already exists
    existing_commands = []
    for h in settings["hooks"][event]:
        if isinstance(h, dict) and "hooks" in h:
            for hh in h["hooks"]:
                if isinstance(hh, dict) and "command" in hh:
                    existing_commands.append(hh["command"])

    if hook_command not in existing_commands:
        settings["hooks"][event].append(hud_hook)

# Save updated settings
with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)

print("Hooks configured successfully")
PYEOF

echo -e "  ${GREEN}✓${NC} Claude Code hooks configured"

echo ""

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo -e "${YELLOW}Adding ~/.local/bin to PATH...${NC}"

    # Detect shell and add to appropriate rc file
    SHELL_NAME=$(basename "$SHELL")
    case "$SHELL_NAME" in
        zsh)
            RC_FILE="$HOME/.zshrc"
            ;;
        bash)
            RC_FILE="$HOME/.bashrc"
            ;;
        *)
            RC_FILE="$HOME/.profile"
            ;;
    esac

    # Add to rc file if not already there
    if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$RC_FILE" 2>/dev/null; then
        echo '' >> "$RC_FILE"
        echo '# Claude HUD' >> "$RC_FILE"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$RC_FILE"
        echo -e "  ${GREEN}✓${NC} Added to $RC_FILE"
    fi

    echo -e "${YELLOW}Note: Run 'source $RC_FILE' or open a new terminal for PATH changes.${NC}"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${GREEN}Installation complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Post-installation steps:${NC}"
echo ""
echo "1. Enable iTerm2 Python API:"
echo "   - Open iTerm2 Preferences (Cmd+,)"
echo "   - Go to General > Magic"
echo "   - Check 'Enable Python API'"
echo ""
echo "2. Restart iTerm2 to activate the daemon"
echo ""
echo -e "${YELLOW}Quick start:${NC}"
echo ""
echo "  # Create a multi-pane grid"
echo "  claude-hud-grid --name \"MyProject\" ~/project1 ~/project2 ~/project3"
echo ""
echo "  # Add a session to existing window"
echo "  claude-hud --window \"MyProject\" ~/project4"
echo ""
echo "  # Check status"
echo "  hud-status"
echo ""
echo "For more info, see: https://github.com/your-username/claude-hud"
