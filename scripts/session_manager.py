#!/usr/bin/env python3
"""
Claude HUD - Session Manager

Tracks multiple Claude Code sessions across iTerm2 windows and panes.
Manages session state, notifications, and provides aggregated status.
"""

import sys
sys.dont_write_bytecode = True

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum

from state_detector import ClaudeState, ClaudeStateDetector, StateInfo


@dataclass
class TrackedSession:
    """Represents a tracked Claude Code session."""
    session_id: str
    iterm_session_id: str
    window_name: Optional[str]
    project_name: str
    project_path: str
    color_index: int = 0  # Index into PROJECT_COLORS palette
    original_bg_color: Optional[str] = None  # Original background color as AppleScript RGB "{r, g, b}"
    current_state: ClaudeState = ClaudeState.IDLE
    current_task: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.now)
    last_notification: Optional[datetime] = None
    notification_cooldown_until: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'session_id': self.session_id,
            'iterm_session_id': self.iterm_session_id,
            'window_name': self.window_name,
            'project_name': self.project_name,
            'project_path': self.project_path,
            'color_index': self.color_index,
            'original_bg_color': self.original_bg_color,
            'current_state': self.current_state.value,
            'current_task': self.current_task,
            'last_updated': self.last_updated.isoformat(),
            'last_notification': self.last_notification.isoformat() if self.last_notification else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'TrackedSession':
        """Create from dictionary."""
        return cls(
            session_id=data['session_id'],
            iterm_session_id=data['iterm_session_id'],
            window_name=data.get('window_name'),
            project_name=data['project_name'],
            project_path=data['project_path'],
            color_index=data.get('color_index', 0),
            original_bg_color=data.get('original_bg_color'),
            current_state=ClaudeState(data.get('current_state', 'idle')),
            current_task=data.get('current_task'),
            last_updated=datetime.fromisoformat(data['last_updated']) if data.get('last_updated') else datetime.now(),
            last_notification=datetime.fromisoformat(data['last_notification']) if data.get('last_notification') else None,
        )


