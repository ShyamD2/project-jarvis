"""
Native Windows Computer Agent for Project J.A.R.V.I.S.
Runs on Windows PC/Laptop and decides HOW to safely execute actions locally:
- OS & Applications (Opera, VS Code, Terminal, Spotify, Calculator, Notepad)
- Browser Automation & Web Navigation
- System Audio & Master Volume
- Active Window Focus & Virtual Desktop
- File System & Screenshots
"""

from __future__ import annotations
import os
import sys
import time
import asyncio
from typing import Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "agents"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/pc-agent"))

from shared.schemas.device_envelope import AgentTaskPacket, AgentTaskResult
from shared.sdk_python.jarvis_sdk.logger import get_logger

# Import local native agents
from agents.computer.windows_agent import windows_agent
from agents.computer.audio_agent import audio_agent
from agents.computer.power_agent import power_agent
from agents.computer.screen_agent import screen_agent
from agents.computer.keyboard_agent import keyboard_agent
from agents.intelligence.safety_guard import safety_guard

try:
    from system_control import system_control
    from system_monitor import system_monitor
except ImportError:
    from services.pc_agent.system_control import system_control
    from services.pc_agent.system_monitor import system_monitor

logger = get_logger("WindowsDeviceAgent")


class WindowsDeviceAgent:
    def __init__(self, device_id: str = "desktop-shyam"):
        self.device_id = device_id
        logger.info(f"💻 [WindowsDeviceAgent] Native Windows Agent initialized for '{self.device_id}'")

    async def execute_task(self, packet: AgentTaskPacket) -> AgentTaskResult:
        """
        Executes an incoming AgentTaskPacket on the Windows host.
        Decides HOW to safely and reliably execute the action on Windows.
        """
        start_time = time.time()
        action = packet.action.lower().strip()
        params = packet.parameters or {}
        logger.info(f"💻 [WindowsDeviceAgent] Received task '{packet.task_id}': action='{action}'")

        try:
            # 1. APPLICATION LAUNCHING (e.g. Opera, VS Code, Spotify)
            if action in ["open_app", "launch_app"]:
                app_name = params.get("app_name") or params.get("name") or "opera"
                mode = params.get("mode", "auto")
                res = windows_agent.launch_app(app_name, mode=mode)
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=res.get("success", False),
                    status="COMPLETED" if res.get("success") else "FAILED",
                    result=res,
                    duration_ms=round(duration, 2)
                )

            # 2. APPLICATION TERMINATION
            elif action in ["close_app", "kill_app"]:
                app_name = params.get("app_name") or params.get("name") or "active"
                if app_name == "all":
                    res = windows_agent.close_all_user_apps()
                else:
                    res = windows_agent.close_active_window(app_name)
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=res.get("success", False),
                    status="COMPLETED" if res.get("success") else "FAILED",
                    result=res,
                    duration_ms=round(duration, 2)
                )

            # 3. MASTER VOLUME & AUDIO
            elif action in ["set_volume", "volume_control"]:
                level = params.get("level", 50)
                sub_act = params.get("action", "set")
                if sub_act == "mute":
                    res = audio_agent.mute()
                elif sub_act == "unmute":
                    res = audio_agent.unmute()
                elif sub_act == "increase":
                    steps = params.get("steps", 5)
                    res = audio_agent.increase_volume(steps)
                elif sub_act == "decrease":
                    steps = params.get("steps", 5)
                    res = audio_agent.decrease_volume(steps)
                else:
                    res = audio_agent.set_volume_percent(int(level))
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=res.get("success", False),
                    status="COMPLETED" if res.get("success") else "FAILED",
                    result=res,
                    duration_ms=round(duration, 2)
                )

            # 4. WEB BROWSER AUTOMATION & TABS
            elif action in ["browse_url", "open_url"]:
                url = params.get("url") or "https://www.google.com"
                res = windows_agent.open_url(url)
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=res.get("success", False),
                    status="COMPLETED" if res.get("success") else "FAILED",
                    result=res,
                    duration_ms=round(duration, 2)
                )

            # 5. ACTIVE WINDOW & SCREEN CONTEXT
            elif action in ["get_active_window", "active_window"]:
                win_info = windows_agent.get_active_window_info()
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=win_info.get("success", False),
                    status="COMPLETED",
                    result=win_info,
                    duration_ms=round(duration, 2)
                )

            # 6. FULL SCREEN RECOGNITION & VISUAL CONTEXT
            elif action in ["recognize_screen", "analyze_screen"]:
                sc_res = screen_agent.capture_screenshot()
                win_info = windows_agent.get_active_window_info()
                active_title = win_info.get("title", "Active Desktop Window")
                active_process = win_info.get("process", "Desktop")
                resolution = screen_agent.get_screen_resolution()
                
                # Format an intelligent, concise summary of screen state
                summary = f"Sir, I have recognized your screen. Active window is '{active_title}' ({active_process}) on display {resolution.get('width', 1536)}x{resolution.get('height', 864)}."
                if sc_res.get("screenshot_path"):
                    summary += f" Visual snapshot captured successfully."

                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=True,
                    status="COMPLETED",
                    result={
                        "message": summary,
                        "active_window": active_title,
                        "process": active_process,
                        "resolution": resolution,
                        "screenshot": sc_res.get("screenshot_path")
                    },
                    duration_ms=round(duration, 2)
                )

            # 7. KEYBOARD TYPING & TEXT INPUT
            elif action in ["type_text", "keyboard_input", "type"]:
                text_to_type = params.get("text", "")
                target_app = params.get("target_app")
                if target_app:
                    from agents.computer.windows_agent import focus_window_by_name
                    focus_window_by_name(target_app)
                    time.sleep(0.3)
                
                res = keyboard_agent.type_text(text_to_type)
                duration = (time.time() - start_time) * 1000
                target_desc = f" into {target_app}" if target_app else ""
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=res.get("success", False),
                    status="COMPLETED" if res.get("success") else "FAILED",
                    result={
                        "message": f"Typed '{text_to_type}'{target_desc}, sir.",
                        "typed_length": len(text_to_type),
                        "target_app": target_app
                    },
                    duration_ms=round(duration, 2)
                )

            # 8. KEY PRESS & HOTKEYS
            elif action in ["press_key", "hotkey"]:
                key_name = params.get("key", "enter").lower().strip()
                res = keyboard_agent.press_key(key_name)
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=res.get("success", False),
                    status="COMPLETED" if res.get("success") else "FAILED",
                    result={
                        "message": f"Pressed '{key_name}' key, sir.",
                        "key": key_name
                    },
                    duration_ms=round(duration, 2)
                )

            # 9. SCREEN CAPTURE & SURVEILLANCE
            elif action in ["screen_capture", "screenshot"]:
                sc_res = screen_agent.capture_screen_bytes()
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=sc_res.get("success", False),
                    status="COMPLETED" if sc_res.get("success") else "FAILED",
                    result={"path": sc_res.get("path")},
                    duration_ms=round(duration, 2)
                )

            # 10. SMART CLIPBOARD DIAGNOSTICS & SYNC
            elif action in ["diagnose_clipboard", "clipboard_sync"]:
                clip_res = await windows_agent.diagnose_clipboard_error()
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=clip_res.get("success", False),
                    status="COMPLETED" if clip_res.get("success") else "FAILED",
                    result=clip_res,
                    duration_ms=round(duration, 2)
                )

            # 11. WORKSTATION LOCK & POWER CONTROLS
            elif action == "lock_workstation":
                system_control.lock_workstation()
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=True,
                    status="COMPLETED",
                    result={"message": "Workstation locked successfully."},
                    duration_ms=round(duration, 2)
                )

            # UNKNOWN ACTION FOR WINDOWS AGENT
            else:
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=False,
                    status="FAILED",
                    error=f"Windows Agent does not support action: '{action}'",
                    duration_ms=round(duration, 2)
                )

        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"[WindowsDeviceAgent] Error executing task '{packet.task_id}': {e}")
            return AgentTaskResult(
                task_id=packet.task_id,
                device_id=self.device_id,
                success=False,
                status="FAILED",
                error=str(e),
                duration_ms=round(duration, 2)
            )

    async def recognize_screen(self) -> Dict[str, Any]:
        """Direct screen recognition capturing display snapshot and active window telemetry."""
        from agents.computer.screen_agent import screen_agent
        from agents.computer.windows_agent import windows_agent
        sc_res = screen_agent.capture_screenshot()
        win_info = windows_agent.get_active_window_info()
        active_title = win_info.get("title", "Active Desktop Window")
        active_process = win_info.get("process", "Desktop")
        resolution = screen_agent.get_screen_resolution()
        summary = f"Sir, I have recognized your screen. Active window is '{active_title}' ({active_process}) on display {resolution.get('width', 1536)}x{resolution.get('height', 864)}."
        return {
            "success": True,
            "message": summary,
            "active_window": active_title,
            "process": active_process,
            "resolution": resolution,
            "screenshot": sc_res.get("screenshot_path")
        }

    async def type_text(self, text: str, target_app: Optional[str] = None) -> Dict[str, Any]:
        """Direct typing into active window or focused application."""
        from agents.computer.keyboard_agent import keyboard_agent
        if target_app:
            from agents.computer.windows_agent import focus_window_by_name
            focus_window_by_name(target_app)
            time.sleep(0.3)
        res = keyboard_agent.type_text(text)
        return {
            "success": res.get("success", False),
            "message": f"Typed '{text}' into {target_app}, sir." if target_app else f"Typed '{text}', sir.",
            "typed_length": len(text),
            "target_app": target_app
        }


# Export singleton instance for desktop
windows_device_agent = WindowsDeviceAgent(device_id="desktop-shyam")
