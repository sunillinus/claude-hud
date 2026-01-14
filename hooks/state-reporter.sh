#!/bin/bash
#
# Claude HUD - State Reporter Hook
#
# Sends state updates to the Claude HUD daemon via Unix domain socket.
# Called by Claude Code hooks on various events.
#
# This script must be fast and never block Claude Code.
# All errors are silently ignored - daemon unavailability should not affect Claude.
#

set -euo pipefail

SOCKET_PATH="$HOME/.claude-hud/daemon.sock"

# Read JSON input from stdin
input=$(cat)

# Extract fields using jq (available on macOS)
session_id=$(echo "$input" | jq -r '.session_id // empty' 2>/dev/null || echo "")
cwd=$(echo "$input" | jq -r '.cwd // empty' 2>/dev/null || echo "")
hook_event=$(echo "$input" | jq -r '.hook_event_name // empty' 2>/dev/null || echo "")

# Skip if no session_id
if [ -z "$session_id" ]; then
    exit 0
fi

# Map hook event to state
case "$hook_event" in
    "UserPromptSubmit")
        state="working"
        ;;
    "PreToolUse")
        state="working"
        ;;
    "Stop")
        state="idle"
        ;;
    "Notification")
        state="waiting"
        ;;
    "SessionStart")
        state="idle"
        ;;
    *)
        # Unknown event, still send for registration
        state="idle"
        ;;
esac

# Build message JSON
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
message=$(jq -n \
    --arg session_id "$session_id" \
    --arg cwd "$cwd" \
    --arg state "$state" \
    --arg hook_event "$hook_event" \
    --arg timestamp "$timestamp" \
    '{
        type: "state_update",
        session_id: $session_id,
        cwd: $cwd,
        state: $state,
        hook_event: $hook_event,
        timestamp: $timestamp
    }' 2>/dev/null || echo "{}")

# Send to socket using Python (more reliable than nc on macOS)
# Non-blocking with 100ms timeout, fail silently
if [ -S "$SOCKET_PATH" ]; then
    python3 << PYEOF 2>/dev/null || true
import socket
import sys

sock_path = "$SOCKET_PATH"
message = '''$message'''

try:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.settimeout(0.1)
    sock.sendto(message.encode('utf-8'), sock_path)
    sock.close()
except Exception:
    pass
PYEOF
fi

# Always exit success - hooks should never block Claude
exit 0
