# Claude HUD

A heads-up display for monitoring multiple Claude Code sessions in iTerm2.

## Features

- **Visual status indicators**: Background turns dark red when a session needs input
- **Project colors**: Each session gets a unique background color for easy identification
- **Multi-pane grid**: Run 2-8 Claude Code sessions in a grid layout
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
hud 8                    # Creates 8 empty panes (max)
```

### Pass arguments to claude

Use `--` to pass any arguments directly to claude:

```bash
hud ~/project -- -c                  # Continue previous session
hud ~/project -- --model opus        # Use opus model
hud ~/project -- -r                  # Open resume picker
hud ~/project -- --model sonnet -c   # Continue with sonnet
```

### All options

```
Usage: hud <project> [project2] ... [-- CLAUDE_ARGS]
       hud <number>                        # Create empty panes (1-8)

Options:
  --mono, -m           Use monochrome color scheme
  --                   Pass remaining args to claude
  --help, -h           Show this help
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
3. **Project Colors**: Each session in a grid gets a unique background color (navy, purple, teal, brown, forest, indigo, burgundy, steel blue)

## Grid Layout

The grid arranges panes as follows:

| Panes | Layout |
|-------|--------|
| 2 | `[1][2]` - 2 columns |
| 3 | `[1][2][3]` - 3 columns |
| 4 | `[1][2][3]` / `[4]` |
| 5 | `[1][2][3]` / `[4][5]` |
| 6 | `[1][2][3]` / `[4][5][6]` - 3x2 grid |
| 7 | `[1][2][3][7]` / `[4][5][6]` - 4th column full height |
| 8 | `[1][2][3][7]` / `[4][5][6][8]` - 4x2 grid |

## Project Structure

```
claude-hud/
├── bin/
│   ├── claude-hud          # Main CLI - launches grid, sets colors
│   ├── hud                  # Symlink to claude-hud
│   └── hud-status           # Show status of all sessions
├── hooks/
│   └── state-reporter.sh    # Claude Code hook - reports state changes
├── iterm2_daemon/           # iTerm2 Python daemon (single process)
│   ├── claude_hud_daemon.py # Entry point - runs in iTerm2 AutoLaunch
│   ├── session_manager.py   # Tracks sessions and colors
│   ├── state_detector.py    # Detects Claude state from screen
│   ├── socket_listener.py   # Receives hook notifications
│   └── window_manager.py    # Tracks named windows
├── iterm2_profiles/
│   └── ClaudeHUD.json       # iTerm2 Dynamic Profile
├── install.sh
└── uninstall.sh
```

## Installed Locations

| Component | Installed To |
|-----------|--------------|
| Dynamic Profile | `~/Library/Application Support/iTerm2/DynamicProfiles/ClaudeHUD.json` |
| Python Daemon | `~/Library/Application Support/iTerm2/Scripts/AutoLaunch/` |
| CLI Tools | `~/.local/bin/` |
| Hook Script | `~/.claude-hud/hooks/` |
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
