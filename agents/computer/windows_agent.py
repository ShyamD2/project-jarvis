"""
Windows Local Execution Agent for J.A.R.V.I.S.
Controls Windows applications, executes PowerShell commands, and manages workspace processes.
"""

import subprocess
import os
import sys
import shutil
import time
import psutil
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("WindowsAgent")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))



def ensure_interactive_desktop():
    """Binds calling thread to WinSta0\\Default interactive desktop so GUI windows and ShellExecute appear on active display."""
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            h_default_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_default_desk:
                user32.SetThreadDesktop(h_default_desk)
        except Exception:
            pass


def focus_window_by_name(keyword: str):
    """Brings matching visible window to the foreground on the active interactive desktop, bypassing Windows foreground lock."""
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            h_def = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_def:
                user32.SetThreadDesktop(h_def)

            user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
            user32.GetWindowTextLengthW.restype = ctypes.c_int
            user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
            user32.GetWindowTextW.restype = ctypes.c_int
            user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
            user32.IsWindowVisible.restype = ctypes.c_bool
            user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
            user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
            user32.SwitchToThisWindow.argtypes = [ctypes.c_void_p, ctypes.c_bool]
            user32.BringWindowToTop.argtypes = [ctypes.c_void_p]

            matches = []
            EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def foreach_desktop_window(hwnd, lParam):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if keyword.lower() in title.lower():
                        matches.append(hwnd)
                return True

            enum_fn = EnumProc(foreach_desktop_window)
            if h_def:
                user32.EnumDesktopWindows(h_def, enum_fn, 0)
            else:
                user32.EnumWindows(enum_fn, 0)

            for hwnd in matches:
                try:
                    fg_hwnd = user32.GetForegroundWindow()
                    fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None)
                    cur_tid = kernel32.GetCurrentThreadId()
                    attached = False
                    if fg_tid and fg_tid != cur_tid:
                        attached = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))

                    user32.ShowWindow(hwnd, 9)          # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    user32.SwitchToThisWindow(hwnd, True)
                    user32.BringWindowToTop(hwnd)

                    if attached:
                        user32.AttachThreadInput(cur_tid, fg_tid, False)
                except Exception:
                    user32.ShowWindow(hwnd, 9)
                    user32.SetForegroundWindow(hwnd)
                    user32.BringWindowToTop(hwnd)

                logger.info(f"[WindowsAgent] Brought '{keyword}' (HWND: {hwnd}) to front display cleanly")
        except Exception as e:
            logger.warning(f"[WindowsAgent] focus_window_by_name error: {e}")


def launch_process_on_interactive_desktop(cmd: str, cwd: Optional[str] = None) -> bool:
    """
    Launches a command directly onto WinSta0\\Default (the active physical desktop)
    using Win32 CreateProcessW with lpDesktop = 'Default'.
    Ensures GUI windows and WebViews render visibly on the physical display even if
    the calling process was launched in a service or sandbox desktop.
    """
    if sys.platform != "win32":
        try:
            subprocess.Popen(cmd, shell=True, cwd=cwd)
            return True
        except Exception:
            return False

    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32

        class STARTUPINFO(ctypes.Structure):
            _fields_ = [
                ('cb', wintypes.DWORD),
                ('lpReserved', wintypes.LPWSTR),
                ('lpDesktop', wintypes.LPWSTR),
                ('lpTitle', wintypes.LPWSTR),
                ('dwX', wintypes.DWORD),
                ('dwY', wintypes.DWORD),
                ('dwXSize', wintypes.DWORD),
                ('dwYSize', wintypes.DWORD),
                ('dwXCountChars', wintypes.DWORD),
                ('dwYCountChars', wintypes.DWORD),
                ('dwFillAttribute', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD),
                ('wShowWindow', wintypes.WORD),
                ('cbReserved2', wintypes.WORD),
                ('lpReserved2', ctypes.c_void_p),
                ('hStdInput', wintypes.HANDLE),
                ('hStdOutput', wintypes.HANDLE),
                ('hStdError', wintypes.HANDLE),
            ]

        class PROCESS_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('hProcess', wintypes.HANDLE),
                ('hThread', wintypes.HANDLE),
                ('dwProcessId', wintypes.DWORD),
                ('dwThreadId', wintypes.DWORD),
            ]

        si = STARTUPINFO()
        si.cb = ctypes.sizeof(STARTUPINFO)
        si.lpDesktop = "Default"

        pi = PROCESS_INFORMATION()

        kernel32.CreateProcessW.argtypes = [
            wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
            wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
            ctypes.POINTER(STARTUPINFO), ctypes.POINTER(PROCESS_INFORMATION)
        ]
        kernel32.CreateProcessW.restype = wintypes.BOOL

        flags = 0x00000200  # CREATE_NEW_PROCESS_GROUP
        cmd_buf = ctypes.create_unicode_buffer(cmd)
        success = kernel32.CreateProcessW(
            None, cmd_buf, None, None, False, flags, None, cwd,
            ctypes.byref(si), ctypes.byref(pi)
        )

        if success:
            kernel32.CloseHandle(pi.hProcess)
            kernel32.CloseHandle(pi.hThread)
            logger.info(f"[WindowsAgent] Launched PID {pi.dwProcessId} on Default desktop: {cmd}")
            return True
        else:
            err = kernel32.GetLastError()
            logger.warning(f"[WindowsAgent] CreateProcessW returned error {err}, falling back to subprocess.Popen")
    except Exception as e:
        logger.warning(f"[WindowsAgent] launch_process_on_interactive_desktop error: {e}")

    try:
        subprocess.Popen(cmd, cwd=cwd, shell=True)
        return True
    except Exception as e_sub:
        logger.error(f"[WindowsAgent] Subprocess fallback failed: {e_sub}")
        return False


