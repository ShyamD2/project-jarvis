"""
J.A.R.V.I.S. Emergency STOP & Abort Framework.
Provides instant vocal kill-switch ('STOP', 'CANCEL', 'ABORT') and global physical hotkey (CTRL + SHIFT + J).
Immediately halts mouse/keyboard automation, compound workflows, and revokes active tokens.
"""

import sys
import threading
import time
from typing import Dict, Any, Callable, List
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.config import config
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.schemas.event_envelope import JarvisEvent

logger = get_logger("JarvisEmergencyStop")


class EmergencyStopController:
    def __init__(self):
        self._stop_event = threading.Event()
        self._registered_cancellation_callbacks: List[Callable[[], None]] = []
        self._hotkey_thread: threading.Thread | None = None
        self._is_listening_hotkey = False

        # Start global hotkey listener
        self.start_hotkey_listener()

    @property
    def is_stopped(self) -> bool:
        return self._stop_event.is_set() or config.emergency_stand_down

    def register_cancellation_hook(self, callback: Callable[[], None]):
        """Registers a callback that will be called immediately when emergency stop triggers"""
        self._registered_cancellation_callbacks.append(callback)

    def trigger_emergency_stop(self, source: str = "vocal_command", reason: str = "User requested immediate halt") -> Dict[str, Any]:
        """
        EMERGENCY KILL-SWITCH:
        Instantly flags emergency stop, invokes all cancellation callbacks, and notifies event mesh.
        """
        logger.critical(f"🛑 [EMERGENCY STOP TRIGGERED] Source: {source} | Reason: {reason}")
        self._stop_event.set()
        config.emergency_stand_down = True

        # Run registered cancellation callbacks (e.g., abort mouse/keyboard loops, cancel async tasks)
        for cb in self._registered_cancellation_callbacks:
            try:
                cb()
            except Exception as e:
                logger.error(f"Error in emergency cancellation callback: {e}")

        # Broadcast event across mesh
        event = JarvisEvent(
            source="emergency.controller",
            type="system.emergency_stand_down",
            data={
                "source": source,
                "reason": reason,
                "timestamp": time.time(),
                "status": "HALTED"
            }
        )
        try:
            mesh.publish(event)
        except Exception as e:
            logger.warning(f"Failed to publish emergency stop event to mesh: {e}")

        return {
            "status": "halted",
            "emergency_stand_down": True,
            "source": source,
            "message": "All autonomous operations, automation loops, and pending workflows have been aborted immediately, sir."
        }

    def resume_operations(self) -> Dict[str, Any]:
        """Resets emergency flags and resumes normal operations"""
        self._stop_event.clear()
        config.emergency_stand_down = False
        logger.info("Emergency stand-down lifted. Normal operations restored.")

        event = JarvisEvent(
            source="emergency.controller",
            type="system.operations_resumed",
            data={"timestamp": time.time(), "status": "OPERATIONAL"}
        )
        try:
            mesh.publish(event)
        except Exception:
            pass

        return {
            "status": "operational",
            "emergency_stand_down": False,
            "message": "Operations resumed, sir. Ready for instructions."
        }

    lift_emergency_stop = resume_operations

    def start_hotkey_listener(self):
        """Starts background daemon thread monitoring for physical hotkey: CTRL + SHIFT + J"""
        if self._is_listening_hotkey or sys.platform != "win32":
            return

        self._is_listening_hotkey = True
        self._hotkey_thread = threading.Thread(target=self._hotkey_worker, daemon=True, name="JarvisHotkeyListener")
        self._hotkey_thread.start()
        logger.info("Physical emergency hotkey listener started (CTRL + SHIFT + J)")

    def _hotkey_worker(self):
        """
        Polls Windows GetAsyncKeyState for CTRL (0x11), SHIFT (0x10), and 'J' (0x4A).
        Lightweight, non-intrusive, zero-dependency low-level polling every 50ms.
        """
        try:
            import ctypes
            user32 = ctypes.windll.user32
            VK_CONTROL = 0x11
            VK_SHIFT = 0x10
            VK_J = 0x4A

            while self._is_listening_hotkey:
                # Check if Ctrl, Shift, and J are all down
                ctrl_down = bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
                shift_down = bool(user32.GetAsyncKeyState(VK_SHIFT) & 0x8000)
                j_down = bool(user32.GetAsyncKeyState(VK_J) & 0x8000)

                if ctrl_down and shift_down and j_down:
                    logger.critical("[HOTKEY] CTRL + SHIFT + J detected! Triggering Emergency Stop.")
                    self.trigger_emergency_stop(source="physical_hotkey", reason="Pressed CTRL + SHIFT + J")
                    # Debounce
                    time.sleep(1.0)

                time.sleep(0.05)
        except Exception as e:
            logger.warning(f"Error in emergency hotkey worker: {e}")


emergency_stop = EmergencyStopController()