class SessionManager:
    """
    Manages tracking of multiple Claude Code sessions.

    Provides methods to:
    - Track/untrack sessions
    - Update session states
    - Get aggregated status
    - Determine which sessions need notifications
    """

    STATE_FILE = Path.home() / ".claude-hud" / "state.json"
    NOTIFICATION_COOLDOWN = timedelta(seconds=30)
    NOTIFICATION_REMINDER = timedelta(minutes=5)

    def __init__(self):
        """Initialize the session manager."""
        self.sessions: Dict[str, TrackedSession] = {}
        self._detectors: Dict[str, ClaudeStateDetector] = {}
        self._load_state()

    def _ensure_state_dir(self) -> None:
        """Ensure the state directory exists."""
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> None:
        """Load persisted state from disk."""
        if self.STATE_FILE.exists():
            try:
                with open(self.STATE_FILE, 'r') as f:
                    data = json.load(f)
                    for session_data in data.get('sessions', []):
                        session = TrackedSession.from_dict(session_data)
                        self.sessions[session.iterm_session_id] = session
            except (json.JSONDecodeError, IOError):
                pass

    def _save_state(self) -> None:
        """Persist state to disk."""
        self._ensure_state_dir()
        data = {
            'sessions': [s.to_dict() for s in self.sessions.values()],
            'last_updated': datetime.now().isoformat(),
        }
        try:
            with open(self.STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass

    def _get_next_color_index(self) -> int:
        """
        Get the next available color index for a new session.

        Uses round-robin assignment from the palette.
        """
        if not self.sessions:
            return 0
        # Find the highest color_index currently in use and wrap around
        used_indices = {s.color_index for s in self.sessions.values()}
        # Try to find an unused index first (up to palette size of 6)
        for i in range(6):
            if i not in used_indices:
                return i
        # All indices used, just use next in sequence
        max_index = max(s.color_index for s in self.sessions.values())
        return (max_index + 1) % 6

    def track_session(
        self,
        iterm_session_id: str,
        project_path: str,
        window_name: Optional[str] = None,
        claude_session_id: Optional[str] = None,
    ) -> TrackedSession:
        """
        Start tracking a new Claude Code session.

        Args:
            iterm_session_id: The iTerm2 session ID.
            project_path: Path to the project directory.
            window_name: Optional name of the containing window.
            claude_session_id: Optional Claude Code session ID.

        Returns:
            The newly tracked session.
        """
        project_name = Path(project_path).name
        color_index = self._get_next_color_index()

        session = TrackedSession(
            session_id=claude_session_id or "",
            iterm_session_id=iterm_session_id,
            window_name=window_name,
            project_name=project_name,
            project_path=project_path,
            color_index=color_index,
        )

        self.sessions[iterm_session_id] = session
        self._save_state()

        return session

    def untrack_session(self, iterm_session_id: str) -> bool:
        """
        Stop tracking a session.

        Args:
            iterm_session_id: The iTerm2 session ID to untrack.

        Returns:
            True if session was found and removed, False otherwise.
        """
        if iterm_session_id in self.sessions:
            del self.sessions[iterm_session_id]
            if iterm_session_id in self._detectors:
                del self._detectors[iterm_session_id]
            self._save_state()
            return True
        return False

    def update_session_state(
        self,
        iterm_session_id: str,
        state: ClaudeState,
        task: Optional[str] = None,
    ) -> bool:
        """
        Update the state of a tracked session.

        Args:
            iterm_session_id: The iTerm2 session ID.
            state: The new state.
            task: Optional current task description.

        Returns:
            True if state changed, False otherwise.
        """
        if iterm_session_id not in self.sessions:
            return False

        session = self.sessions[iterm_session_id]
        state_changed = session.current_state != state

        session.current_state = state
        session.current_task = task
        session.last_updated = datetime.now()

        if state_changed:
            self._save_state()

        return state_changed

    def update_claude_session_id(
        self,
        iterm_session_id: str,
        claude_session_id: str,
    ) -> None:
        """
        Update the Claude session ID for a tracked session.

        Args:
            iterm_session_id: The iTerm2 session ID.
            claude_session_id: The Claude Code session ID.
        """
        if iterm_session_id in self.sessions:
            self.sessions[iterm_session_id].session_id = claude_session_id
            self._save_state()

    def get_session(self, iterm_session_id: str) -> Optional[TrackedSession]:
        """
        Get a tracked session by iTerm2 session ID.

        Args:
            iterm_session_id: The iTerm2 session ID.

        Returns:
            The tracked session, or None if not found.
        """
        return self.sessions.get(iterm_session_id)

    def get_sessions_by_window(self, window_name: str) -> List[TrackedSession]:
        """
        Get all sessions in a specific window.

        Args:
            window_name: The name of the window.

        Returns:
            List of sessions in that window.
        """
        return [
            s for s in self.sessions.values()
            if s.window_name == window_name
        ]

    def get_all_sessions(self) -> List[TrackedSession]:
        """
        Get all tracked sessions.

        Returns:
            List of all tracked sessions.
        """
        return list(self.sessions.values())

    def get_sessions_needing_notification(self) -> List[TrackedSession]:
        """
        Get sessions that need to send a notification.

        Returns:
            List of sessions waiting for input that haven't been notified recently.
        """
        now = datetime.now()
        needing_notification = []

        for session in self.sessions.values():
            # Only notify for WAITING_INPUT state
            if session.current_state != ClaudeState.WAITING_INPUT:
                continue

            # Check cooldown
            if session.notification_cooldown_until:
                if now < session.notification_cooldown_until:
                    continue

            # Check if we should send a reminder
            if session.last_notification:
                time_since = now - session.last_notification
                if time_since < self.NOTIFICATION_REMINDER:
                    continue

            needing_notification.append(session)

        return needing_notification

    def mark_notified(self, iterm_session_id: str) -> None:
        """
        Mark a session as having been notified.

        Args:
            iterm_session_id: The iTerm2 session ID.
        """
        if iterm_session_id in self.sessions:
            now = datetime.now()
            session = self.sessions[iterm_session_id]
            session.last_notification = now
            session.notification_cooldown_until = now + self.NOTIFICATION_COOLDOWN
            self._save_state()

    def get_status_summary(self) -> Dict[str, any]:
        """
        Get a summary of all session statuses grouped by window.

        Returns:
            Dictionary with status summary.
        """
        # Group sessions by window
        windows: Dict[str, List[TrackedSession]] = {}

        for session in self.sessions.values():
            window_name = session.window_name or "Unnamed"
            if window_name not in windows:
                windows[window_name] = []
            windows[window_name].append(session)

        # Build summary
        summary = {
            'total_sessions': len(self.sessions),
            'windows': {},
            'by_state': {state.value: 0 for state in ClaudeState},
        }

        for window_name, sessions in windows.items():
            window_summary = {
                'sessions': [],
                'by_state': {state.value: 0 for state in ClaudeState},
            }

            for session in sessions:
                window_summary['sessions'].append({
                    'project': session.project_name,
                    'state': session.current_state.value,
                    'task': session.current_task,
                })
                window_summary['by_state'][session.current_state.value] += 1
                summary['by_state'][session.current_state.value] += 1

            summary['windows'][window_name] = window_summary

        return summary

    def get_formatted_status(self, window_filter: Optional[str] = None) -> str:
        """
        Get a formatted status string for display.

        Args:
            window_filter: Optional window name to filter by.

        Returns:
            Formatted status string.
        """
        icons = {
            ClaudeState.WORKING: "\u2699",      # Gear
            ClaudeState.WAITING_INPUT: "\u23F3", # Hourglass
            ClaudeState.DONE: "\u2713",          # Check
            ClaudeState.ERROR: "\u2717",         # X
            ClaudeState.IDLE: "\u25CB",          # Circle
        }

        lines = []
        summary = self.get_status_summary()

        for window_name, window_data in summary['windows'].items():
            if window_filter and window_name != window_filter:
                continue

            lines.append(f"Window: {window_name}")

            for session_info in window_data['sessions']:
                state = ClaudeState(session_info['state'])
                icon = icons.get(state, "?")
                task_str = f" - {session_info['task']}" if session_info['task'] else ""
                lines.append(f"  {icon} {session_info['project']}: {state.value.upper()}{task_str}")

            lines.append("")

        if not lines:
            return "No active sessions"

        return "\n".join(lines)


# CLI for testing
if __name__ == "__main__":
    manager = SessionManager()

    print("Claude HUD - Session Manager Test")
    print("=" * 40)

    # Show current status
    print("\nCurrent Status:")
    print(manager.get_formatted_status())

    # Show raw summary
    print("\nRaw Summary:")
    summary = manager.get_status_summary()
    print(json.dumps(summary, indent=2))
