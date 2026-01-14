# Claude HUD

A heads-up display for monitoring multiple Claude Code sessions in iTerm2.

## Features

- **Visual status indicators**: Background turns dark red when a session needs input
- **Project colors**: Each session gets a unique background color for easy identification
- **Multi-pane grid**: Run 2-6 Claude Code sessions in a grid layout
- **Simple command**: Just `hud` to start sessions

## Installation

```bash
git clone https://github.com/sunillinus/claude-hud.git
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

### Single session

```bash
hud ~/myproject
```

### Multi-pane grid (auto-detects when given multiple paths)

```bash
hud ~/api ~/web ~/db
```

### Empty panes (create grid without running Claude)

```bash
hud 4                    # Creates 4 empty panes
hud --name "Work" 3      # Named window with 3 empty panes
```

### Named window

```bash
hud --name "Work" ~/api ~/web ~/db
```

### Split current pane

```bash
hud --here ~/project
```

### Resume previous session

```bash
hud --continue ~/myproject
```

### All options

```
Usage: hud [OPTIONS] <project> [project2] ...
       hud <number>                        # Create empty panes (1-6)

Options:
  --name, -n <name>    Name the window
  --here, -h           Split current pane (single project only)
  --continue, -c       Resume previous Claude session
  --help               Show this help
```

### Check status

```bash
hud-status

# Filter by window
hud-status --window "Work"

# Output as JSON
hud-status --json
```

### Remove sessions

Just close the pane normally:
- `exit` in the terminal, or
- `Cmd+W`

The daemon auto-detects closed sessions and stops tracking them.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd+D` | Split vertically |
| `Cmd+Shift+D` | Split horizontally |
| `Cmd+W` | Close current pane |
| `Cmd+[` / `Cmd+]` | Switch between panes |

## How It Works

1. **State Detection**: Claude Code hooks report session state changes
2. **Visual Feedback**: Background turns dark red when session needs input, restores to project color otherwise
3. **Project Colors**: Each session in a grid gets a unique background color (navy, purple, teal, brown, forest, indigo)

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

## License

MIT License
