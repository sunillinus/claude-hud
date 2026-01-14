#!/usr/bin/env python3
"""
Claude HUD - iTerm2 Python Daemon

Main monitoring daemon that runs inside iTerm2's Python environment.
Monitors Claude Code sessions and provides visual feedback.

This script should be placed in:
~/Library/Application Support/iTerm2/Scripts/AutoLaunch/
"""

import sys
# Prevent Python from creating __pycache__ in iTerm2's Scripts folder
sys.dont_write_bytecode = True

import asyncio
import subprocess
import os
from typing import Optional

# Add scripts directory to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

try:
    import iterm2
except ImportError:
    print("Error: iterm2 module not found.")
    print("Install with: pip3 install iterm2")
    sys.exit(1)

from state_detector import ClaudeState, ClaudeStateDetector
from session_manager import SessionManager, TrackedSession
from window_manager import WindowManager
from socket_listener import SocketListener, SessionMapper


# Project color palette - distinct hues for up to 6 projects (background)
PROJECT_COLORS = [
    "1e3a5f",  # Navy blue
    "4a1942",  # Purple
    "0d4f4f",  # Teal
    "5c3d2e",  # Brown
    "2d4a3e",  # Forest green
    "4a3f5c",  # Indigo
]

# Badge colors by state (RGB 0-1 scale)
BADGE_COLORS = {
    ClaudeState.IDLE: (0.42, 0.45, 0.50, 0.8),          # Gray #6b7280
    ClaudeState.WORKING: (0.23, 0.51, 0.96, 0.8),       # Blue #3b82f6
    ClaudeState.WAITING_INPUT: (0.98, 0.75, 0.14, 0.9), # Amber #fbbf24
    ClaudeState.DONE: (0.13, 0.77, 0.37, 0.8),          # Green #22c55e
    ClaudeState.ERROR: (0.94, 0.27, 0.27, 0.8),         # Red #ef4444
}

ICONS = {
    ClaudeState.WORKING: "\u2699",       # Gear
    ClaudeState.WAITING_INPUT: "\u23F3", # Hourglass
    ClaudeState.DONE: "\u2713",          # Check
    ClaudeState.ERROR: "\u2717",         # X
    ClaudeState.IDLE: "\u25CB",          # Circle
}