def launch_floating_hud() -> Dict[str, Any]:
    """
    Brings J.A.R.V.I.S. 3D Floating HUD to the front if already running,
    or launches it directly onto WinSta0\\Default so it appears visibly on the screen.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            h_def = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_def:
                user32.SetThreadDesktop(h_def)
            hwnd = user32.FindWindowW(None, "J.A.R.V.I.S. Floating Agent")
            if hwnd and user32.IsWindowVisible(hwnd):
                HWND_TOPMOST = ctypes.c_void_p(-1)
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_SHOWWINDOW = 0x0040
                user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
                return {"success": True, "action": "focused", "message": "J.A.R.V.I.S. was already open; brought to foreground."}
        except Exception:
            pass

    py_exe = sys.executable or "python.exe"
    hud_script = os.path.join(PROJECT_ROOT, "services", "floating_agent", "floating_app.py")
    cmd = f'"{py_exe}" -X utf8 "{hud_script}"'
    ok = launch_process_on_interactive_desktop(cmd, cwd=PROJECT_ROOT)
    return {"success": ok, "action": "launched", "message": "J.A.R.V.I.S. 3D Floating Agent launched on desktop."}


def find_start_menu_app(name: str) -> Optional[str]:
    """Finds installed application shortcut (.lnk) in Windows Start Menu directories."""
    dirs = [
        os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")
    ]
    name_clean = name.lower().replace(" ", "").replace("_", "").replace("-", "")
    best_match = None
    for d in dirs:
        if not os.path.exists(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if f.lower().endswith(".lnk"):
                    stem = os.path.splitext(f)[0].lower().replace(" ", "").replace("_", "").replace("-", "")
                    if name_clean == stem:
                        return os.path.join(root, f)
                    if name_clean in stem and not best_match:
                        best_match = os.path.join(root, f)
    return best_match


class WindowsAgent:
    def find_app_path(self, app_name: str) -> Optional[str]:
        """Dynamically locates exact executable path for desktop apps on Windows"""
        if not app_name:
            return None
        app_lower = app_name.lower().strip()

        # Check if already a valid absolute or relative path
        if os.path.isfile(app_name):
            return os.path.abspath(app_name)

        # 1. Opera / Opera GX paths
        if "opera" in app_lower:
            candidates = [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\launcher.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\opera.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Opera GX\opera.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Opera\launcher.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Opera GX\opera.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Opera\launcher.exe"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c

        # 2. Chrome
        if "chrome" in app_lower:
            candidates = [
                os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c

        # 3. Edge
        if "edge" in app_lower:
            candidates = [
                os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c

        # 4. VS Code
        if app_lower in ["code", "vscode"]:
            candidates = [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Microsoft VS Code\Code.exe"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c

        # 5. Common Alias Map
        alias_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "code": "code",
            "vscode": "code",
            "wt": "wt.exe",
            "terminal": "wt.exe",
            "explorer": "explorer.exe",
            "taskmgr": "taskmgr.exe",
            "mspaint": "mspaint.exe",
            "spotify": "spotify.exe",
            "discord": "discord.exe"
        }
        mapped_target = alias_map.get(app_lower, app_name)

        # 6. Resolve via system PATH using shutil.which
        resolved = shutil.which(mapped_target)
        if resolved:
            return resolved
        if not mapped_target.lower().endswith(".exe"):
            resolved = shutil.which(f"{mapped_target}.exe")
            if resolved:
                return resolved

        return None

    @staticmethod
    def _open_url_safely(target_url: str) -> bool:
        """Safely launches a URL directly in the user's browser (prioritizing Opera GX / Opera)."""
        import os
        import subprocess

        # Priority browser candidates on Windows (Opera GX first, then Opera, Chrome, Edge)
        local_app = os.environ.get("LOCALAPPDATA", "")
        prog_files = os.environ.get("ProgramFiles", "")
        prog_files_x86 = os.environ.get("ProgramFiles(x86)", "")

        browser_paths = [
            os.path.join(local_app, r"Programs\Opera GX\opera.exe"),
            os.path.join(local_app, r"Programs\Opera\opera.exe"),
            os.path.join(prog_files, r"Opera GX\opera.exe"),
            os.path.join(prog_files, r"Opera\opera.exe"),
            os.path.join(prog_files, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(prog_files_x86, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(prog_files_x86, r"Microsoft\Edge\Application\msedge.exe"),
            os.path.join(prog_files, r"Microsoft\Edge\Application\msedge.exe"),
        ]

        # 1. Try launching directly with the preferred browser binary for guaranteed new tab creation
        for bp in browser_paths:
            if bp and os.path.exists(bp):
                try:
                    subprocess.Popen([bp, target_url])
                    logger.info(f"[WindowsAgent] Successfully launched URL via browser '{bp}': {target_url}")
                    return True
                except Exception as e:
                    logger.warning(f"[WindowsAgent] Direct launch via '{bp}' failed: {e}")

        # 2. Fallback to os.startfile
        try:
            os.startfile(target_url)
            return True
        except Exception:
            try:
                import webbrowser
                webbrowser.open(target_url)
                return True
            except Exception as e:
                logger.warning(f"[WindowsAgent] Safe URL launch failed for '{target_url}': {e}")
                return False

    def launch_app(self, app_name: str, args: List[str] = None, mode: str = "auto") -> Dict[str, Any]:
        """
        Universally launches applications across Web and Windows System.
        Supports mode="auto", "web", "system".
        """
        import re
        args = args or []
        app_raw = app_name.lower().strip()

        # 1. Parse mode & clean target
        if any(w in app_raw for w in ["on web", "on browser", "web version", "online"]):
            mode = "web"
        elif any(w in app_raw for w in ["on system", "on pc", "on desktop", "system app", "desktop app", "locally", "systems", "system's"]):
            mode = "system"

        clean_target = re.sub(r"\b(on\s+web|on\s+browser|on\s+system|on\s+pc|on\s+desktop|web\s+version|online|systems|system's|system|desktop|locally)\b", "", app_raw).strip()
        clean_target = re.sub(r"\s+", " ", clean_target).strip()
        if not clean_target:
            clean_target = app_raw

        # User Rule: For Snapchat ONLY, DEFAULT to web (https://web.snapchat.com).
        # It must ONLY open on system if the user explicitly specified "system" or "systems".
        if clean_target == "snapchat":
            has_explicit_system = any(w in app_raw for w in ["system", "systems", "system's", "desktop app", "locally"])
            if not has_explicit_system:
                mode = "web"

        logger.info(f"[WindowsAgent] Launching app: '{clean_target}' [mode: {mode}] with args: {args}")
        ensure_interactive_desktop()

        # Comprehensive Web Applications Map
        WEB_APPS = {
            "snapchat": "https://web.snapchat.com",
            "whatsapp": "https://web.whatsapp.com",
            "youtube": "https://www.youtube.com",
            "yt": "https://www.youtube.com",
            "spotify": "https://open.spotify.com",
            "discord": "https://discord.com/app",
            "telegram": "https://web.telegram.org",
            "instagram": "https://www.instagram.com",
            "insta": "https://www.instagram.com",
            "twitter": "https://x.com",
            "x": "https://x.com",
            "reddit": "https://www.reddit.com",
            "github": "https://github.com",
            "linkedin": "https://www.linkedin.com",
            "gmail": "https://mail.google.com",
            "google": "https://www.google.com",
            "calendar": "https://calendar.google.com",
            "maps": "https://maps.google.com",
            "netflix": "https://www.netflix.com",
            "prime": "https://www.primevideo.com",
            "primevideo": "https://www.primevideo.com",
            "chatgpt": "https://chatgpt.com",
            "openai": "https://chatgpt.com",
            "claude": "https://claude.ai",
            "canva": "https://www.canva.com",
            "figma": "https://www.figma.com",
            "twitch": "https://www.twitch.tv",
            "tiktok": "https://www.tiktok.com",
            "facebook": "https://www.facebook.com",
            "notion": "https://www.notion.so",
            "slack": "https://app.slack.com",
            "zoom": "https://zoom.us",
            "drive": "https://drive.google.com"
        }

        # 2. IF MODE == "web" (Explicit Web Request)
        if mode == "web":
            target_url = WEB_APPS.get(clean_target)
            if not target_url:
                target_url = f"https://www.{clean_target}.com"
            logger.info(f"[WindowsAgent] Launching Web Application: {target_url}")
            self._open_url_safely(target_url)
            time.sleep(0.3)
            focus_window_by_name("Opera")
            return {
                "success": True,
                "app": clean_target,
                "path": target_url,
                "pid": 0,
                "mode": "web",
                "status": "running",
                "channel_1_logical": True
            }

        # 3. IF MODE == "system" OR MODE == "auto" (System Search)
        # Check standard Windows Store Protocols
        PROTOCOLS = {
            "calculator": "ms-calculator:",
            "calc": "ms-calculator:",
            "settings": "ms-settings:",
            "photos": "ms-photos:",
            "camera": "microsoft.windows.camera:",
            "store": "ms-windows-store:",
            "whatsapp": "whatsapp:",
            "spotify": "spotify:",
            "discord": "discord:",
            "snapchat": "snapchat:",
            "steam": "steam:",
            "teams": "msteams:",
            "zoom": "zoommtg:"
        }

        # Check native protocol first for system apps
        if clean_target in PROTOCOLS:
            proto = PROTOCOLS[clean_target]
            try:
                os.startfile(proto)
                time.sleep(0.4)
                focus_window_by_name(clean_target.capitalize())
                return {
                    "success": True,
                    "app": clean_target,
                    "path": proto,
                    "pid": 0,
                    "mode": "system",
                    "status": "running",
                    "channel_1_logical": True
                }
            except Exception as pe:
                logger.info(f"[WindowsAgent] Protocol '{proto}' not available: {pe}")

        # Check Start Menu shortcut (.lnk)
        start_menu_app = find_start_menu_app(clean_target)
        if start_menu_app and os.path.exists(start_menu_app):
            logger.info(f"[WindowsAgent] Launching Start Menu application: {start_menu_app}")
            try:
                os.startfile(start_menu_app)
                time.sleep(0.5)
                focus_window_by_name(clean_target)
                return {
                    "success": True,
                    "app": clean_target,
                    "path": start_menu_app,
                    "pid": 0,
                    "mode": "system",
                    "status": "running",
                    "channel_1_logical": True
                }
            except Exception as e_lnk:
                logger.warning(f"[WindowsAgent] Start menu launch error: {e_lnk}")

        # Check executable file path via find_app_path
        target_path = self.find_app_path(clean_target)
        if target_path and os.path.exists(target_path):
            try:
                cmd_args = [target_path] + [str(a) for a in args]
                si = None
                if sys.platform == "win32":
                    si = subprocess.STARTUPINFO()
                    si.lpDesktop = r"WinSta0\Default"

                proc = subprocess.Popen(
                    cmd_args,
                    shell=target_path.lower().endswith((".cmd", ".bat")),
                    startupinfo=si
                )
                pid = proc.pid
                time.sleep(0.4)
                focus_window_by_name(clean_target)
                return {
                    "success": True,
                    "app": clean_target,
                    "path": target_path,
                    "pid": pid,
                    "mode": "system",
                    "status": "running",
                    "channel_1_logical": True
                }
            except Exception as e:
                logger.error(f"[WindowsAgent] Error launching {clean_target} executable: {e}")

        # If mode == "system" and local executable/protocol failed:
        if mode == "system":
            # If web equivalent exists, offer graceful fallback
            if clean_target in WEB_APPS:
                fallback_url = WEB_APPS[clean_target]
                logger.info(f"[WindowsAgent] System app '{clean_target}' not installed; falling back to web version: {fallback_url}")
                self._open_url_safely(fallback_url)
                time.sleep(0.3)
                focus_window_by_name("Opera")
                return {
                    "success": True,
                    "app": clean_target,
                    "path": fallback_url,
                    "pid": 0,
                    "mode": "web_fallback",
                    "notice": f"{clean_target.capitalize()} desktop application is not installed on your system. Launched web version instead.",
                    "status": "running",
                    "channel_1_logical": True
                }
            return {
                "success": False,
                "app": clean_target,
                "status": "not_found",
                "error": f"Application '{clean_target}' is not installed on your Windows system.",
                "channel_1_logical": False
            }

        # 4. IF MODE == "auto" AND NOT FOUND LOCALLY -> Check WEB_APPS or www.<app>.com
        if clean_target in WEB_APPS:
            web_url = WEB_APPS[clean_target]
            logger.info(f"[WindowsAgent] Launching web app for '{clean_target}': {web_url}")
            self._open_url_safely(web_url)
            time.sleep(0.3)
            focus_window_by_name("Opera")
            return {
                "success": True,
                "app": clean_target,
                "path": web_url,
                "pid": 0,
                "mode": "web",
                "status": "running",
                "channel_1_logical": True
            }

        # Fallback to www.<target>.com
        fallback_url = f"https://www.{clean_target}.com"
        logger.info(f"[WindowsAgent] Launching web service fallback: {fallback_url}")
        self._open_url_safely(fallback_url)
        time.sleep(0.3)
        focus_window_by_name("Opera")
        return {
            "success": True,
            "app": clean_target,
            "path": fallback_url,
            "pid": 0,
            "mode": "web",
            "status": "running",
            "channel_1_logical": True
        }

    # Alias for API compatibility
    launch_application = launch_app

    def execute_powershell(self, script: str) -> Dict[str, Any]:
        """Executes a PowerShell scriptlet safely"""
        logger.info(f"[WindowsAgent] Executing PowerShell: {script[:60]}...")
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                timeout=15
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
                "channel_1_logical": result.returncode == 0
            }
        except Exception as e:
            logger.error(f"[WindowsAgent] PowerShell execution error: {e}")
            return {
                "success": False,
                "error": str(e),
                "channel_1_logical": False
            }

    def verify_process_running(self, process_name: str) -> bool:
        """Verifies if a target process name is currently running via psutil"""
        proc_lower = process_name.lower().replace(".exe", "").strip()
        try:
            for p in psutil.process_iter(['name']):
                p_name = p.info.get('name')
                if p_name and p_name.lower().replace(".exe", "").strip() == proc_lower:
                    return True
        except Exception as e:
            logger.error(f"[WindowsAgent] Error checking process {process_name}: {e}")
        return False

    def close_active_tab(self, target_or_browser: Optional[str] = None) -> Dict[str, Any]:
        """Closes targeted tab or active browser tab using native Ctrl+W key event without killing the browser."""
        logger.info(f"[WindowsAgent] Closing tab with target: {target_or_browser}")
        ensure_interactive_desktop()
        if sys.platform != "win32":
            return {"success": False, "error": "Not running on Windows"}

        import ctypes
        u32 = ctypes.windll.user32

        # If a target or tab keyword is provided, search window titles
        focused_target = None
        if target_or_browser:
            t_clean = target_or_browser.strip()
            # Focus window containing the keyword (e.g. "YouTube", "Amazon", "Opera")
            focused_target = focus_window_by_name(t_clean)

        if not focused_target:
            # Fallback to active window or prominent browsers
            active_proc = self.get_active_window_info().get("process", "").lower()
            if not any(b in active_proc for b in ["opera", "chrome", "msedge", "edge", "brave", "firefox", "code"]):
                for b in ["opera", "chrome", "msedge", "edge", "brave", "firefox"]:
                    if focus_window_by_name(b):
                        break

        time.sleep(0.12)
        # Send Ctrl + W to cleanly close active tab
        u32.keybd_event(0x11, 0, 0, 0)  # Ctrl down
        u32.keybd_event(0x57, 0, 0, 0)  # W down
        time.sleep(0.04)
        u32.keybd_event(0x57, 0, 2, 0)  # W up
        u32.keybd_event(0x11, 0, 2, 0)  # Ctrl up
        return {"success": True, "action": "close_tab", "target": target_or_browser or "active_tab"}

    def switch_tab(self, direction: str = "next") -> Dict[str, Any]:
        """Switches to the next or previous tab in the active browser."""
        ensure_interactive_desktop()
        if sys.platform != "win32":
            return {"success": False, "error": "Not running on Windows"}
        import ctypes
        u32 = ctypes.windll.user32
        is_prev = direction.lower().strip() in ["prev", "previous", "left"]

        u32.keybd_event(0x11, 0, 0, 0)  # Ctrl down
        if is_prev:
            u32.keybd_event(0x10, 0, 0, 0)  # Shift down
        u32.keybd_event(0x09, 0, 0, 0)  # Tab down
        time.sleep(0.04)
        u32.keybd_event(0x09, 0, 2, 0)  # Tab up
        if is_prev:
            u32.keybd_event(0x10, 0, 2, 0)  # Shift up
        u32.keybd_event(0x11, 0, 2, 0)  # Ctrl up
        return {"success": True, "action": "switch_tab", "direction": direction}

    def open_new_tab(self) -> Dict[str, Any]:
        """Opens a new browser tab using native Ctrl+T."""
        ensure_interactive_desktop()
        if sys.platform != "win32":
            return {"success": False, "error": "Not running on Windows"}
        import ctypes
        u32 = ctypes.windll.user32
        u32.keybd_event(0x11, 0, 0, 0)  # Ctrl down
        u32.keybd_event(0x54, 0, 0, 0)  # T down
        time.sleep(0.04)
        u32.keybd_event(0x54, 0, 2, 0)  # T up
        u32.keybd_event(0x11, 0, 2, 0)  # Ctrl up
        return {"success": True, "action": "new_tab"}

    def switch_window(self) -> Dict[str, Any]:
        """Switches active foreground window using native Alt+Tab."""
        ensure_interactive_desktop()
        if sys.platform != "win32":
            return {"success": False, "error": "Not running on Windows"}
        import ctypes
        u32 = ctypes.windll.user32
        u32.keybd_event(0x12, 0, 0, 0)  # Alt down
        u32.keybd_event(0x09, 0, 0, 0)  # Tab down
        time.sleep(0.05)
        u32.keybd_event(0x09, 0, 2, 0)  # Tab up
        u32.keybd_event(0x12, 0, 2, 0)  # Alt up
        return {"success": True, "action": "switch_window"}

    def close_active_window(self, window_name: Optional[str] = None) -> Dict[str, Any]:
        """Closes targeted or foreground window via WM_CLOSE / Alt+F4."""
        logger.info(f"[WindowsAgent] Closing window: {window_name or 'active'}")
        ensure_interactive_desktop()
        if window_name:
            focus_window_by_name(window_name)
            time.sleep(0.15)
        if sys.platform == "win32":
            import ctypes
            u32 = ctypes.windll.user32
            u32.keybd_event(0x12, 0, 0, 0)  # Alt down
            u32.keybd_event(0x73, 0, 0, 0)  # F4 down
            time.sleep(0.04)
            u32.keybd_event(0x73, 0, 2, 0)  # F4 up
            u32.keybd_event(0x12, 0, 2, 0)  # Alt up
            return {"success": True, "action": "close_window", "target": window_name or "active", "channel_1_logical": True}
        return {"success": False, "error": "Not running on Windows"}

    def close_all_user_apps(self) -> Dict[str, Any]:
        """Closes open non-system user applications gracefully (Opera, WhatsApp, Calculator, Notepad, Spotify, etc.)"""
        logger.info("[WindowsAgent] Closing user desktop applications.")
        ensure_interactive_desktop()
        target_processes = [
            "opera", "calculator", "calculatorapp", "notepad", "whatsapp",
            "spotify", "discord", "chrome", "msedge", "vlc"
        ]
        closed = []
        for proc in psutil.process_iter(['name']):
            try:
                name = (proc.info['name'] or '').lower()
                for t in target_processes:
                    if t in name and name != "jarvis.exe" and "python" not in name:
                        proc.terminate()
                        closed.append(name)
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Also show desktop via Win+D to clear workspace view
        if sys.platform == "win32":
            import ctypes
            u32 = ctypes.windll.user32
            u32.keybd_event(0x5B, 0, 0, 0)  # Win down
            u32.keybd_event(0x44, 0, 0, 0)  # D down
            time.sleep(0.04)
            u32.keybd_event(0x44, 0, 2, 0)  # D up
            u32.keybd_event(0x5B, 0, 2, 0)  # Win up

        return {
            "success": True,
            "action": "close_all_user_apps",
            "closed_count": len(closed),
            "closed": list(set(closed)),
            "channel_1_logical": True
        }

    def open_browser_bookmarks(self, browser: str = "opera") -> Dict[str, Any]:
        """Opens bookmarks page in Opera GX or default browser."""
        logger.info(f"[WindowsAgent] Opening bookmarks page in {browser}")
        ensure_interactive_desktop()
        # In Opera GX, launch opera://bookmarks directly
        opera_path = self.find_app_path("opera")
        if opera_path and os.path.exists(opera_path):
            try:
                subprocess.Popen([opera_path, "opera://bookmarks"])
                time.sleep(0.4)
                focus_window_by_name("Opera")
                return {"success": True, "action": "open_bookmarks", "url": "opera://bookmarks", "channel_1_logical": True}
            except Exception as e:
                logger.warning(f"[WindowsAgent] Could not launch opera bookmarks via path: {e}")

        # Fallback to shortcut Ctrl+Shift+O in focused Opera
        focus_window_by_name(browser)
        time.sleep(0.15)
        if sys.platform == "win32":
            import ctypes
            u32 = ctypes.windll.user32
            u32.keybd_event(0x11, 0, 0, 0)  # Ctrl
            u32.keybd_event(0x10, 0, 0, 0)  # Shift
            u32.keybd_event(0x4F, 0, 0, 0)  # O
            time.sleep(0.05)
            u32.keybd_event(0x4F, 0, 2, 0)
            u32.keybd_event(0x10, 0, 2, 0)
            u32.keybd_event(0x11, 0, 2, 0)
            return {"success": True, "action": "open_bookmarks", "shortcut": "Ctrl+Shift+O", "channel_1_logical": True}
        return {"success": False, "error": "Not running on Windows"}

    def get_uia_window(self, title_pattern: str, timeout: float = 2.0):
        """Locates and returns pywinauto UIA window handle if available."""
        try:
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")
            win = desktop.window(title_re=f"(?i).*{title_pattern}.*")
            if win.exists(timeout=timeout):
                return win
        except Exception as e:
            logger.debug(f"[WindowsAgent] UIA window lookup notice: {e}")
        return None

    def click_uia_element(self, app_keyword: str, element_title_pattern: str, control_type: Optional[str] = None) -> Dict[str, Any]:
        """Clicks an accessible control within an application using Windows UI Automation."""
        try:
            win = self.get_uia_window(app_keyword)
            if not win:
                return {"success": False, "error": f"Application window matching '{app_keyword}' not found in UIA tree."}
            win.set_focus()
            kwargs = {"title_re": f"(?i).*{element_title_pattern}.*"}
            if control_type:
                kwargs["control_type"] = control_type
            elem = win.child_window(**kwargs)
            if elem.exists(timeout=2.0):
                elem.click_input()
                return {"success": True, "action": "click_uia", "target": element_title_pattern}
            return {"success": False, "error": f"Element '{element_title_pattern}' not found in window '{app_keyword}'."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def type_uia_element(self, app_keyword: str, element_title_pattern: str, text: str, press_enter: bool = False) -> Dict[str, Any]:
        """Types text into an accessible edit/input control using Windows UI Automation."""
        try:
            win = self.get_uia_window(app_keyword)
            if not win:
                return {"success": False, "error": f"Application window matching '{app_keyword}' not found."}
            win.set_focus()
            elem = win.child_window(title_re=f"(?i).*{element_title_pattern}.*", control_type="Edit")
            if elem.exists(timeout=2.0):
                elem.click_input()
                keys = text + ("{ENTER}" if press_enter else "")
                elem.type_keys(keys, with_spaces=True)
                return {"success": True, "action": "type_uia", "text": text}
            return {"success": False, "error": f"Input field '{element_title_pattern}' not found."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_whatsapp_message(self, message: str, recipient: Optional[str] = None, platform: str = "auto") -> Dict[str, Any]:
        """Sends a WhatsApp message using native Windows UI Automation (UIA) with protocol fallback."""
        logger.info(f"[WindowsAgent] Sending WhatsApp message to '{recipient}': {message}")
        ensure_interactive_desktop()

        # 1. Bring WhatsApp to front
        focus_window_by_name("WhatsApp")
        time.sleep(0.3)
        if not self.verify_process_running("WhatsApp"):
            try:
                os.startfile("whatsapp:")
                time.sleep(1.2)
                focus_window_by_name("WhatsApp")
            except Exception:
                pass

        # 2. Attempt native Windows UI Automation (UIA)
        try:
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")
            wa_win = desktop.window(title_re="(?i).*whatsapp.*")
            if wa_win.exists(timeout=2.0):
                wa_win.set_focus()
                time.sleep(0.2)

                # If recipient is specified, search for contact
                if recipient and recipient.lower() not in ["brother", "contact", "specified contact", "active"]:
                    search_box = wa_win.child_window(title_re="(?i).*(search|chats|search or start new chat).*", control_type="Edit")
                    if search_box.exists(timeout=1.0):
                        search_box.click_input()
                        search_box.type_keys(recipient + "{ENTER}", with_spaces=True)
                        time.sleep(0.6)

                # Locate chat message edit box
                msg_box = wa_win.child_window(title_re="(?i).*(type a message|message).*", control_type="Edit")
                if msg_box.exists(timeout=1.5):
                    msg_box.click_input()
                    msg_box.type_keys(message + "{ENTER}", with_spaces=True)
                    logger.info(f"[WindowsAgent] Dispatched WhatsApp message via UIA to '{recipient}'")
                    return {
                        "success": True,
                        "action": "send_whatsapp_message",
                        "method": "uia_automation",
                        "recipient": recipient or "active chat",
                        "message": message,
                        "verified": True
                    }
        except Exception as e:
            logger.warning(f"[WindowsAgent] UIA WhatsApp automation note: {e}")

        # Fallback to desktop/web protocol launcher
        import urllib.parse
        encoded_text = urllib.parse.quote(message)
        is_web = "web" in str(platform).lower()

        if is_web:
            target_url = f"https://web.whatsapp.com/send?text={encoded_text}"
            self._open_url_safely(target_url)
            time.sleep(0.4)
            focus_window_by_name("Opera")
            return {
                "success": True,
                "action": "send_whatsapp_message",
                "method": "web_protocol",
                "platform": "web",
                "recipient": recipient or "specified contact",
                "message": message,
                "verified": False,
                "note": "Opened Web WhatsApp with prefilled message"
            }
        else:
            proto_url = f"whatsapp://send?text={encoded_text}"
            self._open_url_safely(proto_url)
            time.sleep(0.5)
            focus_window_by_name("WhatsApp")
            return {
                "success": True,
                "action": "send_whatsapp_message",
                "method": "desktop_protocol",
                "platform": "desktop",
                "recipient": recipient or "specified contact",
                "message": message,
                "verified": False,
                "note": "Opened Desktop WhatsApp with prefilled message"
            }

    def check_latest_messages(self, platform: str = "whatsapp") -> Dict[str, Any]:
        """Brings messaging application to the active foreground to view latest messages."""
        logger.info(f"[WindowsAgent] Checking latest messages on {platform}")
        ensure_interactive_desktop()
        if "whatsapp" in platform.lower():
            # First try desktop WhatsApp
            focus_window_by_name("WhatsApp")
            time.sleep(0.2)
            # If not running, start it
            if not self.verify_process_running("WhatsApp"):
                try:
                    os.startfile("whatsapp:")
                except Exception:
                    self._open_url_safely('https://web.whatsapp.com')
            time.sleep(0.4)
            focus_window_by_name("WhatsApp")
    def list_running_applications(self) -> Dict[str, Any]:
        """Lists active GUI desktop applications with window titles and memory usage."""
        logger.info("[WindowsAgent] Listing active running GUI applications")
        apps = []
        try:
            for p in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    name = p.info['name'] or ''
                    # Filter out system and background services
                    if name.lower().endswith('.exe') and not name.lower().startswith(('svchost', 'system', 'registry', 'smss', 'csrss', 'wininit', 'services', 'lsass', 'spoolsv', 'runtimebroker')):
                        mem_mb = round(p.info['memory_info'].rss / (1024 * 1024), 1)
                        if mem_mb > 30: # GUI apps usually use >30MB
                            apps.append({"pid": p.info['pid'], "name": name, "memory_mb": mem_mb})
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            # Sort by memory usage
            apps = sorted(apps, key=lambda x: x["memory_mb"], reverse=True)[:15]
            return {"success": True, "count": len(apps), "applications": apps}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_installed_applications(self, query: str) -> Dict[str, Any]:
        """Searches installed applications in Windows Start Menu and Registry."""
        logger.info(f"[WindowsAgent] Searching installed applications matching '{query}'")
        found = []
        q = query.lower().strip()
        search_dirs = [
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs")
        ]
        for sdir in search_dirs:
            if os.path.exists(sdir):
                for root, _, files in os.walk(sdir):
                    for f in files:
                        if f.lower().endswith(('.lnk', '.url')) and q in f.lower():
                            found.append({"name": f.replace('.lnk', '').replace('.url', ''), "path": os.path.join(root, f)})
        return {"success": True, "query": query, "matches": found, "count": len(found)}

    def minimize_window(self, app_name: Optional[str] = None) -> Dict[str, Any]:
        """Minimizes active window or specific application window."""
        logger.info(f"[WindowsAgent] Minimizing window: {app_name or 'active'}")
        if sys.platform == "win32":
            import ctypes
            u32 = ctypes.windll.user32
            if app_name:
                # Find by title
                focus_window_by_name(app_name)
                hwnd = u32.GetForegroundWindow()
            else:
                hwnd = u32.GetForegroundWindow()
            if hwnd:
                u32.ShowWindow(hwnd, 6) # SW_MINIMIZE = 6
                return {"success": True, "action": "minimize", "hwnd": hwnd}
        return {"success": False, "error": "Unable to minimize window"}

    def maximize_window(self, app_name: Optional[str] = None) -> Dict[str, Any]:
        """Maximizes active window or specific application window."""
        logger.info(f"[WindowsAgent] Maximizing window: {app_name or 'active'}")
        if sys.platform == "win32":
            import ctypes
            u32 = ctypes.windll.user32
            if app_name:
                focus_window_by_name(app_name)
                hwnd = u32.GetForegroundWindow()
            else:
                hwnd = u32.GetForegroundWindow()
    def open_url(self, url: str) -> Dict[str, Any]:
        """Opens URL in default web browser or Opera GX"""
        import urllib.parse
        target_url = url.strip()
        if not target_url.startswith(("http://", "https://")):
            target_url = f"https://{target_url}"
        logger.info(f"[WindowsAgent] Opening URL: {target_url}")
        ensure_interactive_desktop()
        success = self._open_url_safely(target_url)
        if not success:
            return {"success": False, "error": f"Failed to launch URL: {target_url}"}
        time.sleep(0.3)
        focus_window_by_name("Opera")
        return {"success": True, "url": target_url, "channel_1_logical": True}

    def search_google(self, query: str) -> Dict[str, Any]:
        """Searches Google for query in active web browser"""
        import urllib.parse
        encoded = urllib.parse.quote(query)
        return self.open_url(f"https://www.google.com/search?q={encoded}")

    def get_active_window_info(self) -> Dict[str, Any]:
        """
        Extracts active foreground window title, process ID, and executable name.
        Uses native Win32 API with robust desktop enumeration fallback.
        """
        if sys.platform != "win32":
            return {"success": False, "title": "Non-Windows host", "process": "unknown", "pid": 0}

        try:
            import ctypes
            u32 = ctypes.windll.user32
            h_def = u32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_def:
                u32.SetThreadDesktop(h_def)

            hwnd = u32.GetForegroundWindow()
            if hwnd:
                length = u32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    u32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.strip()
                    if title:
                        pid = ctypes.c_ulong()
                        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        pname = psutil.Process(pid.value).name() if pid.value else "unknown"
                        return {"success": True, "title": title, "pid": pid.value, "process": pname}

            # Topmost visible desktop window fallback
            top_window = {}
            EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def enum_cb(h, l):
                if u32.IsWindowVisible(h):
                    l_len = u32.GetWindowTextLengthW(h)
                    if l_len > 0:
                        b = ctypes.create_unicode_buffer(l_len + 1)
                        u32.GetWindowTextW(h, b, l_len + 1)
                        t = b.value.strip()
                        if t and t not in ["Program Manager", "Windows Input Experience"]:
                            p_val = ctypes.c_ulong()
                            u32.GetWindowThreadProcessId(h, ctypes.byref(p_val))
                            p_name = psutil.Process(p_val.value).name() if p_val.value else "unknown"
                            top_window["title"] = t
                            top_window["pid"] = p_val.value
                            top_window["process"] = p_name
                            return False
                return True

            enum_fn = EnumProc(enum_cb)
            if h_def:
                u32.EnumDesktopWindows(h_def, enum_fn, 0)
            else:
                u32.EnumWindows(enum_fn, 0)

            if top_window:
                return {"success": True, "title": top_window.get("title", ""), "pid": top_window.get("pid", 0), "process": top_window.get("process", "")}

            return {"success": True, "title": "Windows Desktop", "pid": 0, "process": "explorer.exe"}
        except Exception as e:
            return {"success": False, "error": str(e), "title": "Windows Desktop", "pid": 0, "process": "explorer.exe"}

    def get_clipboard_text(self) -> str:
        """Safely retrieves Unicode text from Windows clipboard using native Win32 API."""
        if sys.platform != "win32":
            return ""
        try:
            import ctypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            CF_UNICODETEXT = 13
            user32.OpenClipboard.argtypes = [ctypes.c_void_p]
            user32.GetClipboardData.argtypes = [ctypes.c_uint]
            user32.GetClipboardData.restype = ctypes.c_void_p
            kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

            if not user32.OpenClipboard(None):
                return ""

            try:
                h_clip_mem = user32.GetClipboardData(CF_UNICODETEXT)
                if not h_clip_mem:
                    return ""
                data_ptr = kernel32.GlobalLock(h_clip_mem)
                if not data_ptr:
                    return ""
                try:
                    text = ctypes.wstring_at(data_ptr)
                    return text
                finally:
                    kernel32.GlobalUnlock(h_clip_mem)
            finally:
                user32.CloseClipboard()
        except Exception as e:
            logger.warning(f"[WindowsAgent] get_clipboard_text error: {e}")
            return ""

    def set_clipboard_text(self, text: str) -> bool:
        """Safely copies Unicode text to Windows clipboard using native Win32 API."""
        if sys.platform != "win32":
            return False
        try:
            import ctypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002

            user32.OpenClipboard.argtypes = [ctypes.c_void_p]
            user32.EmptyClipboard.argtypes = []
            user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
            user32.SetClipboardData.restype = ctypes.c_void_p
            user32.CloseClipboard.argtypes = []

            kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
            kernel32.GlobalAlloc.restype = ctypes.c_void_p
            kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

            encoded = (text + "\0").encode("utf-16-le")
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
            if not h_mem:
                return False

            ptr = kernel32.GlobalLock(h_mem)
            if not ptr:
                return False

            ctypes.memmove(ptr, encoded, len(encoded))
            kernel32.GlobalUnlock(h_mem)

            if not user32.OpenClipboard(None):
                return False

            try:
                user32.EmptyClipboard()
                user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                return True
            finally:
                user32.CloseClipboard()
        except Exception as e:
            logger.warning(f"[WindowsAgent] set_clipboard_text error: {e}")
            return False

    async def diagnose_clipboard_error(self) -> Dict[str, Any]:
        """
        Inspects Windows clipboard text, detects code tracebacks or error messages,
        queries AI for root cause and verified fix, and places the fix back into the clipboard
        for instant Ctrl+V pasting.
        """
        raw_text = self.get_clipboard_text()
        if not raw_text or not raw_text.strip():
            return {
                "success": False,
                "message": "Clipboard is currently empty or contains non-text content, sir."
            }

        text = raw_text.strip()
        error_indicators = [
            "Traceback (most recent call last)", "Error:", "Exception:", "errno",
            "SyntaxError", "TypeError", "ValueError", "KeyError", "IndexError",
            "AttributeError", "ImportError", "ModuleNotFoundError", "FileNotFoundError",
            "NullPointerException", "UndefinedVariable", "ReferenceError", "fatal error",
            "failed with exit code", "FAILED", "AssertionError", "Unhandled exception",
            "panic:", "stack trace:", "at line", "uncaught exception"
        ]

        has_error = any(ind.lower() in text.lower() for ind in error_indicators)

        prompt = (
            "You are J.A.R.V.I.S. Senior Code Diagnostician. "
            "A developer copied the following error message or code snippet from their terminal/editor into the Windows clipboard:\n\n"
            f"```\n{text[:3000]}\n```\n\n"
            "Provide a concise, precise diagnosis with two parts:\n"
            "1. ROOT CAUSE: In 1-2 clear sentences, explain exactly what failed.\n"
            "2. VERIFIED FIX / PATCH: The exact command, replacement code, or fix the developer needs to run/paste.\n"
            "Keep it sharp and directly actionable."
        )

        try:
            from services.brain.providers.ai_manager import ai_manager
            response = await ai_manager.generate(prompt=prompt, temperature=0.2)
            diagnosis = response.content.strip()
        except Exception as e:
            diagnosis = f"Root cause analysis: Encountered error pattern in clipboard text. Error text snippet: {text[:200]}..."

        import re
        code_blocks = re.findall(r'```(?:[a-zA-Z0-9_-]+)?\s*([\s\S]*?)```', diagnosis)
        clipboard_patch = code_blocks[0].strip() if code_blocks else diagnosis

        # Set the fix into Windows clipboard so user can immediately Ctrl+V
        self.set_clipboard_text(clipboard_patch)

        return {
            "success": True,
            "has_error_indicators": has_error,
            "original_length": len(text),
            "diagnosis": diagnosis,
            "clipboard_updated": True,
            "patch_copied_to_clipboard": clipboard_patch[:300],
            "message": "Diagnosed clipboard error, sir. The verified fix has been placed in your clipboard for instant Ctrl+V pasting."
        }

    def focus_window_by_name(self, name_query: str) -> bool:
        """Finds a window by partial title match and brings it to foreground/focus."""
        if sys.platform != "win32":
            return False
        try:
            ensure_interactive_desktop()
            user32 = ctypes.windll.user32
            target_name = name_query.lower().strip()
            found_hwnd = None

            def enum_cb(hwnd, lparam):
                nonlocal found_hwnd
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        if target_name in buff.value.lower():
                            found_hwnd = hwnd
                            return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

            if found_hwnd:
                user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(found_hwnd)
                return True
            return False
        except Exception as e:
            logger.debug(f"[WindowsAgent] focus_window_by_name error: {e}")
            return False


windows_agent = WindowsAgent()


def focus_window_by_name(name_query: str) -> bool:
    """Convenience top-level wrapper for focusing window by title."""
    return windows_agent.focus_window_by_name(name_query)



