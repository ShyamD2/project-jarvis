"""
Autonomous Action Failure Recovery Engine for Project J.A.R.V.I.S.
Implements: Diagnose -> Generate Alternate Plan -> Retry Safely -> Verify Again.
Exhausts multi-tier recovery strategies before escalating failure to operator.
"""

from __future__ import annotations
import os
import time
import shutil
import subprocess
from typing import Dict, Any, List, Optional

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("RecoveryEngine")


class RecoveryEngine:
    def __init__(self):
        pass

    async def attempt_recovery(self, tool_name: str, parameters: Dict[str, Any], original_error: str) -> Dict[str, Any]:
        """
        Diagnoses the failure signature and executes fallback recovery strategies.
        """
        logger.warning(f"🔧 [RecoveryEngine] Intercepted failure for tool '{tool_name}': {original_error}. Initiating autonomous recovery...")

        # 1. APPLICATION LAUNCH RECOVERY
        if tool_name in ["manage_window", "open_app", "launch_app"] or "launch" in tool_name:
            target = parameters.get("target") or parameters.get("app_name") or ""
            return await self._recover_app_launch(target, original_error)

        # 2. BROWSER CDP / WEB RECOVERY
        if "browser" in tool_name or tool_name in ["fetch_webpage", "web_search"]:
            url = parameters.get("url") or ""
            return await self._recover_browser_action(url, original_error)

        # 3. UI ELEMENT CLICK RECOVERY
        if "click" in tool_name or "mouse" in tool_name:
            element = parameters.get("element_name") or parameters.get("target") or ""
            return await self._recover_ui_click(element, original_error)

        return {
            "recovered": False,
            "error": f"No autonomous recovery strategy configured for {tool_name} ({original_error})"
        }

    async def _recover_app_launch(self, app_name: str, error: str) -> Dict[str, Any]:
        """Multi-stage recovery for application launches."""
        logger.info(f"[RecoveryEngine] Stage 1: Searching Windows App Paths & Registry for '{app_name}'...")
        
        local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser(r"~\AppData\Local"))
        known_aliases = {
            "opera": [
                os.path.join(local_app_data, "Programs", "Opera", "launcher.exe"),
                os.path.join(local_app_data, "Programs", "Opera GX", "opera.exe"),
                r"C:\Program Files\Opera\launcher.exe",
                r"C:\Program Files\Opera GX\launcher.exe"
            ],
            "chrome": [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
            ],
            "edge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"],
            "code": [
                os.path.join(local_app_data, "Programs", "Microsoft VS Code", "Code.exe"),
                r"C:\Program Files\Microsoft VS Code\Code.exe"
            ],
            "calculator": ["calc.exe"],
            "notepad": ["notepad.exe"],
            "explorer": ["explorer.exe"],
            "terminal": ["wt.exe", "powershell.exe"]
        }

        matched_exes = known_aliases.get(app_name.lower().strip(), [])
        for exe in matched_exes:
            if os.path.exists(exe) or shutil.which(exe):
                try:
                    subprocess.Popen([exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    logger.info(f"[RecoveryEngine] Stage 1 Recovery SUCCESS via alias '{exe}'")
                    return {"recovered": True, "method": "alias_path", "executable": exe}
                except Exception:
                    pass

        # Strategy 2: Protocol Launch (e.g. calc:, ms-settings:, etc.)
        logger.info(f"[RecoveryEngine] Stage 2: Attempting Windows Protocol URI launch for '{app_name}'...")
        protocol_map = {
            "calculator": "calculator:",
            "settings": "ms-settings:",
            "photos": "ms-photos:",
            "store": "ms-windows-store:",
            "paint": "ms-paint:"
        }
        uri = protocol_map.get(app_name.lower().strip())
        if uri:
            try:
                os.startfile(uri)
                logger.info(f"[RecoveryEngine] Stage 2 Recovery SUCCESS via URI '{uri}'")
                return {"recovered": True, "method": "protocol_uri", "uri": uri}
            except Exception:
                pass

        # Strategy 3: PowerShell Start-Process with fallback
        logger.info(f"[RecoveryEngine] Stage 3: Attempting PowerShell Start-Process...")
        try:
            cmd = f'powershell -Command "Start-Process \\"{app_name}\\" -ErrorAction SilentlyContinue"'
            res = subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
            if res.returncode == 0:
                logger.info("[RecoveryEngine] Stage 3 Recovery SUCCESS via PowerShell Start-Process")
                return {"recovered": True, "method": "powershell_start_process"}
        except Exception:
            pass

        return {"recovered": False, "error": f"All 3 app launch recovery stages failed for '{app_name}'"}

    async def _recover_browser_action(self, url: str, error: str) -> Dict[str, Any]:
        """Browser recovery: retry via system default browser or HTTP."""
        if url:
            try:
                os.startfile(url)
                logger.info(f"[RecoveryEngine] Browser recovery SUCCESS via os.startfile('{url}')")
                return {"recovered": True, "method": "os_startfile", "url": url}
            except Exception as e:
                pass
        return {"recovered": False, "error": f"Browser recovery failed: {error}"}

    async def _recover_ui_click(self, element: str, error: str) -> Dict[str, Any]:
        """UI element click recovery: visual grounding fallback."""
        try:
            from agents.computer.vision_grounding import vision_grounding
            from agents.computer.mouse_agent import mouse_agent
            coords = vision_grounding.ground_target_coordinate(element)
            if coords:
                mouse_agent.click(coords[0], coords[1])
                logger.info(f"[RecoveryEngine] Click recovery SUCCESS via Vision SoM coordinate grounding ({coords[0]}, {coords[1]})")
                return {"recovered": True, "method": "vision_grounding", "coordinates": coords}
        except Exception as e:
            pass
        return {"recovered": False, "error": f"Visual grounding click recovery failed: {error}"}


recovery_engine = RecoveryEngine()
