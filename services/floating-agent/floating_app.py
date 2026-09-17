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

if sys.stdout is None:
    try:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass
if sys.stderr is None:
    try:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass
import threading
import ctypes
import urllib.request
import re
import base64
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
        with urllib.request.urlopen(req, timeout=0.05) as resp:
            if resp.status == 200:
                return SERVER_URL
    except Exception:
        pass
    return f"file:///{HTML_PATH.replace(os.sep, '/')}"


def ensure_interactive_desktop():
    """Binds calling thread to active input desktop so GUI windows appear on active display."""
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
            if not hdesk:
                hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
        except Exception:
            pass


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

    def toggle_mini_mode(self, is_mini: bool):
        """Switches between compact HUD (420x560) and sleek Mini Orb (96x96)."""
        if self._window:
            try:
                if is_mini:
                    self._window.resize(96, 96)
                else:
                    self._window.resize(420, 560)
            except Exception as e:
                logger.debug(f"[FloatingApp] Mini mode resize error: {e}")

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

    def analyze_screen_vision(self, prompt: str = "Analyze what is on my screen") -> dict:
        """Multimodal Screen Vision bridge using real desktop capture + AI analysis."""
        import asyncio
        from services.sensory.screen_vision import screen_vision
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(screen_vision.analyze_screen_context(prompt))
            loop.close()
            return res
        except Exception as e:
            logger.error(f"[FloatingApp] Screen vision bridge error: {e}")
            return {"success": False, "analysis": f"Screen vision error: {str(e)}"}

    def synthesize_speech(self, text: str) -> dict:
        """Synthesizes Paul Bettany British neural speech using Edge-TTS and returns base64 MP3."""
        import asyncio
        try:
            import edge_tts
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            clean_text = text[:450]
            clean_text = re.sub(r'[*#_~`\[\]]', '', clean_text)
            async def _synth():
                communicate = edge_tts.Communicate(clean_text, "en-GB-RyanNeural", pitch="-2Hz", rate="-2%")
                chunks = []
                async for chunk in communicate.stream():
                    if chunk.get("type") == "audio":
                        chunks.append(chunk["data"])
                return b"".join(chunks)
            audio_bytes = loop.run_until_complete(_synth())
            loop.close()
            if audio_bytes:
                b64 = base64.b64encode(audio_bytes).decode("utf-8")
                return {"success": True, "audio_b64": f"data:audio/mp3;base64,{b64}"}
        except Exception as e:
            logger.debug(f"[FloatingApp] Speech synthesis error: {e}")
        return {"success": False, "audio_b64": ""}

    def analyze_dropped_file(self, filename: str, content_b64: str) -> dict:
        """Processes files dropped onto the 3D Arc Reactor."""
        try:
            raw_bytes = base64.b64decode(content_b64)
            ext = os.path.splitext(filename)[1].lower()

            if ext in [".py", ".js", ".html", ".css", ".json", ".md", ".txt", ".log", ".bat", ".sh", ".yaml", ".yml", ".env"]:
                text_content = raw_bytes.decode("utf-8", errors="replace")
                lines = text_content.splitlines()
                num_lines = len(lines)
                size_kb = round(len(raw_bytes) / 1024, 1)

                analysis = f"Ingested {filename} ({num_lines} lines, {size_kb} KB). Code syntax and parameters locked into active buffer, sir."
                return {
                    "success": True,
                    "filename": filename,
                    "lines": num_lines,
                    "analysis": analysis
                }
            elif ext in [".png", ".jpg", ".jpeg", ".webp"]:
                return {
                    "success": True,
                    "filename": filename,
                    "analysis": f"Visual imagery '{filename}' ingested into Stark sensory buffer. Resolution and telemetry locked, sir."
                }
            else:
                return {
                    "success": True,
                    "filename": filename,
                    "analysis": f"Binary asset '{filename}' ({len(raw_bytes)} bytes) ingested into Stark tactical cache, sir."
                }
        except Exception as e:
            return {"success": False, "filename": filename, "analysis": f"File ingestion notice: {str(e)}"}

    def execute_device_action(self, action: str, params: dict = None) -> dict:
        """Native Windows UI automation bridge for clicks, scrolls, and typing."""
        params = params or {}
        try:
            from services.device_agents.windows.windows_device_agent import windows_agent
            if action == "click":
                return windows_agent.left_click(params.get("x", 0), params.get("y", 0))
            elif action == "type":
                return windows_agent.type_text(params.get("text", ""))
            elif action == "press":
                return windows_agent.press_key(params.get("key", "enter"))
            elif action == "scroll":
                return windows_agent.scroll_page(params.get("direction", "down"), params.get("clicks", 3))
            return {"success": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


def start_global_hotkey_listener(window):
    """
    Background daemon monitoring Alt + J (0x12 + 0x4A) via user32.GetAsyncKeyState.
    Toggles the floating window between foreground active and minimized globally.
    """
    if sys.platform != "win32":
        return

    def _loop():
        user32 = ctypes.windll.user32
        VK_MENU = 0x12  # Alt
        VK_J = 0x4A     # 'J'
        is_hidden = False

        while True:
            try:
                alt_down = bool(user32.GetAsyncKeyState(VK_MENU) & 0x8000)
                j_down = bool(user32.GetAsyncKeyState(VK_J) & 0x8000)

                if alt_down and j_down:
                    logger.info("⚡ [FloatingApp] Global Hotkey Alt+J triggered!")
                    hwnd = user32.FindWindowW(None, "J.A.R.V.I.S. Floating Agent")
                    if is_hidden:
                        if hwnd:
                            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                            user32.SetForegroundWindow(hwnd)
                        try:
                            window.restore()
                        except Exception:
                            pass
                        is_hidden = False
                    else:
                        try:
                            window.minimize()
                        except Exception:
                            if hwnd:
                                user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
                        is_hidden = True

                    time.sleep(0.4)
            except Exception as e:
                logger.debug(f"[FloatingApp] Hotkey check notice: {e}")
            time.sleep(0.05)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    logger.info("⚡ [FloatingApp] Global Alt+J hotkey listener activated.")


def focus_on_start():
    """Brings window to foreground and ensures HWND_TOPMOST once displayed."""
    for _ in range(16):
        time.sleep(0.3)
        if sys.platform == "win32":
            try:
                ensure_interactive_desktop()
                user32 = ctypes.windll.user32
                hwnd = user32.FindWindowW(None, "J.A.R.V.I.S. Floating Agent")
                if hwnd and user32.IsWindowVisible(hwnd):
                    HWND_TOPMOST = ctypes.c_void_p(-1)
                    SWP_NOMOVE = 0x0002
                    SWP_NOSIZE = 0x0001
                    SWP_SHOWWINDOW = 0x0040
                    user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
                    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    logger.info(f"⚡ [FloatingApp] Window pinned TOPMOST and focused (HWND: {hwnd})")
                    break
            except Exception as e:
                logger.debug(f"[FloatingApp] Focus attempt notice: {e}")


def main():
    logger.info("==================================================")
    logger.info("   J.A.R.V.I.S. COMPUTER AGENT COMMAND CENTER")
    logger.info("   Full-Screen Solid HUD (Zero Transparency)")
    logger.info("==================================================")

    # 1. Bind to active user desktop
    ensure_interactive_desktop()

    # 2. Isolate WebView2 profile with unique directory to prevent 0x800700AA resource locked error
    import tempfile
    profile_dir = os.path.join(tempfile.gettempdir(), f"jarvis_hud_{os.getpid()}")
    os.makedirs(profile_dir, exist_ok=True)
    os.environ["WEBVIEW2_USER_DATA_FOLDER"] = profile_dir
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--use-fake-ui-for-media-stream --disable-features=msSmartScreenProtection"

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
        start_global_hotkey_listener(window)

        threading.Thread(target=focus_on_start, daemon=True).start()

        logger.info(f"⚡ [FloatingApp] Spawning compact floating J.A.R.V.I.S. agent from {target_url}...")
        webview.start()

    except Exception as e:
        logger.error(f"[FloatingApp] Desktop agent error: {e}")
        import traceback
        with open(r"d:\Project J.A.R.V.I.S\services\sensory\screenshots\floating_app_error.log", "w") as f:
            traceback.print_exc(file=f)
        try:
            from agents.computer.windows_agent import windows_agent
            windows_agent.open_url(get_target_url())
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        with open(r"d:\Project J.A.R.V.I.S\services\sensory\screenshots\floating_app_error.log", "w") as f:
            traceback.print_exc(file=f)
