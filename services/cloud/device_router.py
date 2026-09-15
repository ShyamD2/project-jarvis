"""
Cross-Device Task Router for J.A.R.V.I.S. Cloud.
Decides WHAT needs to happen and WHERE:
- Extracts target device and intent from natural language or tool calls.
- Validates target device availability and dynamic capabilities.
- Enforces Rule 14: Truthful offline reporting (never fakes success).
- Dispatches AgentTaskPacket to the appropriate platform agent.
"""

from __future__ import annotations
import os
import sys
import re
from typing import Dict, Any, Tuple, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.schemas.device_envelope import (
    AgentTaskPacket,
    AgentTaskResult,
    DeviceType,
    DeviceStatus,
    DeviceCapability
)
from services.cloud.device_registry import device_registry
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisDeviceRouter")


class DeviceRouter:
    def __init__(self, default_device_id: str = "desktop-shyam"):
        self.default_device_id = default_device_id

    def resolve_target_device(self, query: str) -> Tuple[str, str]:
        """
        Parses query to determine intended target device and cleaned command.
        Returns (target_device_id, cleaned_command).
        """
        q = query.strip()
        lower = q.lower()

        # Phone / Mobile detection
        if re.search(r"\b(on\s+(my\s+)?(phone|mobile|android))\b", lower):
            cleaned = re.sub(r"\b(on\s+(my\s+)?(phone|mobile|android))\b", "", q, flags=re.IGNORECASE).strip()
            return "mobile-shyam", cleaned

        # Laptop detection
        if re.search(r"\b(on\s+(my\s+)?laptop)\b", lower):
            cleaned = re.sub(r"\b(on\s+(my\s+)?laptop)\b", "", q, flags=re.IGNORECASE).strip()
            return "laptop-shyam", cleaned

        # Tablet detection
        if re.search(r"\b(on\s+(my\s+)?tablet)\b", lower):
            cleaned = re.sub(r"\b(on\s+(my\s+)?tablet)\b", "", q, flags=re.IGNORECASE).strip()
            return "tablet-shyam", cleaned

        # Desktop detection
        if re.search(r"\b(on\s+(my\s+)?(desktop|pc|computer))\b", lower):
            cleaned = re.sub(r"\b(on\s+(my\s+)?(desktop|pc|computer))\b", "", q, flags=re.IGNORECASE).strip()
            return "desktop-shyam", cleaned

        # Default to current primary desktop workstation
        return self.default_device_id, q

    def map_command_to_action(self, text: str) -> Tuple[str, Dict[str, Any], DeviceCapability]:
        """Maps natural language command to action, parameters, and required capability."""
        t = text.lower().strip()

        # 1. App Launching (e.g. Opera, WhatsApp, Spotify, VS Code)
        m_launch = re.search(r"\b(open|launch|start|run)\s+([a-zA-Z0-9_\-\s]+)", t)
        if m_launch:
            app_raw = m_launch.group(2).strip()
            app_name = re.sub(r"\b(app|application|program)\b", "", app_raw).strip()
            return "open_app", {"app_name": app_name}, DeviceCapability.APP_LAUNCH

        # 2. App Termination
        m_close = re.search(r"\b(close|kill|terminate|shut\s+down)\s+([a-zA-Z0-9_\-\s]+)", t)
        if m_close:
            app_name = m_close.group(2).strip()
            return "close_app", {"app_name": app_name}, DeviceCapability.APP_TERMINATE

        # 3. Volume Controls
        if "volume" in t or "sound" in t or "mute" in t or "unmute" in t:
            if "mute" in t and "unmute" not in t:
                return "set_volume", {"action": "mute"}, DeviceCapability.VOLUME_CONTROL
            elif "unmute" in t:
                return "set_volume", {"action": "unmute"}, DeviceCapability.VOLUME_CONTROL
            elif any(w in t for w in ["increase", "raise", "up", "louder"]):
                return "set_volume", {"action": "increase", "steps": 5}, DeviceCapability.VOLUME_CONTROL
            elif any(w in t for w in ["decrease", "lower", "down", "quieter"]):
                return "set_volume", {"action": "decrease", "steps": 5}, DeviceCapability.VOLUME_CONTROL
            m_vol = re.search(r"(\d{1,3})%?", t)
            if m_vol:
                return "set_volume", {"action": "set", "level": int(m_vol.group(1))}, DeviceCapability.VOLUME_CONTROL
            return "set_volume", {"action": "set", "level": 50}, DeviceCapability.VOLUME_CONTROL

        # 4. Web Browsing
        m_web = re.search(r"\b(browse|search\s+for|google|open\s+website)\s+(.+)", t)
        if m_web:
            return "browse_url", {"url": f"https://www.google.com/search?q={m_web.group(2).strip()}"}, DeviceCapability.BROWSER_CONTROL

        # 5. Telephony / Calls (Mobile)
        if any(w in t for w in ["call", "dial", "phone call"]):
            m_contact = re.search(r"\b(call|dial)\s+([a-zA-Z0-9_\-\s]+)", t)
            contact = m_contact.group(2).strip() if m_contact else "specified contact"
            return "make_call", {"contact": contact}, DeviceCapability.CALLS

        # 6. Messaging / SMS (Mobile)
        if any(w in t for w in ["send sms", "send text", "message", "text "]):
            return "send_sms", {"text": text}, DeviceCapability.MESSAGES

        # 7. Notifications (Mobile)
        if "notification" in t:
            return "check_notifications", {}, DeviceCapability.NOTIFICATIONS

        # 8. Screen Recognition & Visual Analysis
        screen_triggers = ["recognize screen", "analyze screen", "what is on my screen", "what's on my screen", "read screen", "look at screen", "check screen", "inspect screen", "see my screen", "recognise screen", "analyse screen"]
        if any(trig in t for trig in screen_triggers) or ("screen" in t and any(w in t for w in ["what", "recognize", "recognise", "analyze", "analyse", "read", "inspect", "look at"])):
            return "recognize_screen", {}, DeviceCapability.SCREEN_RECOGNITION

        # 9. Keyboard Typing & Text Input
        m_type = re.search(r"^(?:type|write|input)\s+['\"]?(.+?)['\"]?(?:\s+in\s+([a-zA-Z0-9_\-\s]+))?$", text.strip(), re.IGNORECASE)
        if m_type:
            typed_content = m_type.group(1).strip()
            target_app = m_type.group(2).strip() if m_type.group(2) else None
            return "type_text", {"text": typed_content, "target_app": target_app}, DeviceCapability.KEYBOARD_INPUT

        # 10. Key Press & Hotkeys (e.g. Enter, Space, Ctrl+C)
        m_press = re.search(r"^(?:press|hit)\s+([a-zA-Z0-9_\+\-\s]+)$", text.strip(), re.IGNORECASE)
        if m_press:
            key_name = m_press.group(1).strip()
            return "press_key", {"key": key_name}, DeviceCapability.KEYBOARD_INPUT

        # 11. Camera / Photography (Mobile / Desktop)
        if any(w in t for w in ["take a photo", "take photo", "capture photo", "snap photo"]):
            return "take_photo", {}, DeviceCapability.CAMERA

        # 12. Workstation Lock
        if "lock" in t and any(w in t for w in ["screen", "pc", "workstation", "computer"]):
            return "lock_workstation", {}, DeviceCapability.SYSTEM_POWER

        # 13. Clipboard Diagnosis
        if "clipboard" in t or "copied error" in t:
            return "diagnose_clipboard", {}, DeviceCapability.CLIPBOARD_SYNC

        # Fallback to app launch
        return "open_app", {"app_name": text}, DeviceCapability.APP_LAUNCH

    async def route_and_execute(self, query: str, source_device_id: str = "cloud") -> Dict[str, Any]:
        """
        End-to-end routing pipeline:
        1. Resolve intended target device.
        2. Verify device existence & online state (Rule 14).
        3. Verify device capability (Rule 5).
        4. Construct AgentTaskPacket.
        5. Dispatch to device agent.
        """
        target_device_id, cleaned_cmd = self.resolve_target_device(query)
        logger.info(f"🎯 [DeviceRouter] Routing query='{query}' -> Target='{target_device_id}' Command='{cleaned_cmd}'")

        dev = device_registry.get_device(target_device_id)
        if not dev:
            return {
                "success": False,
                "status": "UNKNOWN_DEVICE",
                "message": f"Target device '{target_device_id}' is not registered in your authorized fleet, sir."
            }

        # Rule 14: Truthful Offline Recovery (Never fake success if offline)
        if dev.status != DeviceStatus.ONLINE:
            logger.warning(f"🔌 [DeviceRouter] Target '{dev.name}' is {dev.status.value}. Halting execution.")
            return {
                "success": False,
                "status": "DEVICE_OFFLINE",
                "device_id": dev.device_id,
                "device_name": dev.name,
                "message": f"Sir, {dev.name} is currently offline, so I am unable to perform that action."
            }

        # Determine action & capability
        action, params, required_cap = self.map_command_to_action(cleaned_cmd)

        # Rule 5: Dynamic capability verification (Never send unsupported command)
        if required_cap not in dev.capabilities:
            logger.warning(f"⚠️ [DeviceRouter] Device '{dev.name}' lacks capability '{required_cap.value}'")
            return {
                "success": False,
                "status": "UNSUPPORTED_CAPABILITY",
                "device_id": dev.device_id,
                "device_name": dev.name,
                "message": f"Sir, {dev.name} does not support {required_cap.value.replace('_', ' ')}."
            }

        # Create AgentTaskPacket
        packet = AgentTaskPacket(
            action=action,
            target_device_id=target_device_id,
            source_device_id=source_device_id,
            parameters=params
        )

        # Dispatch based on target platform
        if dev.device_type in [DeviceType.DESKTOP, DeviceType.LAPTOP]:
            # Windows Computer Agent Execution
            try:
                from services.device_agents.windows.windows_device_agent import windows_device_agent
                # In-process or socket dispatch
                result: AgentTaskResult = await windows_device_agent.execute_task(packet)
                msg = f"Executed '{action}' on {dev.name}, sir."
                if isinstance(result.result, dict) and result.result.get("message"):
                    msg = result.result["message"]
                elif not result.success:
                    msg = f"Failed to execute on {dev.name}: {result.error}"

                return {
                    "success": result.success,
                    "status": result.status,
                    "target_device": dev.name,
                    "action": action,
                    "duration_ms": result.duration_ms,
                    "message": msg,
                    "details": result.result
                }
            except Exception as e:
                logger.error(f"[DeviceRouter] Windows execution error: {e}")
                return {
                    "success": False,
                    "status": "EXECUTION_ERROR",
                    "target_device": dev.name,
                    "message": f"Error executing task on {dev.name}: {e}"
                }

        elif dev.device_type == DeviceType.MOBILE:
            # Android / Mobile Agent Execution
            try:
                from services.device_agents.mobile.mobile_device_agent import mobile_device_agent
                result: AgentTaskResult = await mobile_device_agent.execute_task(packet)
                return {
                    "success": result.success,
                    "status": result.status,
                    "target_device": dev.name,
                    "action": action,
                    "duration_ms": result.duration_ms,
                    "message": f"Executed '{action}' on your phone, sir." if result.success else f"Failed on phone: {result.error}",
                    "details": result.result
                }
            except Exception as e:
                logger.error(f"[DeviceRouter] Mobile execution error: {e}")
                return {
                    "success": False,
                    "status": "EXECUTION_ERROR",
                    "target_device": dev.name,
                    "message": f"Error communicating with your phone: {e}"
                }

        return {
            "success": False,
            "status": "UNSUPPORTED_DEVICE_TYPE",
            "message": f"Device type '{dev.device_type.value}' handler not yet attached."
        }


device_router = DeviceRouter()
