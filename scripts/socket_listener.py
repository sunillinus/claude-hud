#!/usr/bin/env python3
"""
Claude HUD - Socket Listener

Listens for state updates from Claude Code hooks via Unix domain socket.
Maps Claude session_id to iTerm2 session_id and triggers visual updates.
"""

import sys
sys.dont_write_bytecode = True

import asyncio
import json
import os
import socket
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Callable, Any, Awaitable

from state_detector import ClaudeState


class SessionMapper:
    """
    Maps Claude session_id to iTerm2 session_id.

    Strategy:
    1. On SessionStart hook, record (claude_session_id, cwd)
    2. When daemon tracks new iTerm2 session, record (iterm_session_id, cwd)
    3. Match based on cwd
    """

    MAP_FILE = Path.home() / ".claude-hud" / "session-map.json"

    def __init__(self):
        self._claude_sessions: Dict[str, dict] = {}  # claude_id -> {cwd, timestamp}
        self._iterm_sessions: Dict[str, dict] = {}   # iterm_id -> {cwd, timestamp}
        self._mapping: Dict[str, str] = {}           # claude_id -> iterm_id
        self._reverse_mapping: Dict[str, str] = {}   # iterm_id -> claude_id
        self._load_mapping()

    def _load_mapping(self) -> None:
        """Load persisted mapping from disk."""
        if self.MAP_FILE.exists():
            try:
                with open(self.MAP_FILE, 'r') as f:
                    data = json.load(f)
                    self._mapping = data.get('mapping', {})
                    self._reverse_mapping = {v: k for k, v in self._mapping.items()}
            except (json.JSONDecodeError, IOError):
                pass

    def _save_mapping(self) -> None:
        """Persist mapping to disk."""
        self.MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.MAP_FILE, 'w') as f:
                json.dump({
                    'mapping': self._mapping,
                    'updated': datetime.now().isoformat()
                }, f, indent=2)
        except IOError:
            pass

    def register_claude_session(self, claude_id: str, cwd: str) -> Optional[str]:
        """
        Register a Claude session from hook.
        Returns matched iTerm session_id if found.
        """
        now = datetime.now()
        self._claude_sessions[claude_id] = {
            'cwd': cwd,
            'timestamp': now.isoformat()
        }

        # Try to match with existing iTerm session
        return self._try_match_by_cwd(claude_id, cwd)

    def register_iterm_session(self, iterm_id: str, cwd: str) -> Optional[str]:
        """
        Register an iTerm2 session from daemon.
        Returns matched Claude session_id if found.
        """
        now = datetime.now()
        self._iterm_sessions[iterm_id] = {
            'cwd': cwd,
            'timestamp': now.isoformat()
        }

        # Try to match with existing Claude sessions
        for claude_id, info in self._claude_sessions.items():
            if info['cwd'] == cwd and claude_id not in self._mapping:
                self._mapping[claude_id] = iterm_id
                self._reverse_mapping[iterm_id] = claude_id
                self._save_mapping()
                print(f"[SessionMapper] Matched: {claude_id[:8]}... -> {iterm_id}")
                return claude_id

        return None

    def _try_match_by_cwd(self, claude_id: str, cwd: str) -> Optional[str]:
        """Try to match Claude session with iTerm session by cwd."""
        # Already mapped?
        if claude_id in self._mapping:
            return self._mapping[claude_id]

        # Find iTerm session with matching cwd that isn't already mapped
        for iterm_id, info in self._iterm_sessions.items():
            if info['cwd'] == cwd and iterm_id not in self._reverse_mapping:
                self._mapping[claude_id] = iterm_id
                self._reverse_mapping[iterm_id] = claude_id
                self._save_mapping()
                print(f"[SessionMapper] Matched: {claude_id[:8]}... -> {iterm_id}")
                return iterm_id

        return None

    def get_iterm_session(self, claude_id: str) -> Optional[str]:
        """Get iTerm session_id for a Claude session_id."""
        return self._mapping.get(claude_id)

    def get_claude_session(self, iterm_id: str) -> Optional[str]:
        """Get Claude session_id for an iTerm session_id."""
        return self._reverse_mapping.get(iterm_id)

    def unregister_iterm_session(self, iterm_id: str) -> None:
        """Remove an iTerm session from tracking."""
        if iterm_id in self._iterm_sessions:
            del self._iterm_sessions[iterm_id]

        if iterm_id in self._reverse_mapping:
            claude_id = self._reverse_mapping[iterm_id]
            del self._reverse_mapping[iterm_id]
            if claude_id in self._mapping:
                del self._mapping[claude_id]
            if claude_id in self._claude_sessions:
                del self._claude_sessions[claude_id]
            self._save_mapping()


