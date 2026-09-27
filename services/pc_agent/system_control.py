"""
Windows System & File Automation Control for J.A.R.V.I.S.
Provides volume control, screen locking, and local file operations.
"""

from __future__ import annotations
import os
import sys
import subprocess
import glob
import time
from typing import Dict, Any, List, Optional

try:
    import ctypes
    user32 = ctypes.windll.user32
except Exception:
    user32 = None

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisSystemControl")


class SystemControl:
    def lock_workstation(self) -> Dict[str, Any]:
        """Locks the Windows computer screen immediately"""
        logger.info("[SystemControl] Locking workstation screen.")
        if user32 and sys.platform == "win32":
            res = user32.LockWorkStation()
            return {"success": bool(res), "action": "lock_screen", "channel_1_logical": True}
        return {"success": False, "error": "Not running on Windows"}

    def adjust_volume(self, direction: str = "up", steps: int = 5) -> Dict[str, Any]:
        """Adjusts master audio volume relatively (up, down, mute) using native Windows virtual key events."""
        logger.info(f"[SystemControl] Adjusting volume: direction={direction}, steps={steps}")
        if not user32 or sys.platform != "win32":
            return {"success": False, "error": "Not running on Windows"}

        direction_lower = direction.lower().strip()
        if "mute" in direction_lower:
            user32.keybd_event(0xAD, 0, 0, 0)
            user32.keybd_event(0xAD, 0, 2, 0)
            return {"success": True, "action": "toggle_mute", "channel_1_logical": True}

        vk = 0xAF if any(w in direction_lower for w in ["up", "increase", "raise", "higher"]) else 0xAE
        for _ in range(max(1, steps)):
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, 2, 0)
            time.sleep(0.04)

        action_name = "volume_up" if vk == 0xAF else "volume_down"
        return {"success": True, "action": action_name, "steps": steps, "channel_1_logical": True}

    def set_volume(self, level_percent: int) -> Dict[str, Any]:
        """Sets Windows master audio volume (0 to 100) instantly via Core Audio endpoint without stealing focus."""
        try:
            target_level = max(0, min(100, int(level_percent)))
        except (ValueError, TypeError):
            target_level = 50
        logger.info(f"[SystemControl] Setting audio volume to {target_level}%")

        # 1. Native Windows Core Audio (Fast, zero-SendKeys, zero focus-stealing)
        try:
            from services.pc_agent.native_audio import set_master_volume
            ok = set_master_volume(target_level)
            if ok:
                return {"success": True, "volume_set": target_level, "channel_1_logical": True}
        except Exception as e:
            logger.debug(f"[SystemControl] Native audio notice: {e}")

        # 2. Legacy PowerShell fallback
        ps_script = f"""
        $wsh = New-Object -ComObject WScript.Shell
        1..50 | ForEach-Object {{ $wsh.SendKeys([char]174) }} # Mute / Volume Down to 0
        $steps = [math]::Round({target_level} / 2)
        1..$steps | ForEach-Object {{ $wsh.SendKeys([char]175) }} # Volume Up
        """
        try:
            subprocess.run(["powershell", "-c", ps_script], capture_output=True, timeout=5)
            return {"success": True, "volume_set": target_level, "channel_1_logical": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    BLOCKED_SENSITIVE_PATTERNS = [
        r"[\\/]\.aws[\\/]",
        r"[\\/]\.ssh[\\/]",
        r"[\\/](id_rsa|id_ed25519|id_ecdsa)",
        r"[\\/]windows[\\/]system32[\\/]config",
        r"[\\/]etc[\\/](shadow|passwd|master\.passwd)",
        r"(^|[\\/])\.env($|\.)"
    ]

    def _is_path_permitted(self, target_path: str) -> bool:
        """Enforces security boundaries against sensitive credential exfiltration and system files."""
        normalized = os.path.normpath(os.path.abspath(target_path))
        import re
        for pat in self.BLOCKED_SENSITIVE_PATTERNS:
            if re.search(pat, normalized, re.IGNORECASE):
                logger.warning(f"🔒 [SystemControl] Blocked access to sensitive path: {normalized}")
                return False
        return True

    def search_files(self, directory: str, pattern: str) -> List[str]:
        """Searches files by glob pattern with directory jail protection"""
        logger.info(f"[SystemControl] Searching files in '{directory}' matching '{pattern}'")
        if not self._is_path_permitted(directory):
            return []

        # Prevent unbounded root directory freezing
        norm_dir = os.path.normpath(os.path.abspath(directory))
        if norm_dir in ("C:\\", "D:\\", "/", "\\"):
            logger.warning(f"[SystemControl] Unbounded root scan on '{norm_dir}' restricted to depth 2.")
            search_path = os.path.join(directory, "*", pattern)
        else:
            search_path = os.path.join(directory, "**", pattern)

        try:
            matches = glob.glob(search_path, recursive=True)
            safe_matches = [m for m in matches if self._is_path_permitted(m)]
            return safe_matches[:25]
        except Exception as e:
            logger.error(f"[SystemControl] File search error: {e}")
            return []

    def read_file_preview(self, file_path: str, max_chars: int = 1000) -> Dict[str, Any]:
        """Reads preview of a text file safely with path traversal protection"""
        if not self._is_path_permitted(file_path):
            return {"success": False, "error": "SECURITY_ERROR: Access to sensitive or restricted path is prohibited."}

        norm_path = os.path.normpath(os.path.abspath(file_path))
        if not os.path.exists(norm_path):
            return {"success": False, "error": "File not found"}

        try:
            with open(norm_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(min(max(10, max_chars), 50000))
            return {"success": True, "file": norm_path, "preview": content}
        except Exception as e:
            return {"success": False, "error": str(e)}


system_control = SystemControl()
