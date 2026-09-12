"""
Windows System Monitor & Telemetry Engine for J.A.R.V.I.S. PC Agent.
Monitors CPU, RAM, active foreground window, and meeting presence state.
"""

from __future__ import annotations
import psutil
import time
import sys
from typing import Dict, Any, Optional

try:
    import ctypes
    user32 = ctypes.windll.user32
except Exception:
    user32 = None

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisSystemMonitor")


class SystemMonitor:
    def get_active_window_title(self) -> str:
        """Retrieves title of the currently focused foreground window on Windows"""
        if user32 and sys.platform == "win32":
            try:
                hwnd = user32.GetForegroundWindow()
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    return buff.value
            except Exception as e:
                logger.debug(f"Could not get foreground window title: {e}")
        return "Unknown Desktop"

    def detect_meeting_presence(self) -> bool:
        """
        Detects if user is on a call or screen-sharing
        (Zoom, Teams, Discord, Meet, Webex running or active).
        """
        meeting_apps = {"zoom.exe", "teams.exe", "slack.exe", "discord.exe", "webex.exe"}
        try:
            for p in psutil.process_iter(['name']):
                if p.info['name'] and p.info['name'].lower() in meeting_apps:
                    return True
        except Exception as e:
            logger.debug(f"Could not iterate processes for meeting presence: {e}")
        return False

    def collect_telemetry(self) -> Dict[str, Any]:
        """Collects full system vitals snapshot"""
        cpu_pct = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')
        active_window = self.get_active_window_title()
        in_meeting = self.detect_meeting_presence()

        return {
            "os": "Windows",
            "cpu_percent": cpu_pct,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024 ** 3), 2),
            "memory_total_gb": round(mem.total / (1024 ** 3), 2),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024 ** 3), 2),
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            "active_window": active_window,
            "in_meeting": in_meeting,
            "focus_mode": in_meeting,
            "timestamp": time.time()
        }


system_monitor = SystemMonitor()
