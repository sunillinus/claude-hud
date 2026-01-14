# Claude HUD

A heads-up display for monitoring multiple Claude Code sessions in iTerm2.

```
Window "Frontend"                    Window "Backend"
+-------------+-------------+       +-------------+-------------+
| [WORKING]   | [WAITING]   |       | [WORKING]   | [DONE]      |
| app-ui      | admin       |       | api         | workers     |
| Blue        | Amber       |       | Blue        | Green       |
+-------------+-------------+       +-------------+-------------+
```

## Features

- **Single window, multiple sessions**: Run 2-6 Claude Code sessions in a grid layout
- **Visual status indicators**: Color-coded backgrounds show state at a glance
  - Blue: Working
  - Amber: Waiting for input
  - Green: Done
  - Red: Error
  - Gray: Idle
- **Notifications**: Get alerted when any session needs input
- **Named windows**: Organize sessions by project or topic
- **CLI tools**: Easy commands for managing sessions

## Installation

```bash
git clone https://github.com/your-username/claude-hud.git
cd claude-hud
./install.sh
```

### Post-installation

1. **Enable iTerm2 Python API**:
   - Open iTerm2 Preferences (Cmd+,)
   - Go to General > Magic
   - Check "Enable Python API"

2. **Restart iTerm2** to activate the daemon

### Requirements

- macOS
- iTerm2 3.4+
- Python 3.8+
- Claude Code CLI

## Usage

### Create a multi-pane grid

```bash
# Create a named window with multiple sessions
claude-hud-grid --name "Frontend" ~/projects/app-ui ~/projects/admin ~/projects/website

# Create another window for backend work
claude-hud-grid --name "Backend" ~/projects/api ~/projects/workers
```

### Add sessions to existing windows

```bash
# Add to a specific named window
claude-hud --window "Frontend" ~/projects/mobile

# Add to current window (split current pane)
claude-hud --here ~/projects/new-app

# Create a new window
claude-hud --new-window ~/projects/standalone
```

### Remove sessions

Just close the pane normally:
- `exit` in the terminal, or
- `Cmd+W`

The daemon auto-detects closed sessions and stops tracking them.

### Check status

```bash
hud-status

# Output:
# Window: Frontend
#   [WORKING] app-ui
#   [WAITING] admin
#   [DONE] website
# Window: Backend
#   [WORKING] api
#   [IDLE] workers
```

```bash
# Filter by window
hud-status --window "Frontend"

# Output as JSON
hud-status --json
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd+D` | Split vertically (then run `claude` manually) |
| `Cmd+Shift+D` | Split horizontally |
| `Cmd+W` | Close current pane |
| `Cmd+[` / `Cmd+]` | Switch between panes |

## How It Works

1. **State Detection**: Monitors `~/.claude/debug/` logs to detect Claude Code session states
2. **Visual Feedback**: Uses iTerm2's Python API to update pane colors, titles, and badges
3. **Triggers**: iTerm2 triggers provide instant pattern matching for common states
4. **Notifications**: macOS notifications alert you when sessions need input

## File Locations

| Component | Location |
|-----------|----------|
| Dynamic Profile | `~/Library/Application Support/iTerm2/DynamicProfiles/ClaudeHUD.json` |
| Python Daemon | `~/Library/Application Support/iTerm2/Scripts/AutoLaunch/` |
| CLI Tools | `~/.local/bin/` |
| State Files | `~/.claude-hud/` |

## Uninstallation

```bash
./uninstall.sh

# Also remove state files
./uninstall.sh --remove-state
```

## Troubleshooting

### Sessions not being tracked

1. Ensure iTerm2 Python API is enabled (Preferences > General > Magic)
2. Restart iTerm2 after installation
3. Check that Claude Code is running in the session

### Colors not updating

The daemon polls every 0.5 seconds. If colors don't update:
1. Check that the daemon is running (Scripts > claude_hud_daemon.py)
2. Verify the Dynamic Profile is installed

### Notifications not appearing

1. Check macOS notification settings for iTerm2
2. Ensure "Do Not Disturb" is not enabled

## Contributing

Contributions welcome! Please open an issue or pull request.

## License

MIT License - see LICENSE file for details.
