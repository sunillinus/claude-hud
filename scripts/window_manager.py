#!/usr/bin/env python3
"""
Claude HUD - Window Manager

Tracks named iTerm2 windows for Claude HUD sessions.
Maps window names to iTerm2 window IDs for targeting new sessions.
"""

import sys
sys.dont_write_bytecode = True

import json
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class TrackedWindow:
    """Represents a tracked iTerm2 window."""
    name: str
    iterm_window_id: str
    created_at: datetime
    session_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'iterm_window_id': self.iterm_window_id,
            'created_at': self.created_at.isoformat(),
            'session_count': self.session_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'TrackedWindow':
        """Create from dictionary."""
        return cls(
            name=data['name'],
            iterm_window_id=data['iterm_window_id'],
            created_at=datetime.fromisoformat(data['created_at']),
            session_count=data.get('session_count', 0),
        )


class WindowManager:
    """
    Manages tracking of named iTerm2 windows.

    Provides methods to:
    - Register/unregister named windows
    - Find windows by name
    - Get the most recently used window
    - Track session counts per window
    """

    STATE_FILE = Path.home() / ".claude-hud" / "windows.json"

    def __init__(self):
        """Initialize the window manager."""
        self.windows: Dict[str, TrackedWindow] = {}
        self._last_used_window: Optional[str] = None
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
                    for window_data in data.get('windows', []):
                        window = TrackedWindow.from_dict(window_data)
                        self.windows[window.name] = window
                    self._last_used_window = data.get('last_used_window')
            except (json.JSONDecodeError, IOError):
                pass

    def _save_state(self) -> None:
        """Persist state to disk."""
        self._ensure_state_dir()
        data = {
            'windows': [w.to_dict() for w in self.windows.values()],
            'last_used_window': self._last_used_window,
            'last_updated': datetime.now().isoformat(),
        }
        try:
            with open(self.STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass

    def register_window(
        self,
        name: str,
        iterm_window_id: str,
    ) -> TrackedWindow:
        """
        Register a new named window.

        Args:
            name: The name for the window.
            iterm_window_id: The iTerm2 window ID.

        Returns:
            The registered window.
        """
        window = TrackedWindow(
            name=name,
            iterm_window_id=iterm_window_id,
            created_at=datetime.now(),
        )

        self.windows[name] = window
        self._last_used_window = name
        self._save_state()

        return window

    def unregister_window(self, name: str) -> bool:
        """
        Unregister a named window.

        Args:
            name: The name of the window to unregister.

        Returns:
            True if window was found and removed, False otherwise.
        """
        if name in self.windows:
            del self.windows[name]
            if self._last_used_window == name:
                self._last_used_window = None
            self._save_state()
            return True
        return False

    def get_window(self, name: str) -> Optional[TrackedWindow]:
        """
        Get a window by name.

        Args:
            name: The name of the window.

        Returns:
            The tracked window, or None if not found.
        """
        return self.windows.get(name)

    def get_window_by_iterm_id(self, iterm_window_id: str) -> Optional[TrackedWindow]:
        """
        Get a window by its iTerm2 window ID.

        Args:
            iterm_window_id: The iTerm2 window ID.

        Returns:
            The tracked window, or None if not found.
        """
        for window in self.windows.values():
            if window.iterm_window_id == iterm_window_id:
                return window
        return None

    def get_last_used_window(self) -> Optional[TrackedWindow]:
        """
        Get the most recently used window.

        Returns:
            The most recently used window, or None if no windows tracked.
        """
        if self._last_used_window and self._last_used_window in self.windows:
            return self.windows[self._last_used_window]

        # Fall back to most recently created
        if self.windows:
            return max(self.windows.values(), key=lambda w: w.created_at)

        return None

    def mark_window_used(self, name: str) -> None:
        """
        Mark a window as the most recently used.

        Args:
            name: The name of the window.
        """
        if name in self.windows:
            self._last_used_window = name
            self._save_state()

    def increment_session_count(self, name: str) -> None:
        """
        Increment the session count for a window.

        Args:
            name: The name of the window.
        """
        if name in self.windows:
            self.windows[name].session_count += 1
            self._save_state()

    def decrement_session_count(self, name: str) -> None:
        """
        Decrement the session count for a window.

        Args:
            name: The name of the window.
        """
        if name in self.windows:
            self.windows[name].session_count = max(0, self.windows[name].session_count - 1)
            self._save_state()

    def get_all_windows(self) -> List[TrackedWindow]:
        """
        Get all tracked windows.

        Returns:
            List of all tracked windows.
        """
        return list(self.windows.values())

    def get_window_names(self) -> List[str]:
        """
        Get all window names.

        Returns:
            List of window names.
        """
        return list(self.windows.keys())

    def update_window_id(self, name: str, new_iterm_window_id: str) -> bool:
        """
        Update the iTerm2 window ID for a named window.

        This is useful when a window is recreated but we want to keep the name.

        Args:
            name: The name of the window.
            new_iterm_window_id: The new iTerm2 window ID.

        Returns:
            True if window was found and updated, False otherwise.
        """
        if name in self.windows:
            self.windows[name].iterm_window_id = new_iterm_window_id
            self._save_state()
            return True
        return False

    def cleanup_stale_windows(self, valid_window_ids: List[str]) -> List[str]:
        """
        Remove windows that no longer exist in iTerm2.

        Args:
            valid_window_ids: List of currently valid iTerm2 window IDs.

        Returns:
            List of removed window names.
        """
        removed = []
        for name, window in list(self.windows.items()):
            if window.iterm_window_id not in valid_window_ids:
                del self.windows[name]
                removed.append(name)

        if removed:
            self._save_state()

        return removed


# CLI for testing
if __name__ == "__main__":
    manager = WindowManager()

    print("Claude HUD - Window Manager Test")
    print("=" * 40)

    # Show current windows
    windows = manager.get_all_windows()
    print(f"\nTracked windows: {len(windows)}")

    for window in windows:
        print(f"  - {window.name} (sessions: {window.session_count})")

    # Show last used
    last_used = manager.get_last_used_window()
    if last_used:
        print(f"\nLast used: {last_used.name}")
