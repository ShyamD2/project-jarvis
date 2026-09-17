"""
J.A.R.V.I.S. Mouse Control Agent (Computer Pillar).
Handles cursor movement, clicks, double clicks, and scrolling using Win32 API.
Integrated with Emergency Stop abort checks.
"""

import sys
import time
import ctypes
from typing import Dict, Any, Tuple
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisMouseAgent")


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MouseAgent:
    def __init__(self):
        self._user32 = ctypes.windll.user32 if sys.platform == "win32" else None

        # Win32 Mouse Event Flags
        self.MOUSEEVENTF_MOVE = 0x0001
        self.MOUSEEVENTF_LEFTDOWN = 0x0002
        self.MOUSEEVENTF_LEFTUP = 0x0004
        self.MOUSEEVENTF_RIGHTDOWN = 0x0008
        self.MOUSEEVENTF_RIGHTUP = 0x0010
        self.MOUSEEVENTF_MIDDLEDOWN = 0x0020
        self.MOUSEEVENTF_MIDDLEUP = 0x0040
        self.MOUSEEVENTF_WHEEL = 0x0800

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
        """Returns True if emergency stop is active"""
        try:
            from agents.intelligence.emergency_stop import emergency_stop
            return emergency_stop.is_stopped
        except Exception:
            return False

    def get_cursor_position(self) -> Tuple[int, int]:
        """Returns current (x, y) coordinates of mouse cursor"""
        if not self._user32:
            return (0, 0)
        self._ensure_desktop()
        pt = POINT()
        self._user32.GetCursorPos(ctypes.byref(pt))
        return (pt.x, pt.y)

    def move_relative(self, dx: float, dy: float) -> Dict[str, Any]:
        """Instantly moves cursor relative to current position via Win32 hardware event"""
        if self._check_emergency():
            return {"success": False, "status": "aborted_by_emergency_stop"}
        if not self._user32:
            return {"success": False, "error": "Win32 unavailable"}
        self._ensure_desktop()
        self._user32.mouse_event(self.MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)
        return {"success": True, "dx": dx, "dy": dy}

    def move_cursor(self, x: int, y: int, smooth: bool = False) -> Dict[str, Any]:
        """Moves mouse cursor to target coordinates (x, y)"""
        if self._check_emergency():
            return {"success": False, "status": "aborted_by_emergency_stop"}

        if not self._user32:
            return {"success": False, "error": "Win32 unavailable"}

        self._ensure_desktop()
        if not smooth:
            self._user32.SetCursorPos(int(x), int(y))
            return {"success": True, "x": x, "y": y}

        # Smooth interpolation
        cur_x, cur_y = self.get_cursor_position()
        steps = 15
        for i in range(1, steps + 1):
            if self._check_emergency():
                break
            nx = int(cur_x + (x - cur_x) * (i / steps))
            ny = int(cur_y + (y - cur_y) * (i / steps))
            self._user32.SetCursorPos(nx, ny)
            time.sleep(0.01)

        self._user32.SetCursorPos(int(x), int(y))
        return {"success": True, "x": x, "y": y, "smooth": True}

    def click(self, button: str = "left", count: int = 1) -> Dict[str, Any]:
        """Performs left, right, or double click"""
        if self._check_emergency():
            return {"success": False, "status": "aborted_by_emergency_stop"}

        if not self._user32:
            return {"success": False, "error": "Win32 unavailable"}

        self._ensure_desktop()
        b = button.lower().strip()
        for i in range(count):
            if self._check_emergency():
                break
            if b in ["left", "primary"]:
                self._user32.mouse_event(self.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.02)
                self._user32.mouse_event(self.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            elif b in ["right", "secondary"]:
                self._user32.mouse_event(self.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                time.sleep(0.02)
                self._user32.mouse_event(self.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            elif b in ["double", "dblclick"]:
                # Two left clicks in quick succession
                self._user32.mouse_event(self.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                self._user32.mouse_event(self.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                time.sleep(0.05)
                self._user32.mouse_event(self.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                self._user32.mouse_event(self.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            elif b in ["middle"]:
                self._user32.mouse_event(self.MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
                time.sleep(0.02)
                self._user32.mouse_event(self.MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)
            if i < count - 1:
                time.sleep(0.05)

        return {"success": True, "button": button, "count": count}

    def scroll(self, clicks: int = 3, direction: str = "down") -> Dict[str, Any]:
        """Scrolls mouse wheel up or down"""
        if self._check_emergency():
            return {"success": False, "status": "aborted_by_emergency_stop"}

        if not self._user32:
            return {"success": False, "error": "Win32 unavailable"}

        self._ensure_desktop()
        # WHEEL_DELTA is 120
        delta = 120 * abs(clicks)
        if direction.lower().strip() in ["down", "scroll_down"]:
            delta = -delta

        self._user32.mouse_event(self.MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
        return {"success": True, "clicks": clicks, "direction": direction}


mouse_agent = MouseAgent()
