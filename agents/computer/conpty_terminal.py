"""
Persistent Interactive Terminal Session Manager for Project J.A.R.V.I.S.
Provides persistent background shell sessions (PowerShell, CMD, Bash)
allowing multi-turn interactive CLI execution, SSH sessions, Python REPLs,
interactive installers, and streaming stdout/stderr diagnostics without closing process context.
"""

from __future__ import annotations
import os
import time
import queue
import threading
import subprocess
from typing import Dict, Any, List, Optional

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("ConPTYTerminal")


class PersistentShellSession:
    def __init__(self, session_id: str, shell: str = "powershell.exe", cwd: Optional[str] = None):
        self.session_id = session_id
        self.shell = shell
        self.cwd = cwd or os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self.created_at = time.time()
        self._start_process()

    def _start_process(self):
        cmd = [self.shell, "-NoLogo", "-NoProfile", "-NoExit"] if "powershell" in self.shell.lower() else [self.shell]
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=self.cwd,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            self._running = True
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True, name=f"PTYReader-{self.session_id}")
            self._reader_thread.start()
            time.sleep(0.3)
            logger.info(f"[ConPTYTerminal] Spawned persistent session '{self.session_id}' using {self.shell} (PID: {self.process.pid})")
        except Exception as e:
            logger.error(f"[ConPTYTerminal] Failed to spawn {self.shell}: {e}")
            self._running = False

    def _read_loop(self):
        while self._running and self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if line:
                    self.output_queue.put(line)
                else:
                    time.sleep(0.02)
            except Exception:
                break

    def send_command(self, command: str) -> bool:
        if not self.process or self.process.poll() is not None:
            logger.warning(f"[ConPTYTerminal] Session '{self.session_id}' is terminated. Restarting...")
            self._start_process()

        try:
            self.process.stdin.write(command.strip() + "\r\n")
            self.process.stdin.flush()
            return True
        except Exception as e:
            logger.error(f"[ConPTYTerminal] Write error in session '{self.session_id}': {e}")
            return False

    def read_available_output(self, timeout: float = 6.0, expected: Optional[str] = None) -> str:
        """Reads output lines until stream pauses, expected content appears, or timeout expires."""
        lines = []
        deadline = time.time() + timeout
        quiescent_count = 0
        while time.time() < deadline:
            try:
                line = self.output_queue.get(timeout=0.1)
                lines.append(line)
                while not self.output_queue.empty():
                    lines.append(self.output_queue.get_nowait())
                quiescent_count = 0
                if expected and any(expected in l for l in lines):
                    time.sleep(0.05)
                    while not self.output_queue.empty():
                        lines.append(self.output_queue.get_nowait())
                    break
            except queue.Empty:
                if lines:
                    quiescent_count += 1
                    if quiescent_count >= 8:
                        break

        return "".join(lines).strip()

    def close(self):
        self._running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception:
                pass


class ConPTYManager:
    def __init__(self):
        self._sessions: Dict[str, PersistentShellSession] = {}

    def get_session(self, session_id: str = "default", shell: str = "powershell.exe") -> PersistentShellSession:
        if session_id not in self._sessions or not self._sessions[session_id].process or self._sessions[session_id].process.poll() is not None:
            self._sessions[session_id] = PersistentShellSession(session_id, shell=shell)
        return self._sessions[session_id]

    def execute_in_session(self, command: str, session_id: str = "default", timeout: float = 6.0) -> Dict[str, Any]:
        """Executes an interactive command within a persistent terminal context."""
        sess = self.get_session(session_id)
        ok = sess.send_command(command)
        if not ok:
            return {"success": False, "error": "Failed to send command to persistent shell"}

        # Target token from command for early return if present
        parts = command.strip().split()
        expected_token = parts[-1] if parts else None

        output = sess.read_available_output(timeout=timeout, expected=expected_token)
        return {
            "success": True,
            "session_id": session_id,
            "command": command,
            "output": output,
            "active": (sess.process.poll() is None)
        }

    def terminate_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            self._sessions[session_id].close()
            del self._sessions[session_id]
            logger.info(f"[ConPTYTerminal] Terminated session '{session_id}'")
            return True
        return False

    def terminate_all(self):
        for sid in list(self._sessions.keys()):
            self.terminate_session(sid)

    def close_all(self):
        self.terminate_all()


conpty_manager = ConPTYManager()
terminal_manager = conpty_manager
