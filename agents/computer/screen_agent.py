"""
J.A.R.V.I.S. Screen & Capture Agent (Computer Pillar).
Handles screenshots, display geometry, and screen capture operations.
"""

import os
import sys
import time
import ctypes
from datetime import datetime
from typing import Dict, Any, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisScreenAgent")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, "services", "sensory", "screenshots")


class ScreenAgent:
    def __init__(self):
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        self._user32 = ctypes.windll.user32 if sys.platform == "win32" else None

    def get_screen_resolution(self) -> Dict[str, Any]:
        """Returns primary display resolution (width x height)"""
        if not self._user32:
            return {"width": 1920, "height": 1080}
        w = self._user32.GetSystemMetrics(0) # SM_CXSCREEN
        h = self._user32.GetSystemMetrics(1) # SM_CYSCREEN
        return {"success": True, "width": w, "height": h}

    def capture_screenshot(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Captures full screen and saves to PNG file"""
        logger.info("[ScreenAgent] Capturing screen snapshot")
        if not output_path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(SCREENSHOTS_DIR, f"screen_{ts}.png")

        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
                if not hdesk:
                    hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
                if hdesk:
                    user32.SetThreadDesktop(hdesk)
            except Exception:
                pass

        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(all_screens=True)
            img.save(output_path, "PNG")
            return {
                "success": True,
                "screenshot_path": output_path,
                "size_bytes": os.path.getsize(output_path),
                "resolution": img.size
            }
        except Exception as e_pil:
            logger.debug(f"PIL ImageGrab error: {e_pil}; attempting PowerShell fallback")
            # PowerShell fallback
            try:
                safe_out = output_path.replace("'", "''")
                ps_script = f"""
                Add-Type -AssemblyName System.Windows.Forms
                Add-Type -AssemblyName System.Drawing
                $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
                $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
                $graphics = [System.Drawing.Graphics]::FromImage($bmp)
                $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
                $bmp.Save('{safe_out}', [System.Drawing.Imaging.ImageFormat]::Png)
                $graphics.Dispose()
                $bmp.Dispose()
                """
                import subprocess
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, timeout=5)
                if os.path.exists(output_path):
                    return {"success": True, "screenshot_path": output_path, "fallback": True}
            except Exception as e_ps:
                return {"success": False, "error": f"Capture failed: {e_pil} | {e_ps}"}

        return {"success": False, "error": "Screenshot failed"}


screen_agent = ScreenAgent()
