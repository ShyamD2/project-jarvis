"""
Remote Workstation Unlocker for Project J.A.R.V.I.S.
Enables remote lock-screen bypass via Telegram / mobile commands.
"""

from __future__ import annotations
import os
import sys
import time
import ctypes
from typing import Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisRemoteUnlocker")


class WindowsUnlocker:
    def __init__(self):
        self._user32 = ctypes.windll.user32 if sys.platform == "win32" else None

    def is_locked(self) -> bool:
        """Determines if the Windows workstation is currently locked or displaying lock screen."""
        if not self._user32:
            return False

        try:
            h_desk = self._user32.OpenInputDesktop(0, False, 0x01FF)
            if not h_desk:
                return True

            buf = ctypes.create_unicode_buffer(256)
            needed = ctypes.c_ulong(0)
            self._user32.GetUserObjectInformationW(h_desk, 2, buf, 256, ctypes.byref(needed))
            desk_name = buf.value.lower()
            self._user32.CloseDesktop(h_desk)

            if desk_name != "default":
                return True
        except Exception as e:
            logger.debug(f"[Unlocker] Desktop query notice: {e}")

        try:
            from agents.computer.windows_agent import windows_agent
            win_info = windows_agent.get_active_window_info()
            proc = win_info.get("process", "").lower()
            if proc in ["lockapp.exe", "logonui.exe"]:
                return True
        except Exception:
            pass

        return False

    def wake_screen(self):
        """Wakes up the monitor and moves mouse slightly."""
        if not self._user32:
            return
        try:
            self._user32.SendMessageW(0xFFFF, 0x0112, 0xF170, -1)
            self._user32.mouse_event(0x0001, 0, 1, 0, 0)
            time.sleep(0.05)
            self._user32.mouse_event(0x0001, 0, -1, 0, 0)
        except Exception as e:
            logger.debug(f"[Unlocker] Wake screen notice: {e}")

    def _attach_input_desktop(self) -> bool:
        """Binds calling thread to active input desktop."""
        if not self._user32:
            return False
        try:
            h_desk = self._user32.OpenInputDesktop(0, False, 0x01FF)
            if h_desk:
                self._user32.SetThreadDesktop(h_desk)
                self._user32.CloseDesktop(h_desk)
                return True
        except Exception:
            pass
        return False

    def _send_key(self, vk: int, down: bool = True):
        if self._user32:
            flags = 0 if down else 2
            self._user32.keybd_event(vk, 0, flags, 0)

    def _type_char(self, char: str):
        if not self._user32:
            return
        res = self._user32.VkKeyScanW(ord(char))
        if res == -1:
            return
        vk = res & 0xFF
        shift = bool((res >> 8) & 1)
        ctrl = bool((res >> 8) & 2)
        alt = bool((res >> 8) & 4)

        if shift: self._send_key(0x10, True)
        if ctrl: self._send_key(0x11, True)
        if alt: self._send_key(0x12, True)

        self._send_key(vk, True)
        time.sleep(0.02)
        self._send_key(vk, False)

        if alt: self._send_key(0x12, False)
        if ctrl: self._send_key(0x11, False)
        if shift: self._send_key(0x10, False)
        time.sleep(0.03)

    async def unlock(self, pin_or_password: str) -> Dict[str, Any]:
        if not self._user32:
            return {"success": False, "error": "Win32 subsystem unavailable."}

        logger.info("🔓 [Unlocker] Remote unlock sequence initiated.")

        # 1. Wake physical display
        self.wake_screen()
        time.sleep(0.4)

        # 2. Attach desktop
        self._attach_input_desktop()

        # 3. Dismiss lock screen overlay: click center & send Space + Enter
        try:
            # Click center of screen to prompt password field
            w = self._user32.GetSystemMetrics(0)
            h = self._user32.GetSystemMetrics(1)
            self._user32.SetCursorPos(w // 2, h // 2)
            time.sleep(0.05)
            self._user32.mouse_event(0x0002, 0, 0, 0, 0) # Left down
            time.sleep(0.02)
            self._user32.mouse_event(0x0004, 0, 0, 0, 0) # Left up
        except Exception:
            pass

        # Send Space to trigger PIN prompt animation
        self._send_key(0x20, True)
        time.sleep(0.05)
        self._send_key(0x20, False)

        # Generous wait for Windows 11 lock screen slide animation to complete and focus input box
        time.sleep(1.4)
        self._attach_input_desktop()

        # Clear any stray characters already in PIN box
        for _ in range(4):
            self._send_key(0x08, True) # Backspace
            time.sleep(0.02)
            self._send_key(0x08, False)
            time.sleep(0.02)

        # 4. Type credentials cleanly
        for ch in pin_or_password:
            self._type_char(ch)
            time.sleep(0.03)

        # 5. Submit with Enter
        time.sleep(0.25)
        self._send_key(0x0D, True)
        time.sleep(0.05)
        self._send_key(0x0D, False)

        # 6. Wait for logon session transition
        time.sleep(2.0)

        # 7. Verify unlock state
        still_locked = self.is_locked()

        # 8. Capture confirmation screenshot
        screenshot_path = None
        try:
            from agents.computer.screen_agent import screen_agent
            snap = screen_agent.capture_screenshot()
            if snap.get("success"):
                screenshot_path = snap.get("screenshot_path")
        except Exception as e:
            logger.debug(f"[Unlocker] Post-unlock snapshot notice: {e}")

        if not still_locked:
            logger.info("✅ [Unlocker] Workstation unlocked successfully.")
            return {
                "success": True,
                "message": "Workstation unlocked successfully, sir.",
                "screenshot_path": screenshot_path
            }
        else:
            logger.warning("⚠️ [Unlocker] Workstation may still be locked.")
            return {
                "success": False,
                "error": "Workstation credential prompt did not complete or Windows Winlogon security is blocking user-space keystrokes. Use '🌙 Stealth Screen Off' mode to keep workstation accessible with zero password friction!",
                "screenshot_path": screenshot_path
            }


remote_unlocker = WindowsUnlocker()
