"""
Floating 3D Desktop Agent Launcher for Project J.A.R.V.I.S.
Launches the full-screen, solid non-transparent 3D desktop command center.
Supports pywebview with Edge WebView2 runtime and direct backend bridging.
"""

from __future__ import annotations
import os
import sys
import subprocess
import time
import threading
import ctypes
import urllib.request
from typing import Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisFloatingApp")

HTML_PATH = os.path.join(PROJECT_ROOT, "services", "floating-agent", "floating_agent.html")
SERVER_URL = "http://127.0.0.1:8000/floating_agent"


def get_target_url():
    """Returns local server URL if responsive, else falls back to local file URL."""
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/health", headers={"User-Agent": "JarvisLauncher"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            if resp.status == 200:
                return SERVER_URL
    except Exception:
        pass
    return f"file:///{HTML_PATH.replace(os.sep, '/')}"


def ensure_interactive_desktop():
    """Binds calling thread to WinSta0\\Default interactive desktop so GUI windows appear on active display."""
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            h_default_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_default_desk:
                user32.SetThreadDesktop(h_default_desk)
        except Exception:
            pass


def ensure_backend_server():
    """Checks if the jarvis-core server is running on port 8000; if not, starts it."""
    url = "http://127.0.0.1:8000/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisLauncher"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                logger.info("⚡ [FloatingApp] J.A.R.V.I.S. Core server verified online.")
                return
    except Exception:
        pass

    logger.info("🚀 [FloatingApp] Starting J.A.R.V.I.S. Core server daemon on port 8000...")
    try:
        core_dir = os.path.join(PROJECT_ROOT, "services", "jarvis-core")
        flags = 0
        if sys.platform == "win32":
            flags = 0x00000008 | 0x00000200
        subprocess.Popen(
            [sys.executable, "main.py"],
            cwd=core_dir,
            creationflags=flags
        )
        for _ in range(12):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(url, timeout=1.0) as resp:
                    if resp.status == 200:
                        logger.info("✅ [FloatingApp] J.A.R.V.I.S. Core server started successfully.")
                        return
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Could not auto-start core server: {e}")


class FloatingAgentAPI:
    def __init__(self):
        self._window = None

    def bind_window(self, window):
        self._window = window

    def set_window_size(self, width: int, height: int):
        """Dynamically resizes the window."""
        if self._window:
            try:
                self._window.resize(width, height)
            except Exception as e:
                logger.debug(f"[FloatingApp] Window resize notice: {e}")

    def toggle_fullscreen(self):
        """Toggles fullscreen state."""
        if self._window:
            try:
                self._window.toggle_fullscreen()
            except Exception as e:
                logger.debug(f"[FloatingApp] Fullscreen toggle: {e}")

    def minimize(self):
        """Minimizes the window to taskbar."""
        if self._window:
            try:
                self._window.minimize()
            except Exception as e:
                logger.debug(f"[FloatingApp] Minimize: {e}")

    def close(self):
        """Closes the window."""
        if self._window:
            try:
                self._window.destroy()
            except Exception as e:
                pass

    def execute_command(self, query: str) -> dict:
        """Direct native bridge to device_router for immediate autonomous execution."""
        import asyncio
        from services.cloud.device_router import device_router
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(device_router.route_and_execute(query, source_device_id="desktop-shyam"))
            loop.close()
            return res
        except Exception as e:
            logger.error(f"[FloatingApp] Direct execution error: {e}")
            return {"success": False, "message": f"Execution error: {str(e)}", "target_device": "DESKTOP-SHYAM"}


def focus_on_start():
    """Brings window to foreground once displayed."""
    time.sleep(1.0)
    if sys.platform == "win32":
        try:
            ensure_interactive_desktop()
            from agents.computer.windows_agent import focus_window_by_name
            focus_window_by_name("JARVIS")
        except Exception:
            pass


def main():
    logger.info("==================================================")
    logger.info("   J.A.R.V.I.S. COMPUTER AGENT COMMAND CENTER")
    logger.info("   Full-Screen Solid HUD (Zero Transparency)")
    logger.info("==================================================")

    # 1. Bind to active user desktop
    ensure_interactive_desktop()

    # 2. Ensure Core backend server is running
    ensure_backend_server()

    # 3. Isolate WebView2 profile
    profile_dir = os.path.join(PROJECT_ROOT, "data", "webview2_profile")
    os.makedirs(profile_dir, exist_ok=True)
    os.environ["WEBVIEW2_USER_DATA_FOLDER"] = profile_dir

    # 4. Compact Floating Window Geometry (NOT full screen)
    user32 = ctypes.windll.user32 if sys.platform == "win32" else None
    screen_w = user32.GetSystemMetrics(0) if user32 else 1536
    screen_h = user32.GetSystemMetrics(1) if user32 else 864

    win_w = 420
    win_h = 560
    win_x = max(20, screen_w - win_w - 30)
    win_y = max(20, screen_h - win_h - 60)

    logger.info(f"📍 [FloatingApp] Opening compact floating agent: {win_w}x{win_h} at ({win_x}, {win_y})")

    try:
        import webview
        api = FloatingAgentAPI()
        target_url = get_target_url()

        window = webview.create_window(
            title="J.A.R.V.I.S. Floating Agent",
            url=target_url,
            width=win_w,
            height=win_h,
            x=win_x,
            y=win_y,
            frameless=True,
            fullscreen=False,
            on_top=True,
            resizable=True,
            transparent=False,
            background_color="#060e1c",
            js_api=api
        )
        api.bind_window(window)

        threading.Thread(target=focus_on_start, daemon=True).start()

        logger.info(f"⚡ [FloatingApp] Spawning compact floating J.A.R.V.I.S. agent from {target_url}...")
        webview.start()

    except Exception as e:
        logger.error(f"[FloatingApp] Desktop agent error: {e}")
        try:
            from agents.computer.windows_agent import windows_agent
            windows_agent.open_url(get_target_url())
        except Exception:
            pass


if __name__ == "__main__":
    main()
