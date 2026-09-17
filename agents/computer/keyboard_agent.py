"""
J.A.R.V.I.S. Keyboard Control Agent (Computer Pillar).
Handles text typing, individual key presses, and multi-key shortcuts using Win32 API.
Integrated with Emergency Stop abort checks.
"""

import sys
import time
import ctypes
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisKeyboardAgent")


class KeyboardAgent:
    def __init__(self):
        self._user32 = ctypes.windll.user32 if sys.platform == "win32" else None

        # Virtual Key Codes
        self.VK_MAP = {
            "ctrl": 0x11, "control": 0x11,
            "shift": 0x10,
            "alt": 0x12,
            "win": 0x5B, "windows": 0x5B,
            "esc": 0x1B, "escape": 0x1B,
            "enter": 0x0D, "return": 0x0D,
            "space": 0x20,
            "tab": 0x09,
            "backspace": 0x08,
            "delete": 0x2E, "del": 0x2E,
            "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
            "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
            "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
            "f11": 0x7A, "f12": 0x7B
        }

    def _ensure_desktop(self):
        """Attaches calling thread to active input desktop to prevent ERROR_ACCESS_DENIED (Error 5)"""
        if not self._user32:
            return
        try:
            hdesk = self._user32.OpenInputDesktop(0, False, 0x01FF)
            if hdesk:
                self._user32.SetThreadDesktop(hdesk)
                self._user32.CloseDesktop(hdesk)
        except Exception:
            pass

    def _check_emergency(self) -> bool:
        try:
            from agents.intelligence.emergency_stop import emergency_stop
            return emergency_stop.is_stopped
        except Exception:
            return False

    def _key_down(self, vk: int):
        if self._user32:
            self._ensure_desktop()
            self._user32.keybd_event(vk, 0, 0, 0)

    def _key_up(self, vk: int):
        if self._user32:
            self._ensure_desktop()
            self._user32.keybd_event(vk, 0, 2, 0) # 2 = KEYEVENTF_KEYUP

    def press_shortcut(self, keys: List[str]) -> Dict[str, Any]:
        """
        Executes a simultaneous key combination, e.g. ['ctrl', 'shift', 'esc'], ['win', 'd'], ['alt', 'tab']
        """
        if self._check_emergency():
            return {"success": False, "status": "aborted_by_emergency_stop"}

        if not self._user32:
            return {"success": False, "error": "Win32 unavailable"}

        vk_sequence = []
        for k in keys:
            k_clean = k.lower().strip()
            if k_clean in self.VK_MAP:
                vk_sequence.append(self.VK_MAP[k_clean])
            elif len(k_clean) == 1:
                # ASCII char virtual key code
                vk_sequence.append(ord(k_clean.upper()))

        logger.info(f"[KeyboardAgent] Executing shortcut: {keys} -> VK: {vk_sequence}")

        # Press all down in order
        for vk in vk_sequence:
            self._key_down(vk)
            time.sleep(0.02)

        time.sleep(0.05)

        # Release all in reverse order
        for vk in reversed(vk_sequence):
            self._key_up(vk)
            time.sleep(0.02)

        return {"success": True, "shortcut": keys}

    def type_text(self, text: str, delay: float = 0.01) -> Dict[str, Any]:
        """Types text character by character using SendInput / VkKeyScan"""
        if self._check_emergency():
            return {"success": False, "status": "aborted_by_emergency_stop"}

        if not self._user32:
            return {"success": False, "error": "Win32 unavailable"}

        logger.info(f"[KeyboardAgent] Typing text: '{text[:20]}...' (length: {len(text)})")

        for char in text:
            if self._check_emergency():
                return {"success": False, "status": "aborted_by_emergency_stop"}

            # Use SendInput or VkKeyScan for ASCII characters
            vk = self._user32.VkKeyScanW(ord(char))
            vk_code = vk & 0xFF
            shift_state = (vk >> 8) & 0xFF

            if shift_state & 1:
                self._key_down(self.VK_MAP["shift"])

            self._key_down(vk_code)
            self._key_up(vk_code)

            if shift_state & 1:
                self._key_up(self.VK_MAP["shift"])

            if delay > 0:
                time.sleep(delay)

        return {"success": True, "typed_length": len(text)}

    def press_key(self, key_name: str) -> Dict[str, Any]:
        """Presses and releases a single key (e.g. 'enter', 'tab', 'esc', 'space')"""
        return self.press_shortcut([key_name])


keyboard_agent = KeyboardAgent()
