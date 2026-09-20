"""
Native Mobile / Android Device Agent for Project J.A.R.V.I.S.
Runs as the device execution agent on mobile devices (or through mobile bridge):
- Mobile Applications (WhatsApp, Instagram, Camera, Settings, Phone)
- Notifications & Messages
- Voice Calls & Contact Dialing
- Media & Volume
"""

from __future__ import annotations
import os
import sys
import shutil
import subprocess
import time
from typing import Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.schemas.device_envelope import AgentTaskPacket, AgentTaskResult
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("MobileDeviceAgent")


class MobileDeviceAgent:
    def __init__(self, device_id: str = "mobile-shyam"):
        self.device_id = device_id
        logger.info(f"📱 [MobileDeviceAgent] Mobile Device Agent initialized for '{self.device_id}'")

    async def execute_task(self, packet: AgentTaskPacket) -> AgentTaskResult:
        """
        Executes an incoming task packet on the mobile device.
        Decides HOW to safely perform the action on Android/Mobile.
        """
        start_time = time.time()
        action = packet.action.lower().strip()
        params = packet.parameters or {}
        logger.info(f"📱 [MobileDeviceAgent] Received mobile task '{packet.task_id}': action='{action}'")

        try:
            # Verify physical connectivity / ADB bridge availability
            adb_bin = shutil.which("adb")
            target_ip = os.getenv("ANDROID_DEVICE_IP", "")
            
            # 1. OPEN MOBILE APPLICATION (e.g. WhatsApp, Instagram, Camera)
            if action in ["open_app", "launch_app"]:
                app_name = params.get("app_name", "").strip().lower()
                logger.info(f"📱 [MobileDeviceAgent] Requesting mobile app launch: '{app_name}'")

                if adb_bin:
                    # Attempt real launch via adb if device available
                    pkg_map = {
                        "whatsapp": "com.whatsapp",
                        "instagram": "com.instagram.android",
                        "camera": "com.android.camera",
                        "settings": "com.android.settings",
                        "chrome": "com.android.chrome"
                    }
                    pkg = pkg_map.get(app_name, app_name)
                    cmd = [adb_bin, "shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if res.returncode == 0:
                        duration = (time.time() - start_time) * 1000
                        return AgentTaskResult(
                            task_id=packet.task_id,
                            device_id=self.device_id,
                            success=True,
                            status="COMPLETED",
                            result={"action": "open_app", "app_name": app_name, "dispatched_via": "adb"},
                            duration_ms=round(duration, 2)
                        )

                # If no ADB bridge or device unreachable, report truthfully
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=False,
                    status="DEVICE_UNPAIRED",
                    error=f"Cannot open '{app_name}' on phone: Android device '{self.device_id}' is not connected via ADB or local bridge.",
                    duration_ms=round(duration, 2)
                )

            # 2. CHECK NOTIFICATIONS
            elif action in ["check_notifications", "notifications"]:
                duration = (time.time() - start_time) * 1000
                if adb_bin:
                    # Real dumpsys notification query
                    res = subprocess.run([adb_bin, "shell", "dumpsys", "notification", "--noredact"], capture_output=True, text=True, timeout=5)
                    if res.returncode == 0:
                        return AgentTaskResult(
                            task_id=packet.task_id,
                            device_id=self.device_id,
                            success=True,
                            status="COMPLETED",
                            result={"raw_telemetry": res.stdout[:500]},
                            duration_ms=round(duration, 2)
                        )

                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=False,
                    status="DEVICE_UNPAIRED",
                    error="Phone is currently unreachable to fetch notifications.",
                    duration_ms=round(duration, 2)
                )

            # 3. SEND MESSAGE
            elif action in ["send_message", "message"]:
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=False,
                    status="DEVICE_UNPAIRED",
                    error="Mobile message dispatch requires an active paired Android bridge.",
                    duration_ms=round(duration, 2)
                )

            # 4. PHONE CALL / DIAL CONTACT
            elif action in ["call_contact", "call"]:
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=False,
                    status="DEVICE_UNPAIRED",
                    error="Phone call execution requires paired mobile telephony bridge.",
                    duration_ms=round(duration, 2)
                )

            # 5. CAMERA
            elif action in ["camera", "open_camera"]:
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=False,
                    status="DEVICE_UNPAIRED",
                    error="Mobile camera remote control requires active ADB session.",
                    duration_ms=round(duration, 2)
                )

            # UNKNOWN ACTION
            else:
                duration = (time.time() - start_time) * 1000
                return AgentTaskResult(
                    task_id=packet.task_id,
                    device_id=self.device_id,
                    success=False,
                    status="FAILED",
                    error=f"Mobile Agent does not support action '{action}'",
                    duration_ms=round(duration, 2)
                )

        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"[MobileDeviceAgent] Error executing mobile task: {e}")
            return AgentTaskResult(
                task_id=packet.task_id,
                device_id=self.device_id,
                success=False,
                status="FAILED",
                error=str(e),
                duration_ms=round(duration, 2)
            )


mobile_device_agent = MobileDeviceAgent(device_id="mobile-shyam")
