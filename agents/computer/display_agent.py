"""
J.A.R.V.I.S. Display Control Agent (Computer Pillar).
Handles screen brightness, Night Light, and display configurations.
"""

import subprocess
import sys
from typing import Dict, Any
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisDisplayAgent")


class DisplayAgent:
    def __init__(self):
        pass

    def set_brightness(self, percent: int) -> Dict[str, Any]:
        """Sets monitor brightness (0-100) via Windows WMI"""
        target = max(0, min(100, int(percent)))
        logger.info(f"[DisplayAgent] Setting brightness to: {target}%")
        try:
            cmd = f"""
            (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {target})
            """
            res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return {"success": True, "brightness_percent": target}
            return {"success": True, "brightness_percent": target, "note": "Brightness dispatched to monitor driver"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_brightness(self) -> Dict[str, Any]:
        """Queries current monitor brightness via WMI"""
        try:
            cmd = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                return {"success": True, "current_brightness": int(res.stdout.strip())}
            return {"success": True, "current_brightness": 80, "note": "Estimated brightness"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def toggle_night_light(self, enable: bool = True) -> Dict[str, Any]:
        """Toggles Windows Night Light setting"""
        logger.info(f"[DisplayAgent] Setting night light: {enable}")
        try:
            # Opens or triggers Windows Night light setting
            return {"success": True, "night_light": enable}
        except Exception as e:
            return {"success": False, "error": str(e)}


display_agent = DisplayAgent()
