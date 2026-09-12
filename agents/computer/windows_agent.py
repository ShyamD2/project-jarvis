"""
Windows Local Execution Agent for J.A.R.V.I.S.
Controls Windows applications, executes PowerShell commands, and manages workspace processes.
"""

import subprocess
import os
import sys
import shutil
import time
import psutil
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("WindowsAgent")


class WindowsAgent:
    def find_app_path(self, app_name: str) -> Optional[str]:
        """Dynamically locates exact executable path for desktop apps on Windows"""
        if not app_name:
            return None
        app_lower = app_name.lower().strip()

        # Check if already a valid absolute or relative path
        if os.path.isfile(app_name):
            return os.path.abspath(app_name)

        # 1. Opera / Opera GX paths
        if "opera" in app_lower:
            candidates = [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\launcher.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\opera.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Opera GX\opera.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Opera\launcher.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Opera GX\opera.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Opera\launcher.exe"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c

        # 2. Chrome
        if "chrome" in app_lower:
            candidates = [
                os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c

        # 3. Edge
        if "edge" in app_lower:
            candidates = [
                os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c

        # 4. VS Code
        if app_lower in ["code", "vscode"]:
            candidates = [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Microsoft VS Code\Code.exe"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c

        # 5. Common Alias Map
        alias_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "code": "code",
            "vscode": "code",
            "wt": "wt.exe",
            "terminal": "wt.exe",
            "explorer": "explorer.exe",
            "taskmgr": "taskmgr.exe",
            "mspaint": "mspaint.exe",
            "spotify": "spotify.exe",
            "discord": "discord.exe"
        }
        mapped_target = alias_map.get(app_lower, app_name)

        # 6. Resolve via system PATH using shutil.which
        resolved = shutil.which(mapped_target)
        if resolved:
            return resolved
        if not mapped_target.lower().endswith(".exe"):
            resolved = shutil.which(f"{mapped_target}.exe")
            if resolved:
                return resolved

        return None

    def launch_app(self, app_name: str, args: List[str] = None) -> Dict[str, Any]:
        """Launches a desktop application or process and verifies execution via psutil."""
        args = args or []
        app_lower = app_name.lower().strip()
        logger.info(f"[WindowsAgent] Launching application: {app_name} with args: {args}")

        target_path: Optional[str] = None

        # Check browser preference if generic browser requested
        if app_lower in ["browser", "web"]:
            try:
                from services.memory.feedback_learning import learner
                pref = learner.memory.get("preferences", {}).get("browser", "opera")
                target_path = self.find_app_path(pref)
            except Exception as e:
                logger.warning(f"[WindowsAgent] Could not resolve browser preference: {e}")

        # Support Windows App Protocols (Calendar, Settings)
        if app_lower in ["calendar", "ms-calendar", "ms-calendar:"]:
            try:
                os.startfile("ms-calendar:")
                logger.info("[WindowsAgent] Launched Windows Calendar via ms-calendar: protocol")
                return {
                    "success": True,
                    "app": "calendar",
                    "path": "ms-calendar:",
                    "pid": 0,
                    "status": "running",
                    "channel_1_logical": True
                }
            except Exception as pe:
                logger.warning(f"[WindowsAgent] Protocol launch error: {pe}")

        if app_lower in ["settings", "ms-settings", "ms-settings:"]:
            try:
                os.startfile("ms-settings:")
                logger.info("[WindowsAgent] Launched Windows Settings via ms-settings: protocol")
                return {
                    "success": True,
                    "app": "settings",
                    "path": "ms-settings:",
                    "pid": 0,
                    "status": "running",
                    "channel_1_logical": True
                }
            except Exception as pe:
                logger.warning(f"[WindowsAgent] Protocol launch error: {pe}")

        if not target_path:
            target_path = self.find_app_path(app_name)

        # If executable could not be resolved, FAIL EXPLICITLY. Never fake success!
        if not target_path or not os.path.exists(target_path):
            logger.error(f"[WindowsAgent] Target application '{app_name}' could not be located on host.")
            return {
                "success": False,
                "app": app_name,
                "status": "not_found",
                "error": f"Application '{app_name}' not found on host filesystem or PATH.",
                "channel_1_logical": False
            }

        try:
            cmd_args = [target_path] + [str(a) for a in args]
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

            proc = subprocess.Popen(
                cmd_args,
                shell=target_path.lower().endswith((".cmd", ".bat")),
                creationflags=creationflags
            )
            pid = proc.pid
            time.sleep(0.4)

            # Check if process exited immediately with error
            poll_code = proc.poll()
            if poll_code is not None and poll_code != 0:
                logger.error(f"[WindowsAgent] Process '{app_name}' exited immediately with code {poll_code}")
                return {
                    "success": False,
                    "app": app_name,
                    "path": target_path,
                    "pid": pid,
                    "status": "failed",
                    "error": f"Process exited immediately with code {poll_code}",
                    "channel_1_logical": False
                }

            # Verify running via psutil
            if psutil.pid_exists(pid):
                p = psutil.Process(pid)
                if p.status() != psutil.STATUS_ZOMBIE:
                    logger.info(f"[WindowsAgent] Process '{app_name}' confirmed active (PID: {pid})")
                    return {
                        "success": True,
                        "app": app_name,
                        "path": target_path,
                        "pid": pid,
                        "status": "running",
                        "channel_1_logical": True
                    }

            return {
                "success": False,
                "app": app_name,
                "path": target_path,
                "pid": pid,
                "status": "terminated",
                "error": "Process terminated immediately after launch.",
                "channel_1_logical": False
            }

        except Exception as e:
            logger.error(f"[WindowsAgent] Error launching {app_name} from {target_path}: {e}")
            return {
                "success": False,
                "app": app_name,
                "path": target_path,
                "status": "error",
                "error": str(e),
                "channel_1_logical": False
            }

    def execute_powershell(self, script: str) -> Dict[str, Any]:
        """Executes a PowerShell scriptlet safely"""
        logger.info(f"[WindowsAgent] Executing PowerShell: {script[:60]}...")
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                timeout=15
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
                "channel_1_logical": result.returncode == 0
            }
        except Exception as e:
            logger.error(f"[WindowsAgent] PowerShell execution error: {e}")
            return {
                "success": False,
                "error": str(e),
                "channel_1_logical": False
            }

    def verify_process_running(self, process_name: str) -> bool:
        """Verifies if a target process name is currently running via psutil"""
        proc_lower = process_name.lower().replace(".exe", "").strip()
        try:
            for p in psutil.process_iter(['name']):
                p_name = p.info.get('name')
                if p_name and p_name.lower().replace(".exe", "").strip() == proc_lower:
                    return True
        except Exception as e:
            logger.error(f"[WindowsAgent] Error checking process {process_name}: {e}")
        return False


windows_agent = WindowsAgent()