class ClaudeHUDDaemon:
    """Main daemon for monitoring Claude Code sessions."""

    POLL_INTERVAL = 0.5  # seconds
    CLAUDE_PROCESS_NAME = "claude"

    def __init__(self, connection: iterm2.Connection):
        """
        Initialize the daemon.

        Args:
            connection: The iTerm2 connection.
        """
        self.connection = connection
        self.app = None
        self.session_manager = SessionManager()
        self.window_manager = WindowManager()
        self._detectors: dict = {}
        self._monitored_sessions: set = set()

        # Hook-based state detection
        self.session_mapper = SessionMapper()
        self.socket_listener = SocketListener(
            session_mapper=self.session_mapper,
            on_state_update=self._handle_hook_state_update
        )

    async def start(self) -> None:
        """Start the daemon."""
        self.app = await iterm2.async_get_app(self.connection)

        # Scan all existing sessions first
        await self._scan_existing_sessions()

        # Start monitoring tasks (including socket listener for hooks)
        await asyncio.gather(
            self._monitor_sessions(),
            self._watch_for_new_sessions(),
            self._cleanup_closed_sessions(),
            self.socket_listener.start(),  # Hook-based state updates
        )

    async def _scan_existing_sessions(self) -> None:
        """Scan all existing sessions and track any running Claude."""
        print("Scanning existing sessions...")
        for window in self.app.windows:
            for tab in window.tabs:
                for session in tab.sessions:
                    await self._check_and_track_session(session.session_id)

    async def _monitor_sessions(self) -> None:
        """Main monitoring loop for tracked sessions."""
        while True:
            try:
                for session in self.session_manager.get_all_sessions():
                    await self._update_session_state(session)
                    await self._check_notification(session)
            except Exception as e:
                print(f"Error in monitor loop: {e}")

            await asyncio.sleep(self.POLL_INTERVAL)

    async def _watch_for_new_sessions(self) -> None:
        """Watch for new iTerm2 sessions that might be running Claude."""
        async with iterm2.NewSessionMonitor(self.connection) as monitor:
            while True:
                session_id = await monitor.async_get()
                await self._check_and_track_session(session_id)

    async def _cleanup_closed_sessions(self) -> None:
        """Periodically clean up sessions that have been closed."""
        while True:
            try:
                await self._cleanup_sessions()
            except Exception as e:
                print(f"Error in cleanup: {e}")

            await asyncio.sleep(5)  # Check every 5 seconds

    async def _check_and_track_session(self, session_id: str) -> None:
        """
        Check if a session is running Claude and track it if so.

        Args:
            session_id: The iTerm2 session ID.
        """
        if session_id in self._monitored_sessions:
            return

        session = self.app.get_session_by_id(session_id)
        if not session:
            return

        # Wait a bit for the process to start
        await asyncio.sleep(1)

        # Check if this session is running Claude
        if await self._is_claude_session(session):
            await self._start_tracking_session(session)

    async def _is_claude_session(self, session: iterm2.Session) -> bool:
        """
        Check if a session is running Claude Code.

        Args:
            session: The iTerm2 session.

        Returns:
            True if the session appears to be running Claude Code.
        """
        try:
            # Get the session's variables
            name = await session.async_get_variable("jobName")
            if name and self.CLAUDE_PROCESS_NAME in name.lower():
                return True

            # Check command
            command = await session.async_get_variable("commandLine")
            if command and self.CLAUDE_PROCESS_NAME in command.lower():
                return True

            # Check screen contents for Claude indicators
            contents = await session.async_get_screen_contents()
            if contents:
                text = ""
                for line_num in range(contents.number_of_lines):
                    line = contents.line(line_num)
                    text += line.string + "\n"

                # Look for Claude Code indicators
                text_lower = text.lower()
                if ("claude" in text_lower or
                    "❯" in text or
                    "> " in text or
                    "ctrl+c to interrupt" in text_lower or
                    "for shortcuts" in text_lower):
                    return True

        except Exception as e:
            print(f"Error checking if Claude session: {e}")
            pass

        return False

    async def _start_tracking_session(self, session: iterm2.Session) -> None:
        """
        Start tracking a Claude Code session.

        Args:
            session: The iTerm2 session.
        """
        session_id = session.session_id
        if session_id in self._monitored_sessions:
            return

        self._monitored_sessions.add(session_id)

        # Get project info from working directory
        try:
            cwd = await session.async_get_variable("path")
            project_path = cwd or "Unknown"
        except Exception:
            project_path = "Unknown"

        # Get window name if available
        window = session.tab.window
        window_name = None
        if window:
            tracked_window = self.window_manager.get_window_by_iterm_id(window.window_id)
            if tracked_window:
                window_name = tracked_window.name

        # Track the session
        tracked = self.session_manager.track_session(
            iterm_session_id=session_id,
            project_path=project_path,
            window_name=window_name,
        )

        # Query and store the original background color (set by grid script)
        original_color = self._get_session_background_color(session_id)
        if original_color:
            tracked.original_bg_color = original_color
            self.session_manager._save_state()
            print(f"Stored original bg color for {tracked.project_name}: {original_color}")

        # Register with session mapper for hook correlation
        self.session_mapper.register_iterm_session(session_id, project_path)

        # Create a detector for this session (fallback)
        self._detectors[session_id] = ClaudeStateDetector()

        print(f"Started tracking: {tracked.project_name} ({session_id})")

    async def _handle_hook_state_update(
        self,
        iterm_session_id: str,
        state: ClaudeState,
        cwd: str
    ) -> None:
        """
        Handle state update from Claude Code hook via socket.
        This is the primary state update path - more reliable than screen scraping.

        Args:
            iterm_session_id: The iTerm2 session ID.
            state: The detected state from hook.
            cwd: The working directory.
        """
        session = self.app.get_session_by_id(iterm_session_id)
        if not session:
            return

        tracked = self.session_manager.get_session(iterm_session_id)
        if not tracked:
            return

        # Check if state changed
        if state != tracked.current_state:
            print(f"[Hook] State change: {tracked.project_name} {tracked.current_state} -> {state}")
            self.session_manager.update_session_state(iterm_session_id, state)

            # Update visual feedback (amber for WAITING_INPUT, restore original otherwise)
            await self._update_visual_feedback(
                session,
                state,
                tracked.project_name,
                tracked.original_bg_color,
            )

            # Check notification for WAITING_INPUT
            if state == ClaudeState.WAITING_INPUT:
                await self._send_notification(tracked)

    async def _update_session_state(self, tracked: TrackedSession) -> None:
        """
        Update the state of a tracked session.

        Args:
            tracked: The tracked session.
        """
        session = self.app.get_session_by_id(tracked.iterm_session_id)
        if not session:
            return

        # Detect state from screen contents
        state = await self._detect_state_from_screen(session)

        # Check if state changed
        if state != tracked.current_state:
            print(f"State change: {tracked.project_name} {tracked.current_state} -> {state}")
            self.session_manager.update_session_state(
                tracked.iterm_session_id,
                state,
            )

            # Update visual feedback (amber for WAITING_INPUT, restore original otherwise)
            await self._update_visual_feedback(
                session,
                state,
                tracked.project_name,
                tracked.original_bg_color,
            )

    async def _detect_state_from_screen(self, session: iterm2.Session) -> ClaudeState:
        """
        Detect Claude state by analyzing screen contents.

        Args:
            session: The iTerm2 session.

        Returns:
            The detected ClaudeState.
        """
        try:
            contents = await session.async_get_screen_contents()
            if not contents:
                return ClaudeState.IDLE

            # Get last 30 lines of screen content
            lines = []
            for line_num in range(max(0, contents.number_of_lines - 30), contents.number_of_lines):
                line = contents.line(line_num)
                lines.append(line.string)

            text = '\n'.join(lines).lower()

            # Check for WAITING_INPUT patterns (highest priority)
            waiting_patterns = [
                'do you want to proceed',
                'yes, and always allow',
                '? allow',
                'esc to cancel',
                'tab to add additional',
                '1. yes',
                '2. yes, and',
                '3. no',
            ]
            for pattern in waiting_patterns:
                if pattern in text:
                    return ClaudeState.WAITING_INPUT

            # Check for WORKING patterns
            working_patterns = [
                'ctrl+c to interrupt',  # Streaming indicator
                'tokens)',              # Token counter during streaming
                'running',
                '● ',                   # Activity indicator
                'waiting…',             # Waiting for async op
                'explore(',             # Tool calls
                'task(',
                'bash(',
                'read(',
                'write(',
                'edit(',
                'glob(',
                'grep(',
                'webfetch(',
                'websearch(',
                'let me',
                'i\'ll ',
                'i will',
                '+50 more tool',        # Tool expansion indicator
                'ctrl+o to expand',
            ]
            for pattern in working_patterns:
                if pattern in text:
                    return ClaudeState.WORKING

            # Check for ERROR patterns
            error_patterns = [
                '[error]',
                'error:',
                'failed',
                'exception',
            ]
            for pattern in error_patterns:
                if pattern in text:
                    return ClaudeState.ERROR

            # Check for DONE patterns - just completed a response
            done_patterns = [
                '✓',
                '✔',
                'completed',
                'done!',
            ]
            for pattern in done_patterns:
                if pattern in text:
                    # Only if no working indicators
                    has_working = any(p in text for p in ['running', '● '])
                    if not has_working:
                        return ClaudeState.DONE

            # Default to IDLE if at prompt
            if '❯' in text or '> ' in text:
                return ClaudeState.IDLE

            return ClaudeState.IDLE

        except Exception as e:
            print(f"Error detecting state from screen: {e}")
            return ClaudeState.IDLE

    def _run_applescript(self, script: str) -> bool:
        """Run AppleScript and return success status."""
        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=5
            )
            return True
        except Exception as e:
            print(f"AppleScript error: {e}")
            return False

    def _hex_to_applescript_rgb(self, hex_color: str) -> str:
        """Convert hex color to AppleScript RGB format {r, g, b}."""
        r = int(hex_color[0:2], 16) * 257  # Scale 0-255 to 0-65535
        g = int(hex_color[2:4], 16) * 257
        b = int(hex_color[4:6], 16) * 257
        return f"{{{r}, {g}, {b}}}"

    def _get_session_background_color(self, session_id: str) -> Optional[str]:
        """Query the current background color of a session via AppleScript.

        Returns the color as AppleScript RGB format "{r, g, b}" or None if failed.
        """
        script = f'''
        tell application "iTerm2"
            repeat with w in windows
                repeat with t in tabs of w
                    repeat with s in sessions of t
                        if unique ID of s is "{session_id}" then
                            set bgColor to background color of s
                            return "{{" & (item 1 of bgColor) & ", " & (item 2 of bgColor) & ", " & (item 3 of bgColor) & "}}"
                        end if
                    end repeat
                end repeat
            end repeat
        end tell
        '''
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception as e:
            print(f"Error getting background color: {e}")
        return None

    async def _update_visual_feedback(
        self,
        session: iterm2.Session,
        state: ClaudeState,
        project_name: str,
        original_bg_color: Optional[str] = None,
    ) -> None:
        """
        Update the visual feedback for a session.

        Args:
            session: The iTerm2 session.
            state: The current state.
            project_name: The project name.
            original_bg_color: The original background color to restore to (AppleScript RGB format).
        """
        try:
            session_id = session.session_id

            # Background color changes based on state:
            # - WAITING_INPUT: Dark red to grab attention
            # - Other states: Restore to original project color
            if state == ClaudeState.WAITING_INPUT:
                # Dark red background - attention-grabbing but still readable
                bg_rgb = "{35000, 8000, 8000}"  # Dark red
                print(f"ATTENTION: {project_name} needs input!")
            elif original_bg_color:
                # Restore to original project color
                bg_rgb = original_bg_color
            else:
                # Fallback: don't change background if we don't know original
                return

            bg_script = f'''
            tell application "iTerm2"
                repeat with w in windows
                    repeat with t in tabs of w
                        repeat with s in sessions of t
                            if unique ID of s is "{session_id}" then
                                set background color of s to {bg_rgb}
                            end if
                        end repeat
                    end repeat
                end repeat
            end tell
            '''
            self._run_applescript(bg_script)

        except Exception as e:
            print(f"Error updating visual feedback: {e}")

    async def _check_notification(self, tracked: TrackedSession) -> None:
        """
        Check if a session needs a notification and send it.

        Args:
            tracked: The tracked session.
        """
        # Check if this session needs notification
        sessions_needing = self.session_manager.get_sessions_needing_notification()

        for session in sessions_needing:
            if session.iterm_session_id == tracked.iterm_session_id:
                await self._send_notification(session)
                self.session_manager.mark_notified(session.iterm_session_id)

    async def _send_notification(self, tracked: TrackedSession) -> None:
        """
        Send a macOS notification for a session.

        Args:
            tracked: The tracked session needing notification.
        """
        try:
            # Send macOS system notification
            subprocess.run([
                'osascript', '-e',
                f'display notification "{tracked.project_name} needs input" '
                f'with title "Claude HUD" sound name "Glass"'
            ], capture_output=True)

        except Exception as e:
            print(f"Error sending notification: {e}")

    async def _cleanup_sessions(self) -> None:
        """Clean up sessions that have been closed."""
        # Get all current iTerm2 session IDs
        current_session_ids = set()
        for window in self.app.windows:
            for tab in window.tabs:
                for session in tab.sessions:
                    current_session_ids.add(session.session_id)

        # Find and remove closed sessions
        for session_id in list(self._monitored_sessions):
            if session_id not in current_session_ids:
                self._monitored_sessions.discard(session_id)
                self.session_manager.untrack_session(session_id)
                if session_id in self._detectors:
                    del self._detectors[session_id]
                print(f"Cleaned up closed session: {session_id}")

        # Cleanup stale windows
        current_window_ids = [w.window_id for w in self.app.windows]
        removed = self.window_manager.cleanup_stale_windows(current_window_ids)
        for name in removed:
            print(f"Cleaned up stale window: {name}")


async def main(connection: iterm2.Connection) -> None:
    """
    Main entry point for the iTerm2 Python script.

    Args:
        connection: The iTerm2 connection.
    """
    print("Claude HUD daemon starting...")

    daemon = ClaudeHUDDaemon(connection)

    try:
        await daemon.start()
    except Exception as e:
        print(f"Daemon error: {e}")
        raise


# Entry point for iTerm2
if __name__ == "__main__":
    try:
        iterm2.run_forever(main)
    except Exception as e:
        print(f"Failed to start Claude HUD daemon: {e}")
        sys.exit(1)
