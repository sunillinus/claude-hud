#!/usr/bin/env python3
"""
Claude HUD - State Detector

Monitors Claude Code debug logs to detect session states:
- IDLE: No active work
- WORKING: Actively processing/streaming
- WAITING_INPUT: Permission prompt waiting for user
- DONE: Task completed
- ERROR: Error occurred
"""

import sys
sys.dont_write_bytecode = True

import os
import re
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Tuple


class ClaudeState(Enum):
    IDLE = "idle"
    WORKING = "working"
    WAITING_INPUT = "waiting"
    DONE = "done"
    ERROR = "error"


@dataclass
class StateInfo:
    """Information about the current state of a Claude Code session."""
    state: ClaudeState
    project_name: Optional[str] = None
    current_task: Optional[str] = None
    last_activity: Optional[datetime] = None
    error_message: Optional[str] = None


class ClaudeStateDetector:
    """Detects the state of a Claude Code session by monitoring debug logs."""

    CLAUDE_DIR = Path.home() / ".claude"
    DEBUG_DIR = CLAUDE_DIR / "debug"
    TODOS_DIR = CLAUDE_DIR / "todos"

    # Patterns to detect in debug logs
    PATTERNS = {
        'working': [
            r'Stream started',
            r'executePreToolHooks',
            r'\[API:request\]',
            r'Executing tool',
        ],
        'waiting': [
            r'permission_prompt',
            r'GetInput',
        ],
        'error': [
            r'\[ERROR\]',
            r'Error:',
        ],
        'done': [
            r'Stream completed',
            r'Task completed',
        ],
    }

    # Compiled regex patterns for efficiency
    _compiled_patterns: dict = {}

    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize the state detector.

        Args:
            session_id: Optional Claude Code session ID. If not provided,
                       will attempt to detect from recent activity.
        """
        self.session_id = session_id
        self._last_file_position = 0
        self._last_state = ClaudeState.IDLE
        self._last_activity_time: Optional[datetime] = None
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching."""
        if not self._compiled_patterns:
            for state, patterns in self.PATTERNS.items():
                self._compiled_patterns[state] = [
                    re.compile(p, re.IGNORECASE) for p in patterns
                ]

    def find_debug_file(self) -> Optional[Path]:
        """
        Find the debug log file for this session.

        Returns:
            Path to the debug log file, or None if not found.
        """
        if not self.DEBUG_DIR.exists():
            return None

        # If we have a session ID, look for that specific file
        if self.session_id:
            debug_file = self.DEBUG_DIR / f"{self.session_id}.txt"
            if debug_file.exists():
                return debug_file

        # Otherwise, find the most recently modified debug file
        debug_files = list(self.DEBUG_DIR.glob("*.txt"))
        if not debug_files:
            return None

        # Sort by modification time, most recent first
        debug_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return debug_files[0]

    def find_active_sessions(self) -> List[Tuple[str, Path]]:
        """
        Find all active Claude Code sessions.

        Returns:
            List of (session_id, debug_file_path) tuples for active sessions.
        """
        if not self.DEBUG_DIR.exists():
            return []

        active_sessions = []
        now = datetime.now()

        for debug_file in self.DEBUG_DIR.glob("*.txt"):
            # Consider a session active if modified in the last 5 minutes
            mtime = datetime.fromtimestamp(debug_file.stat().st_mtime)
            if now - mtime < timedelta(minutes=5):
                session_id = debug_file.stem
                active_sessions.append((session_id, debug_file))

        return active_sessions

    def read_recent_entries(self, debug_file: Path, max_lines: int = 100) -> List[str]:
        """
        Read recent entries from a debug log file.

        Args:
            debug_file: Path to the debug log file.
            max_lines: Maximum number of lines to read from the end.

        Returns:
            List of recent log entries.
        """
        try:
            with open(debug_file, 'r', encoding='utf-8', errors='ignore') as f:
                # Read all lines and get the last max_lines
                lines = f.readlines()
                return lines[-max_lines:] if len(lines) > max_lines else lines
        except (IOError, OSError):
            return []

    def read_new_entries(self, debug_file: Path) -> List[str]:
        """
        Read only new entries since last check.

        Args:
            debug_file: Path to the debug log file.

        Returns:
            List of new log entries since last read.
        """
        try:
            file_size = debug_file.stat().st_size

            # If file was truncated or is new, start from beginning
            if file_size < self._last_file_position:
                self._last_file_position = 0

            with open(debug_file, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(self._last_file_position)
                new_content = f.read()
                self._last_file_position = f.tell()

            return new_content.splitlines() if new_content else []
        except (IOError, OSError):
            return []

    def parse_timestamp(self, line: str) -> Optional[datetime]:
        """
        Parse timestamp from a debug log line.

        Args:
            line: A line from the debug log.

        Returns:
            Datetime if timestamp found, None otherwise.
        """
        # Common timestamp format: 2026-01-13T09:48:27.123Z
        match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
        if match:
            try:
                return datetime.fromisoformat(match.group(1))
            except ValueError:
                pass
        return None

    def analyze_entries(self, entries: List[str]) -> ClaudeState:
        """
        Analyze log entries to determine the current state.

        Args:
            entries: List of recent log entries.

        Returns:
            The detected ClaudeState.
        """
        if not entries:
            return ClaudeState.IDLE

        # Check entries from most recent to oldest
        reversed_entries = list(reversed(entries))
        recent_text = '\n'.join(reversed_entries[:50])

        # Check for error state first (highest priority)
        for pattern in self._compiled_patterns.get('error', []):
            if pattern.search(recent_text):
                return ClaudeState.ERROR

        # Track when we last saw each type of pattern
        waiting_index = -1
        working_index = -1
        done_index = -1

        for i, line in enumerate(reversed_entries[:50]):
            # Check for waiting patterns
            for pattern in self._compiled_patterns.get('waiting', []):
                if pattern.search(line) and waiting_index == -1:
                    waiting_index = i

            # Check for working patterns
            for pattern in self._compiled_patterns.get('working', []):
                if pattern.search(line) and working_index == -1:
                    working_index = i

            # Check for done patterns
            for pattern in self._compiled_patterns.get('done', []):
                if pattern.search(line) and done_index == -1:
                    done_index = i

        # Determine state based on which pattern appeared most recently
        # (lower index = more recent)

        # If waiting is most recent, we're waiting for input
        if waiting_index != -1:
            if working_index == -1 or waiting_index < working_index:
                return ClaudeState.WAITING_INPUT

        # If done is most recent and no activity after, we're done
        if done_index != -1:
            if (working_index == -1 or done_index < working_index) and \
               (waiting_index == -1 or done_index < waiting_index):
                return ClaudeState.DONE

        # If we saw working patterns recently, we're working
        if working_index != -1 and working_index < 10:
            return ClaudeState.WORKING

        # Check file modification time for activity
        return ClaudeState.IDLE

    def get_state(self) -> StateInfo:
        """
        Get the current state of the Claude Code session.

        Returns:
            StateInfo with the current state and metadata.
        """
        debug_file = self.find_debug_file()

        if not debug_file:
            return StateInfo(state=ClaudeState.IDLE)

        # Check if file was recently modified
        mtime = datetime.fromtimestamp(debug_file.stat().st_mtime)
        now = datetime.now()

        # If no activity in last 30 seconds, consider it done/idle
        if now - mtime > timedelta(seconds=30):
            if self._last_state == ClaudeState.WORKING:
                return StateInfo(
                    state=ClaudeState.DONE,
                    last_activity=mtime
                )
            return StateInfo(
                state=ClaudeState.IDLE,
                last_activity=mtime
            )

        # Read and analyze recent entries
        entries = self.read_recent_entries(debug_file)
        state = self.analyze_entries(entries)

        self._last_state = state
        self._last_activity_time = mtime

        return StateInfo(
            state=state,
            last_activity=mtime
        )

    def get_state_for_session(self, session_id: str) -> StateInfo:
        """
        Get the state for a specific session ID.

        Args:
            session_id: The Claude Code session ID.

        Returns:
            StateInfo with the current state and metadata.
        """
        debug_file = self.DEBUG_DIR / f"{session_id}.txt"

        if not debug_file.exists():
            return StateInfo(state=ClaudeState.IDLE)

        detector = ClaudeStateDetector(session_id)
        return detector.get_state()


def get_project_name_from_path(project_path: str) -> str:
    """
    Extract a display name from a project path.

    Args:
        project_path: The full path to the project.

    Returns:
        A short display name for the project.
    """
    return Path(project_path).name


# CLI for testing
if __name__ == "__main__":
    import sys
    import time

    detector = ClaudeStateDetector()

    print("Claude HUD - State Detector Test")
    print("=" * 40)

    # Find active sessions
    sessions = detector.find_active_sessions()
    print(f"\nFound {len(sessions)} active session(s)")

    for session_id, debug_file in sessions:
        print(f"\nSession: {session_id}")
        print(f"  Debug file: {debug_file}")

        # Get state for this session
        state_info = detector.get_state_for_session(session_id)
        print(f"  State: {state_info.state.value}")
        if state_info.last_activity:
            print(f"  Last activity: {state_info.last_activity}")

    # If monitoring mode requested
    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        print("\n\nWatching for state changes (Ctrl+C to stop)...")
        last_state = None

        while True:
            state_info = detector.get_state()
            if state_info.state != last_state:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] State: {state_info.state.value}")
                last_state = state_info.state
            time.sleep(0.5)
