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
        """Sets Windows master audio volume (0 to 100) via PowerShell Audio endpoint"""
        logger.info(f"[SystemControl] Setting audio volume to {level_percent}%")
        # PowerShell script using Audio Device endpoint
        ps_script = f"""
        $wsh = New-Object -ComObject WScript.Shell
        1..50 | ForEach-Object {{ $wsh.SendKeys([char]174) }} # Mute / Volume Down to 0
        $steps = [math]::Round({level_percent} / 2)
        1..$steps | ForEach-Object {{ $wsh.SendKeys([char]175) }} # Volume Up
        """
        try:
            subprocess.run(["powershell", "-c", ps_script], capture_output=True, timeout=5)
            return {"success": True, "volume_set": level_percent, "channel_1_logical": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_files(self, directory: str, pattern: str) -> List[str]:
        """Searches files by glob pattern"""
        logger.info(f"[SystemControl] Searching files in '{directory}' matching '{pattern}'")
        search_path = os.path.join(directory, "**", pattern)
        matches = glob.glob(search_path, recursive=True)
        return matches[:25] # Return top 25 matches

    def read_file_preview(self, file_path: str, max_chars: int = 1000) -> Dict[str, Any]:
        """Reads preview of a text file safely"""
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_chars)
            return {"success": True, "file": file_path, "preview": content}
        except Exception as e:
            return {"success": False, "error": str(e)}


system_control = SystemControl()