class SocketListener:
    """
    Listens for state updates via Unix domain socket.
    Uses SOCK_DGRAM for non-blocking, connectionless messaging.
    """

    SOCKET_PATH = Path.home() / ".claude-hud" / "daemon.sock"
    BUFFER_SIZE = 4096

    def __init__(
        self,
        session_mapper: SessionMapper,
        on_state_update: Callable[[str, ClaudeState, str], Awaitable[None]]
    ):
        """
        Initialize the socket listener.

        Args:
            session_mapper: SessionMapper instance for claude->iterm mapping
            on_state_update: Async callback (iterm_session_id, state, cwd) for updates
        """
        self.session_mapper = session_mapper
        self.on_state_update = on_state_update
        self._socket: Optional[socket.socket] = None
        self._running = False

    def _setup_socket(self) -> None:
        """Create and bind the Unix domain socket."""
        # Ensure directory exists
        self.SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing socket file
        if self.SOCKET_PATH.exists():
            self.SOCKET_PATH.unlink()

        # Create datagram socket
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self._socket.setblocking(False)
        self._socket.bind(str(self.SOCKET_PATH))

        # Set permissions (owner read/write only)
        os.chmod(str(self.SOCKET_PATH), 0o600)

        print(f"[SocketListener] Bound to {self.SOCKET_PATH}")

    def _cleanup_socket(self) -> None:
        """Clean up the socket."""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass

        if self.SOCKET_PATH.exists():
            try:
                self.SOCKET_PATH.unlink()
            except Exception:
                pass

    async def start(self) -> None:
        """Start listening for messages."""
        self._setup_socket()
        self._running = True

        while self._running:
            try:
                # Non-blocking receive
                try:
                    data, _ = self._socket.recvfrom(self.BUFFER_SIZE)
                    if data:
                        await self._handle_message(data)
                except BlockingIOError:
                    # No data available
                    pass
                except socket.error:
                    pass

                # Small sleep to prevent busy-waiting
                await asyncio.sleep(0.01)

            except Exception as e:
                print(f"[SocketListener] Error: {e}")
                await asyncio.sleep(0.1)

    async def _handle_message(self, data: bytes) -> None:
        """Process a received message."""
        try:
            message = json.loads(data.decode('utf-8'))

            msg_type = message.get('type')
            if msg_type != 'state_update':
                return

            claude_session_id = message.get('session_id')
            cwd = message.get('cwd', '')
            state_str = message.get('state', 'idle')
            hook_event = message.get('hook_event', '')

            if not claude_session_id:
                return

            # Map state string to enum
            state_map = {
                'idle': ClaudeState.IDLE,
                'working': ClaudeState.WORKING,
                'waiting': ClaudeState.WAITING_INPUT,
                'done': ClaudeState.DONE,
                'error': ClaudeState.ERROR
            }
            state = state_map.get(state_str, ClaudeState.IDLE)

            # Register Claude session (helps with mapping)
            self.session_mapper.register_claude_session(claude_session_id, cwd)

            # Get iTerm session ID
            iterm_session_id = self.session_mapper.get_iterm_session(claude_session_id)

            if iterm_session_id:
                # Trigger visual update
                print(f"[Hook] {hook_event}: {state_str} (cwd: {Path(cwd).name})")
                await self.on_state_update(iterm_session_id, state, cwd)
            else:
                # No mapping yet - will be matched when daemon detects iTerm session
                print(f"[Hook] No iTerm mapping for Claude session {claude_session_id[:8]}... (cwd: {cwd})")

        except json.JSONDecodeError:
            print(f"[SocketListener] Invalid JSON: {data[:100]}")
        except Exception as e:
            print(f"[SocketListener] Error handling message: {e}")

    def stop(self) -> None:
        """Stop the listener and clean up."""
        self._running = False
        self._cleanup_socket()
