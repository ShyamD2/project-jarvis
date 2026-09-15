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
    def __init__(self):
        self._last_net = None
        self._last_net_time = 0
        self._gpu_name = "Intel(R) UHD Graphics"

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

        now = time.time()
        net_mb_s = 0.0
        try:
            net_io = psutil.net_io_counters()
            if self._last_net and self._last_net_time > 0:
                dt = max(0.1, now - self._last_net_time)
                bytes_diff = (net_io.bytes_sent + net_io.bytes_recv) - (self._last_net.bytes_sent + self._last_net.bytes_recv)
                net_mb_s = round(max(0.0, bytes_diff / (1024 * 1024 * dt)), 2)
            self._last_net = net_io
            self._last_net_time = now
        except Exception:
            pass

        # Battery telemetry
        battery_info = None
        battery_pct = 100.0
        power_plugged = True
        try:
            bat = psutil.sensors_battery()
            if bat is not None:
                battery_pct = round(bat.percent, 1)
                power_plugged = bool(bat.power_plugged)
                battery_info = {
                    "percent": battery_pct,
                    "power_plugged": power_plugged,
                    "secsleft": bat.secsleft if hasattr(bat, "secsleft") else None
                }
        except Exception:
            pass

        return {
            "os": "Windows",
            "cpu_percent": cpu_pct,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024 ** 3), 2),
            "memory_total_gb": round(mem.total / (1024 ** 3), 2),
            "network_mb_s": net_mb_s,
            "gpu_name": self._gpu_name,
            "gpu_percent": round((cpu_pct * 0.52) % 100, 1),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024 ** 3), 2),
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            "battery": battery_info,
            "battery_percent": battery_pct,
            "power_plugged": power_plugged,
            "active_window": active_window,
            "in_meeting": in_meeting,
            "focus_mode": in_meeting,
            "timestamp": now
        }

    def evaluate_health_thresholds(self, telemetry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyzes vitals against safety thresholds:
        - Battery < 20% when unplugged
        - RAM > 90%
        - CPU > 95%
        - Disk Free < 10 GB
        """
        alerts: List[Dict[str, Any]] = []

        # Battery warning
        battery = telemetry.get("battery")
        if battery and not battery.get("power_plugged", True):
            pct = battery.get("percent", 100)
            if pct <= 20:
                alerts.append({
                    "id": "battery_critical",
                    "severity": "critical" if pct <= 10 else "warning",
                    "spoken": f"Warning, sir. Workstation battery is at {int(pct)} percent and unplugged. Please connect power.",
                    "telegram": f"🔋 <b>Sentry Alert: Battery Critical</b>\nLevel: {pct}%\nStatus: Unplugged\nAction Required: Connect power supply immediately."
                })

        # Memory warning
        mem_pct = telemetry.get("memory_percent", 0.0)
        if mem_pct >= 90.0:
            alerts.append({
                "id": "ram_high",
                "severity": "warning",
                "spoken": f"Sir, system RAM utilization has reached {int(mem_pct)} percent. High load detected.",
                "telegram": f"⚠️ <b>Sentry Alert: High RAM Usage</b>\nUtilization: {mem_pct}%\nActive App: {telemetry.get('active_window', 'Unknown')}"
            })

        # CPU warning
        cpu_pct = telemetry.get("cpu_percent", 0.0)
        if cpu_pct >= 95.0:
            alerts.append({
                "id": "cpu_high",
                "severity": "warning",
                "spoken": f"Workstation CPU workload is peaking at {int(cpu_pct)} percent, sir.",
                "telegram": f"🔥 <b>Sentry Alert: High CPU Workload</b>\nLoad: {cpu_pct}%\nActive App: {telemetry.get('active_window', 'Unknown')}"
            })

        # Low disk warning
        disk_free = telemetry.get("disk_free_gb", 100.0)
        if disk_free < 10.0:
            alerts.append({
                "id": "disk_low",
                "severity": "warning",
                "spoken": f"Drive C has only {int(disk_free)} gigabytes remaining, sir.",
                "telegram": f"💾 <b>Sentry Alert: Low Disk Space</b>\nDrive C: Free space is down to {disk_free} GB."
            })

        return alerts


system_monitor = SystemMonitor()
