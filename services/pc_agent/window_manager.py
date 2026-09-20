"""
Windows Window Management Engine for J.A.R.V.I.S.
Provides programmatic control over open desktop applications and windows.
"""

from __future__ import annotations
import sys
from typing import List, Dict, Any, Optional
import subprocess

try:
    import ctypes
    user32 = ctypes.windll.user32
except Exception:
    user32 = None

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisWindowManager")


class WindowManager:
    def get_open_windows(self) -> List[Dict[str, Any]]:
        """Enumerates visible top-level desktop windows"""
        windows = []
        if not user32 or sys.platform != "win32":
            return windows

        def enum_windows_callback(hwnd, extra):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if title and title != "Program Manager":
                        windows.append({"hwnd": hwnd, "title": title})
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return windows

    def focus_window(self, title_query: str) -> bool:
        """Brings the first matching window to the foreground"""
        logger.info(f"[WindowManager] Focusing window matching: '{title_query}'")
        windows = self.get_open_windows()
        for w in windows:
            if title_query.lower() in w["title"].lower():
                hwnd = w["hwnd"]
                # 9 = SW_RESTORE
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
                return True
        return False

    def minimize_window(self, title_query: str) -> bool:
        """Minimizes matching window"""
        windows = self.get_open_windows()
        for w in windows:
            if title_query.lower() in w["title"].lower():
                hwnd = w["hwnd"]
                # 6 = SW_MINIMIZE
                user32.ShowWindow(hwnd, 6)
                return True
        return False


window_manager = WindowManager()
