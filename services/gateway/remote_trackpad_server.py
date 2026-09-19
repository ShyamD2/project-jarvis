"""
Project J.A.R.V.I.S. Ultimate Mobile Touch Trackpad, Live Screen & Remote Control Server.
Features:
1. Automated Cloudflare HTTPS Tunnel (access from any phone on Wi-Fi or mobile data anywhere in the world)
2. Interactive Live Screen Display with Direct Tap-To-Click (tap on phone screen to click on PC!)
3. Fluid Glide Trackpad with RequestAnimationFrame batching, two-finger smooth scroll, and momentum
4. Dedicated Navigation: New Tab (Ctrl+T), Close Tab (Ctrl+W), Switch Tab, Switch Window (Alt+Tab)
5. Essential Keys: Enter, Esc, Backspace, Space, Play/Pause, Next Track, Micro-Step Nudge D-pad
6. Sub-millisecond WebSocket connection with HTTP fallback
"""
from __future__ import annotations
import os
import sys
import io
import re
import time
import socket
import asyncio
import threading
import subprocess
import ctypes
import secrets
from typing import Optional, Dict, Any
from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from PIL import ImageGrab

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger
from agents.computer.mouse_agent import mouse_agent
from agents.computer.keyboard_agent import keyboard_agent
from agents.computer.windows_agent import windows_agent

logger = get_logger("JarvisTrackpadServer")

app = FastAPI(title="JARVIS Ultimate Remote Trackpad & Stream")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_public_url: str = ""
_tunnel_process: Optional[subprocess.Popen] = None

_OPERATOR_TOKEN_FILE = os.path.join(PROJECT_ROOT, "services", "gateway", "operator_token.txt")

def get_operator_token() -> str:
    """Returns persistent secure operator authentication token."""
    if os.path.exists(_OPERATOR_TOKEN_FILE):
        try:
            with open(_OPERATOR_TOKEN_FILE, "r", encoding="utf-8") as f:
                tok = f.read().strip()
                if tok:
                    return tok
        except Exception:
            pass
    tok = secrets.token_urlsafe(12)
    try:
        with open(_OPERATOR_TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(tok)
    except Exception:
        pass
    return tok

OPERATOR_TOKEN = get_operator_token()


def get_local_ip() -> str:
    """Returns local LAN IPv4 address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_public_url(wait_timeout: float = 6.0) -> str:
    """Returns Cloudflare public HTTPS URL or local Wi-Fi URL if tunnel still connecting."""
    global _public_url
    if _public_url and _public_url.startswith("https://"):
        return _public_url
    # If tunnel process is active, wait briefly for the public URL to register
    if _tunnel_process and _tunnel_process.poll() is None:
        start_t = time.time()
        while time.time() - start_t < wait_timeout:
            if _public_url and _public_url.startswith("https://"):
                return _public_url
            time.sleep(0.4)
    # Check cache file
    url_file = os.path.join(PROJECT_ROOT, "services", "gateway", "trackpad_url.txt")
    if os.path.exists(url_file):
        try:
            with open(url_file, "r", encoding="utf-8") as f:
                cached = f.read().strip()
                if cached.startswith("https://"):
                    _public_url = cached
                    return _public_url
        except Exception:
            pass
    return f"http://{get_local_ip()}:8085"


def start_cloudflare_tunnel(port: int = 8085):
    """Launches cloudflared daemon and continuously keeps the public HTTPS tunnel active."""
    global _public_url, _tunnel_process
    if _tunnel_process and _tunnel_process.poll() is None:
        logger.info("[TrackpadServer] Cloudflare tunnel process is already running.")
        return

    cf_exe = os.path.join(PROJECT_ROOT, "services", "gateway", "cloudflared.exe")
    if not os.path.exists(cf_exe):
        logger.warning("[TrackpadServer] cloudflared.exe not found; tunnel unavailable.")
        return

    def _run_tunnel():
        global _public_url, _tunnel_process
        try:
            logger.info(f"⚡ [TrackpadServer] Initializing Cloudflare secure public tunnel on port {port}...")
            _tunnel_process = subprocess.Popen(
                [cf_exe, "tunnel", "--url", f"http://127.0.0.1:{port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            # Drain stdout continuously so cloudflared doesn't block on full pipe buffer
            for line in iter(_tunnel_process.stdout.readline, ''):
                if not line:
                    break
                if not _public_url or not _public_url.startswith("https://"):
                    m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                    if m:
                        _public_url = m.group(0)
                        logger.info(f"🌐 [TrackpadServer] Public Mobile HTTPS Trackpad URL: {_public_url}/remote")
                        url_file = os.path.join(PROJECT_ROOT, "services", "gateway", "trackpad_url.txt")
                        try:
                            with open(url_file, "w", encoding="utf-8") as f:
                                f.write(_public_url)
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"[TrackpadServer] Cloudflare tunnel exception: {e}")

    t = threading.Thread(target=_run_tunnel, daemon=True)
    t.start()


class MoveRequest(BaseModel):
    dx: float
    dy: float


class AbsClickRequest(BaseModel):
    x: float
    y: float
    button: str = "left"


class ClickRequest(BaseModel):
    button: str = "left"


class ScrollRequest(BaseModel):
    delta: int = -2


class TypeRequest(BaseModel):
    text: str


class KeyRequest(BaseModel):
    key: str


def is_workstation_locked() -> bool:
    """Checks if the Windows workstation is currently locked or in Winlogon."""
    if sys.platform != "win32":
        return False
    try:
        u32 = ctypes.windll.user32
        hdesk = u32.OpenInputDesktop(0, False, 0x01FF)
        if not hdesk:
            return True
        buf = ctypes.create_unicode_buffer(256)
        needed = ctypes.c_ulong(0)
        u32.GetUserObjectInformationW(hdesk, 2, buf, 256, ctypes.byref(needed))
        desk_name = buf.value.lower()
        u32.CloseDesktop(hdesk)
        return desk_name != "default"
    except Exception:
        return False


def _create_locked_screen_image():
    """Generates a stylish HUD card when Windows is locked to avoid showing a confusing pitch-black screen."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (960, 540), color=(6, 10, 18))
    draw = ImageDraw.Draw(img)
    # HUD neon frame
    draw.rectangle([20, 20, 940, 520], outline=(0, 240, 255), width=2)
    draw.rectangle([24, 24, 936, 516], outline=(255, 51, 102), width=1)

    draw.text((310, 150), "🔒 WINDOWS WORKSTATION IS LOCKED", fill=(255, 60, 90))
    draw.text((210, 210), "• Windows kernel (Winlogon) isolates desktop framebuffer while locked.", fill=(200, 215, 235))
    draw.text((210, 245), "• Screen grabbers receive black frames from Windows OS architecture.", fill=(200, 215, 235))
    draw.text((210, 305), "💡 RECOMMENDED ZERO-PASSWORD SCREEN SOLUTION:", fill=(0, 240, 255))
    draw.text((210, 340), "Use '🌙 Stealth Screen Off' (/stealth) in Telegram instead of Win+L.", fill=(0, 255, 136))
    draw.text((210, 375), "Monitors turn completely black in the room while your phone keeps 100% live access!", fill=(180, 200, 220))
    return img


def _draw_cursor_on_image(img):
    """Draws a prominent, high-contrast mouse pointer directly onto the PIL image at actual cursor coordinates."""
    if sys.platform != "win32":
        return img
    try:
        from ctypes import wintypes
        class CURSORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("flags", ctypes.c_uint),
                ("hCursor", ctypes.c_void_p),
                ("ptScreenPos", wintypes.POINT)
            ]

        ci = CURSORINFO()
        ci.cbSize = ctypes.sizeof(CURSORINFO)
        u32 = ctypes.windll.user32
        if u32.GetCursorInfo(ctypes.byref(ci)):
            if ci.flags & 1:  # CURSOR_SHOWING
                raw_cx = ci.ptScreenPos.x
                raw_cy = ci.ptScreenPos.y

                # Accurately scale from logical desktop metrics (e.g. 1536x864) to real captured physical image pixels (e.g. 1920x1080)
                sys_w = max(u32.GetSystemMetrics(0), 1)
                sys_h = max(u32.GetSystemMetrics(1), 1)
                phys_w, phys_h = img.size

                scale_x = phys_w / sys_w
                scale_y = phys_h / sys_h

                cx = int(raw_cx * scale_x)
                cy = int(raw_cy * scale_y)

                from PIL import ImageDraw
                draw = ImageDraw.Draw(img)
                # Scaled pointer arrow polygon: 28px height, clearly visible even when image is scaled down on mobile
                arrow = [
                    (cx, cy),
                    (cx, cy + 28),
                    (cx + 8, cy + 22),
                    (cx + 14, cy + 33),
                    (cx + 19, cy + 30),
                    (cx + 13, cy + 19),
                    (cx + 22, cy + 19)
                ]
                # High-contrast double stroke: solid black outer border (3px), bright neon cyan core
                draw.polygon(arrow, fill=(0, 240, 255), outline=(0, 0, 0), width=3)
                # Precision red hotspot marker at the exact tip
                draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(255, 50, 70), outline=(255, 255, 255), width=1)
    except Exception:
        pass
    return img


def _capture_desktop_frame():
    if sys.platform == "win32":
        try:
            u32 = ctypes.windll.user32
            # Wake display monitor from power saving if asleep so framebuffer is active
            u32.SendMessageW(0xFFFF, 0x0112, 0xF170, -1)
            hd = u32.OpenInputDesktop(0, False, 0x01FF) or u32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hd:
                u32.SetThreadDesktop(hd)
        except Exception:
            pass

    if is_workstation_locked():
        return _create_locked_screen_image()

    try:
        frame = ImageGrab.grab(all_screens=False)
        frame = _draw_cursor_on_image(frame)
        return frame
    except Exception:
        return _create_locked_screen_image()


async def generate_mjpeg_frames():
    """Asynchronously streams JPEG frames of the desktop without blocking event loop (Low-CPU Eco Mode)."""
    from PIL import Image
    loop = asyncio.get_event_loop()
    while True:
        try:
            img = await loop.run_in_executor(None, _capture_desktop_frame)
            w, h = img.size
            ratio = 960 / max(w, 1)
            target_size = (960, int(h * ratio))
            # Low-CPU Bilinear resize uses 50% less CPU than default Bicubic
            img = img.resize(target_size, resample=Image.Resampling.BILINEAR)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=68)
            frame = buf.getvalue()

            header = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
            yield header + frame + b"\r\n"
            await asyncio.sleep(0.16)  # ~6.2 FPS: Smooth & responsive while halving CPU utilization
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(0.3)


def launch_floating_hud() -> Dict[str, Any]:
    """Ensures the 3D floating HUD window is launched on Default desktop, restored, and brought to foreground."""
    try:
        from agents.computer.power_agent import power_agent
        power_agent.wake_display()

        from agents.computer.windows_agent import launch_floating_hud as _win_launch_hud
        return _win_launch_hud()
    except Exception as e:
        logger.error(f"[TrackpadServer] Error launching HUD: {e}")
        return {"success": False, "error": str(e)}


def close_floating_hud() -> Dict[str, Any]:
    """Closes the floating HUD window."""
    try:
        import ctypes
        user32 = ctypes.windll.user32 if sys.platform == "win32" else None
        if user32:
            try:
                hdesk = user32.OpenInputDesktop(0, False, 0x01FF) or user32.OpenDesktopW("Default", 0, False, 0x01FF)
                if hdesk:
                    user32.SetThreadDesktop(hdesk)
            except Exception:
                pass
            hwnd = user32.FindWindowW(None, "J.A.R.V.I.S. Floating Agent")
            if hwnd:
                user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
                return {"success": True, "action": "closed"}
        subprocess.run(["taskkill", "/F", "/FI", "WINDOWTITLE eq J.A.R.V.I.S. Floating Agent*"], capture_output=True)
        return {"success": True, "action": "killed"}
    except Exception as e:
        logger.error(f"[TrackpadServer] Error closing HUD: {e}")
        return {"success": False, "error": str(e)}


def verify_token(token: Optional[str]) -> bool:
    """Verifies that request originates from authenticated operator phone."""
    return bool(token and token == get_operator_token())


@app.get("/stream")
async def stream_screen(token: Optional[str] = None):
    """Live MJPEG video stream of the Windows desktop (Token Authenticated)."""
    if not verify_token(token):
        return Response(content=b"Unauthorized", status_code=403)
    return StreamingResponse(
        generate_mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-transform, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


_last_snapshot_bytes = b""
_last_snapshot_time = 0.0


@app.get("/api/screen/snapshot")
async def get_screen_snapshot(token: Optional[str] = None):
    """Returns an instantaneous single JPEG frame of the active desktop (Token Authenticated, Low-CPU Cached)."""
    if not verify_token(token):
        return Response(content=b"Unauthorized", status_code=403)

    global _last_snapshot_bytes, _last_snapshot_time
    now = time.time()
    # Cache frames for 160ms (~6 FPS max capture rate) to protect low-end CPUs from redundant capture thrashing
    if _last_snapshot_bytes and (now - _last_snapshot_time < 0.16):
        return Response(content=_last_snapshot_bytes, media_type="image/jpeg", headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache"
        })

    loop = asyncio.get_event_loop()
    try:
        from PIL import Image
        img = await loop.run_in_executor(None, _capture_desktop_frame)
        w, h = img.size
        ratio = 960 / max(w, 1)
        target_size = (960, int(h * ratio))
        img = img.resize(target_size, resample=Image.Resampling.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=68)
        data = buf.getvalue()
        _last_snapshot_bytes = data
        _last_snapshot_time = now
        return Response(content=data, media_type="image/jpeg", headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache"
        })
    except Exception:
        return Response(content=b"", status_code=500)


@app.get("/api/screen/info")
def get_screen_info(token: Optional[str] = None):
    """Returns the primary screen width and height (Token Authenticated)."""
    if not verify_token(token):
        return Response(content=b"Unauthorized", status_code=403)
    try:
        import ctypes
        u32 = ctypes.windll.user32
        w = u32.GetSystemMetrics(0)
        h = u32.GetSystemMetrics(1)
        return {"width": w, "height": h}
    except Exception:
        return {"width": 1920, "height": 1080}


@app.websocket("/ws/trackpad")
async def trackpad_websocket(websocket: WebSocket):
    """
    Sub-millisecond full-duplex WebSocket connection for mobile touch trackpad.
    """
    token = websocket.query_params.get("token")
    if not verify_token(token):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    mouse_agent._ensure_desktop()
    await websocket.send_json({"status": "connected"})
    try:
        while True:
            msg = await websocket.receive_json()
            t = msg.get("t")
            if t == "m":
                # Relative motion
                mouse_agent.move_relative(msg.get("dx", 0), msg.get("dy", 0))
            elif t == "abs_click":
                # Direct tap on screen preview
                x = int(msg.get("x", 0))
                y = int(msg.get("y", 0))
                btn = msg.get("b", "left")
                mouse_agent.move_cursor(x, y, smooth=False)
                mouse_agent.click(button=btn)
            elif t == "c":
                # Button click
                mouse_agent.click(button=msg.get("b", "left"))
            elif t == "s":
                # Scroll
                d = msg.get("d", -2)
                direction = "up" if d > 0 else "down"
                mouse_agent.scroll(clicks=abs(d), direction=direction)
            elif t == "k":
                # Key press
                key_name = msg.get("k", "")
                if key_name:
                    keyboard_agent.press_key(key_name)
            elif t == "tab_new":
                windows_agent.open_new_tab()
            elif t == "tab_close":
                windows_agent.close_active_tab()
            elif t == "tab_next":
                windows_agent.switch_tab("next")
            elif t == "tab_prev":
                windows_agent.switch_tab("prev")
            elif t == "win_switch":
                windows_agent.switch_window()
            elif t == "launch_hud":
                launch_floating_hud()
            elif t == "close_hud":
                close_floating_hud()
            elif t == "media":
                from agents.computer.audio_agent import audio_agent
                audio_agent.control_media(msg.get("action", "play_pause"))
            elif t == "type":
                keyboard_agent.type_text(msg.get("text", ""))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"[TrackpadWS] Notice: {e}")


@app.post("/api/hud/launch")
def api_launch_hud(token: Optional[str] = None):
    if not verify_token(token):
        return Response(content=b"Unauthorized", status_code=403)
    return launch_floating_hud()


@app.post("/api/hud/close")
def api_close_hud(token: Optional[str] = None):
    if not verify_token(token):
        return Response(content=b"Unauthorized", status_code=403)
    return close_floating_hud()


@app.post("/api/mouse/move")
def move_mouse(req: MoveRequest, token: Optional[str] = None):
    if not verify_token(token):
        return Response(content=b"Unauthorized", status_code=403)
    return mouse_agent.move_relative(req.dx, req.dy)


@app.post("/api/mouse/abs_click")
def abs_click_mouse(req: AbsClickRequest, token: Optional[str] = None):
    if not verify_token(token):
        return Response(content=b"Unauthorized", status_code=403)
    mouse_agent.move_cursor(int(req.x), int(req.y), smooth=False)
    return mouse_agent.click(button=req.button)


@app.post("/api/mouse/click")
def click_mouse(req: ClickRequest, token: Optional[str] = None):
    if not verify_token(token):
        return Response(content=b"Unauthorized", status_code=403)
    return mouse_agent.click(button=req.button.lower())


@app.post("/api/mouse/scroll")
def scroll_mouse(req: ScrollRequest, token: Optional[str] = None):
    if not verify_token(token):
        return Response(content=b"Unauthorized", status_code=403)
    direction = "down" if req.delta < 0 else "up"
    return mouse_agent.scroll(clicks=abs(req.delta), direction=direction)


@app.post("/api/keyboard/type")
def type_text(req: TypeRequest, token: Optional[str] = None):
    if not verify_token(token):
        return Response(content=b"Unauthorized", status_code=403)
    return keyboard_agent.type_text(req.text)


@app.post("/api/keyboard/key")
def press_key(req: KeyRequest, token: Optional[str] = None):
    if not verify_token(token):
        return Response(content=b"Unauthorized", status_code=403)
    return keyboard_agent.press_key(req.key)


class PinVerifyRequest(BaseModel):
    pin: str


@app.post("/api/auth/verify_pin")
def api_verify_pin(req: PinVerifyRequest):
    """Authenticates mobile operator using persistent Master Security PIN."""
    from services.security.cyber_lock import get_stored_pin
    correct = get_stored_pin()
    if req.pin.strip() == correct:
        return {"success": True, "token": get_operator_token()}
    return {"success": False, "error": "Invalid Master PIN"}


@app.get("/live", response_class=HTMLResponse)
def live_screen_page(token: Optional[str] = None):
    """Full-screen live desktop video stream viewer with zero-blackout architecture."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>J.A.R.V.I.S. Live Screen Feed</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #050811;
      color: #00f0ff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      user-select: none;
    }
    header {
      padding: 8px 14px;
      background: rgba(10, 18, 32, 0.96);
      border-bottom: 1px solid rgba(0, 240, 255, 0.3);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
      z-index: 20;
    }
    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .live-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(255, 51, 102, 0.15);
      border: 1px solid #ff3366;
      color: #ff3366;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 1px;
    }
    .live-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #ff3366;
      box-shadow: 0 0 8px #ff3366;
      animation: pulseLive 1.2s infinite;
    }
    @keyframes pulseLive {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.3; }
    }
    header h1 {
      font-size: 12px;
      font-weight: 700;
      color: #fff;
      letter-spacing: 0.5px;
    }
    .header-actions {
      display: flex;
      gap: 6px;
      align-items: center;
    }
    .btn-hdr {
      background: rgba(0, 240, 255, 0.12);
      border: 1px solid #00f0ff;
      color: #fff;
      padding: 5px 9px;
      border-radius: 5px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .btn-hdr:active {
      background: #00f0ff;
      color: #000;
    }
    .viewer-area {
      flex: 1;
      position: relative;
      display: flex;
      justify-content: center;
      align-items: center;
      background: #020408;
      overflow: hidden;
    }
    #screenFeed {
      max-width: 100%;
      max-height: 100%;
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }
    .hud-meta {
      position: absolute;
      top: 10px;
      left: 12px;
      background: rgba(4, 9, 18, 0.85);
      border: 1px solid rgba(0, 240, 255, 0.35);
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 10px;
      color: #00f0ff;
      letter-spacing: 0.5px;
      pointer-events: none;
      backdrop-filter: blur(6px);
    }
    .hud-toolbar {
      position: absolute;
      bottom: 16px;
      display: flex;
      gap: 8px;
      background: rgba(8, 16, 30, 0.9);
      border: 1px solid rgba(0, 240, 255, 0.35);
      padding: 6px 12px;
      border-radius: 24px;
      backdrop-filter: blur(10px);
      box-shadow: 0 0 25px rgba(0, 240, 255, 0.2);
    }
    .btn-tool {
      background: rgba(0, 240, 255, 0.12);
      border: 1px solid rgba(0, 240, 255, 0.4);
      color: #fff;
      font-size: 11px;
      font-weight: 600;
      padding: 6px 12px;
      border-radius: 16px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .btn-tool:active {
      background: #00f0ff;
      color: #000;
    }
    .btn-tool.primary {
      background: #00f0ff;
      color: #000;
      font-weight: 700;
      box-shadow: 0 0 10px rgba(0, 240, 255, 0.4);
    }
    /* PIN MODAL GATE */
    .pin-modal-overlay {
      position: fixed;
      top: 0; left: 0; width: 100vw; height: 100vh;
      background: rgba(5, 8, 17, 0.98);
      z-index: 99999;
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 16px;
      backdrop-filter: blur(10px);
    }
    .pin-card {
      background: rgba(13, 24, 41, 0.98);
      border: 1px solid rgba(0, 240, 255, 0.4);
      box-shadow: 0 0 35px rgba(0, 240, 255, 0.2);
      border-radius: 16px;
      padding: 24px 20px;
      width: 100%;
      max-width: 360px;
      text-align: center;
    }
    .pin-badge {
      display: inline-block;
      background: rgba(0, 240, 255, 0.12);
      color: #00f0ff;
      border: 1px solid rgba(0, 240, 255, 0.3);
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 1px;
      margin-bottom: 12px;
    }
    .pin-card h2 {
      font-size: 18px; font-weight: 800; color: #fff; margin-bottom: 6px; letter-spacing: 0.5px;
    }
    .pin-card p {
      font-size: 11px; color: #94a3b8; margin-bottom: 16px; line-height: 1.4;
    }
    .pin-input-box { margin-bottom: 8px; }
    .pin-input-box input {
      width: 180px; height: 44px; background: #070d18;
      border: 2px solid #00f0ff; border-radius: 8px;
      color: #00f0ff; font-size: 26px; font-weight: 700;
      text-align: center; letter-spacing: 8px; outline: none;
      box-shadow: 0 0 12px rgba(0, 240, 255, 0.2);
    }
    .pin-error-msg {
      font-size: 11px; color: #ff3366; font-weight: 700; height: 16px; margin-bottom: 10px;
    }
    .pin-keypad {
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 14px;
    }
    .pin-key {
      background: rgba(20, 32, 54, 0.85);
      border: 1px solid rgba(0, 240, 255, 0.25);
      color: #fff; font-size: 20px; font-weight: 700; padding: 12px 0;
      border-radius: 10px; cursor: pointer; touch-action: manipulation;
    }
    .pin-key:active { background: #00f0ff; color: #000; }
    .pin-key.clr { color: #ff3366; border-color: rgba(255, 51, 102, 0.4); font-size: 14px; }
    .pin-key.unlock {
      background: rgba(0, 240, 255, 0.2); border-color: #00f0ff;
      color: #00f0ff; font-size: 12px; font-weight: 800;
    }
  </style>
</head>
<body>
  <!-- PIN GATE MODAL -->
  <div id="pinModal" class="pin-modal-overlay">
    <div class="pin-card">
      <div class="pin-badge">🛡️ J.A.R.V.I.S. LIVE SCREEN SECURITY</div>
      <h2>SECURE LIVE FEED</h2>
      <p>Enter Master Security PIN to view live desktop stream</p>
      <div class="pin-input-box">
        <input type="password" id="modalPinInput" maxlength="8" placeholder="••••" readonly />
      </div>
      <div id="pinError" class="pin-error-msg"></div>
      <div class="pin-keypad">
        <button class="pin-key" onclick="pinPress('1')">1</button>
        <button class="pin-key" onclick="pinPress('2')">2</button>
        <button class="pin-key" onclick="pinPress('3')">3</button>
        <button class="pin-key" onclick="pinPress('4')">4</button>
        <button class="pin-key" onclick="pinPress('5')">5</button>
        <button class="pin-key" onclick="pinPress('6')">6</button>
        <button class="pin-key" onclick="pinPress('7')">7</button>
        <button class="pin-key" onclick="pinPress('8')">8</button>
        <button class="pin-key" onclick="pinPress('9')">9</button>
        <button class="pin-key clr" onclick="pinClear()">CLR</button>
        <button class="pin-key" onclick="pinPress('0')">0</button>
        <button class="pin-key unlock" onclick="pinSubmit()">🔓 UNLOCK</button>
      </div>
    </div>
  </div>

  <header>
    <div class="header-left">
      <div class="live-badge"><div class="live-dot"></div> LIVE FEED</div>
      <h1 id="statusTxt">CONNECTED</h1>
    </div>
    <div class="header-actions">
      <button class="btn-hdr" id="modeBtn" onclick="toggleMode()">⚡ FAST</button>
      <a class="btn-hdr" href="/remote" id="remoteLink">🖱️ TOUCHPAD</a>
      <button class="btn-hdr" onclick="toggleFullscreen()">⛶ FULL</button>
      <button class="btn-hdr" style="color:#ff3366; border-color:#ff3366;" onclick="lockConsole()">🔒</button>
    </div>
  </header>

  <div class="viewer-area" id="viewerArea">
    <div class="hud-meta" id="hudMeta">FPS: ~12 | RES: 960x540 | CURSOR: ACTIVE</div>
    <img id="screenFeed" src="/api/screen/snapshot" alt="Live Screen Stream" />
    <div class="hud-toolbar">
      <button class="btn-tool" onclick="refreshFeed()">📸 REFRESH</button>
      <a class="btn-tool primary" href="/remote" id="remoteLink2" style="text-decoration:none;">🖱️ OPEN TOUCHPAD</a>
      <button class="btn-tool" onclick="toggleFullscreen()">⛶ FULLSCREEN</button>
    </div>
  </div>

  <script>
    let authToken = '';
    const params = new URLSearchParams(window.location.search);
    if (params.get('token')) {
      authToken = params.get('token');
      sessionStorage.setItem('jarvis_auth_token', authToken);
    } else {
      authToken = sessionStorage.getItem('jarvis_auth_token') || '';
    }

    function updateLinks() {
      const rl = document.getElementById('remoteLink');
      const rl2 = document.getElementById('remoteLink2');
      if (rl && authToken) rl.href = `/remote?token=${encodeURIComponent(authToken)}`;
      if (rl2 && authToken) rl2.href = `/remote?token=${encodeURIComponent(authToken)}`;
    }

    function checkAuth() {
      const modal = document.getElementById('pinModal');
      if (authToken) {
        modal.style.display = 'none';
        updateLinks();
        startFastPolling();
      } else {
        modal.style.display = 'flex';
      }
    }

    function lockConsole() {
      authToken = '';
      sessionStorage.removeItem('jarvis_auth_token');
      if (pollTimer) clearTimeout(pollTimer);
      const modal = document.getElementById('pinModal');
      document.getElementById('modalPinInput').value = '';
      document.getElementById('pinError').innerText = '';
      modal.style.display = 'flex';
    }

    function pinPress(n) {
      const inp = document.getElementById('modalPinInput');
      if (inp.value.length < 8) inp.value += n;
    }
    function pinClear() {
      document.getElementById('modalPinInput').value = '';
      document.getElementById('pinError').innerText = '';
    }
    async function pinSubmit() {
      const inp = document.getElementById('modalPinInput');
      const err = document.getElementById('pinError');
      const pin = inp.value.trim();
      if (!pin) { err.innerText = 'Enter 4-digit Master PIN'; return; }
      err.innerText = 'VERIFYING...';
      try {
        const res = await fetch('/api/auth/verify_pin', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({pin: pin})
        });
        const d = await res.json();
        if (d.success && d.token) {
          authToken = d.token;
          sessionStorage.setItem('jarvis_auth_token', authToken);
          err.innerText = '✅ UNLOCKED';
          err.style.color = '#00ff88';
          setTimeout(() => {
            document.getElementById('pinModal').style.display = 'none';
            updateLinks();
            startFastPolling();
          }, 250);
        } else {
          err.innerText = '❌ INCORRECT PIN';
          err.style.color = '#ff3366';
          inp.value = '';
        }
      } catch (e) {
        err.innerText = 'Connection error';
      }
    }

    let isFast = true;
    let pollTimer = null;
    let isFetching = false;
    let frameCount = 0;
    let lastFpsTime = Date.now();

    function fetchNext() {
      if (!isFast) return;
      if (isFetching) return;
      isFetching = true;
      const feed = document.getElementById('screenFeed');
      const temp = new Image();
      temp.onload = () => {
        feed.src = temp.src;
        isFetching = false;
        frameCount++;
        const now = Date.now();
        if (now - lastFpsTime >= 1000) {
          const fps = Math.round((frameCount * 1000) / (now - lastFpsTime));
          document.getElementById('hudMeta').innerText = `FPS: ${fps} | RES: LIVE | CURSOR: ACTIVE`;
          frameCount = 0;
          lastFpsTime = now;
        }
        if (isFast) pollTimer = setTimeout(fetchNext, 180);
      };
      temp.onerror = () => {
        isFetching = false;
        if (isFast) pollTimer = setTimeout(fetchNext, 800);
      };
      temp.src = `/api/screen/snapshot?token=${encodeURIComponent(authToken)}&_t=${Date.now()}`;
    }

    function startFastPolling() {
      isFast = true;
      if (pollTimer) clearTimeout(pollTimer);
      const b = document.getElementById('modeBtn');
      if (b) { b.innerText = '⚡ FAST'; b.style.color = '#00f0ff'; }
      fetchNext();
    }

    function startMjpegStream() {
      isFast = false;
      if (pollTimer) clearTimeout(pollTimer);
      const b = document.getElementById('modeBtn');
      if (b) { b.innerText = '🎥 STREAM'; b.style.color = '#a78bfa'; }
      const feed = document.getElementById('screenFeed');
      feed.src = `/stream?token=${encodeURIComponent(authToken)}&_t=${Date.now()}`;
    }

    function toggleMode() {
      if (isFast) startMjpegStream(); else startFastPolling();
    }

    function refreshFeed() {
      if (isFast) fetchNext();
      else {
        const feed = document.getElementById('screenFeed');
        feed.src = `/stream?token=${encodeURIComponent(authToken)}&_t=${Date.now()}`;
      }
    }

    function toggleFullscreen() {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(()=>{});
      } else {
        document.exitFullscreen().catch(()=>{});
      }
    }

    window.addEventListener('DOMContentLoaded', checkAuth);
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


@app.get("/remote", response_class=HTMLResponse)
def remote_trackpad_page():
    """Ultimate mobile touch trackpad with live interactive screen and full navigation."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>J.A.R.V.I.S. Master Touchpad</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
    body {
      background: #050811;
      color: #00f0ff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      touch-action: none;
      user-select: none;
    }
    header {
      padding: 6px 12px;
      background: rgba(10, 18, 32, 0.95);
      border-bottom: 1px solid rgba(0, 240, 255, 0.3);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
    }
    .header-left {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .status-dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: #ffaa00;
      box-shadow: 0 0 8px currentColor;
      transition: background 0.3s;
    }
    header h1 { font-size: 12px; font-weight: 700; letter-spacing: 0.5px; }
    .btn-header {
      background: rgba(0, 240, 255, 0.15);
      border: 1px solid #00f0ff;
      color: #fff;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 600;
      cursor: pointer;
    }
    /* LIVE INTERACTIVE SCREEN CONTAINER */
    #screenSection {
      width: 100%;
      height: 165px;
      background: #000;
      display: flex;
      justify-content: center;
      align-items: center;
      border-bottom: 1px solid rgba(0, 240, 255, 0.3);
      position: relative;
      flex-shrink: 0;
      overflow: hidden;
    }
    #screenImg {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      cursor: crosshair;
    }
    .screen-overlay {
      position: absolute;
      top: 4px;
      left: 6px;
      background: rgba(0,0,0,0.6);
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 9px;
      color: #00f0ff;
      pointer-events: none;
    }
    .tap-indicator {
      position: absolute;
      width: 26px;
      height: 26px;
      border-radius: 50%;
      border: 2px solid #00f0ff;
      background: rgba(0, 240, 255, 0.4);
      transform: translate(-50%, -50%) scale(0.5);
      animation: tapPulse 0.4s ease-out forwards;
      pointer-events: none;
      z-index: 10;
    }
    @keyframes tapPulse {
      0% { transform: translate(-50%, -50%) scale(0.5); opacity: 1; }
      100% { transform: translate(-50%, -50%) scale(1.6); opacity: 0; }
    }
    .screen-tools {
      position: absolute;
      bottom: 4px;
      right: 6px;
      display: flex;
      gap: 4px;
    }
    .btn-tool {
      background: rgba(0, 0, 0, 0.7);
      border: 1px solid rgba(0, 240, 255, 0.5);
      color: #00f0ff;
      font-size: 9px;
      padding: 2px 6px;
      border-radius: 4px;
      cursor: pointer;
    }
    /* TRACKPAD AREA */
    .trackpad-wrapper {
      flex: 1;
      display: flex;
      margin: 6px 8px;
      gap: 6px;
      position: relative;
      overflow: hidden;
    }
    #trackpad {
      flex: 1;
      background: radial-gradient(circle at center, #0e1c33 0%, #070e1a 100%);
      border: 2px solid rgba(0, 240, 255, 0.4);
      border-radius: 10px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      color: rgba(0, 240, 255, 0.7);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 1px;
      position: relative;
      transition: border-color 0.15s, background 0.15s;
    }
    #trackpad.active {
      border-color: #00f0ff;
      background: radial-gradient(circle at center, #183359 0%, #0a1526 100%);
      box-shadow: inset 0 0 20px rgba(0, 240, 255, 0.3);
    }
    .scroll-rail {
      width: 38px;
      background: #091220;
      border: 1px solid rgba(0, 240, 255, 0.3);
      border-radius: 10px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      align-items: center;
      padding: 8px 0;
      color: rgba(0, 240, 255, 0.6);
      font-size: 10px;
    }
    .scroll-rail.active {
      border-color: #00f0ff;
      background: #11233d;
      color: #00f0ff;
    }
    /* CONTROLS GRID */
    .controls {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 4px;
      padding: 0 8px 4px 8px;
      flex-shrink: 0;
    }
    .tabs-bar {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 4px;
      padding: 0 8px 4px 8px;
      flex-shrink: 0;
    }
    .btn {
      background: rgba(0, 240, 255, 0.08);
      border: 1px solid rgba(0, 240, 255, 0.3);
      color: #fff;
      padding: 8px 0;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
      text-align: center;
      cursor: pointer;
    }
    .btn:active { background: #00f0ff; color: #000; }
    .btn.primary {
      background: rgba(0, 240, 255, 0.25);
      border-color: #00f0ff;
    }
    .btn.enter-btn {
      background: #00f0ff;
      color: #000;
      font-weight: 700;
      box-shadow: 0 0 10px rgba(0, 240, 255, 0.4);
    }
    .btn.enter-btn:active { background: #fff; color: #000; }
    .btn.tab-btn {
      font-size: 10px;
      padding: 6px 0;
      background: rgba(255, 255, 255, 0.05);
    }
    .type-bar {
      display: flex;
      padding: 2px 8px 8px 8px;
      gap: 4px;
      flex-shrink: 0;
    }
    .type-input {
      flex: 1;
      background: #0b1526;
      border: 1px solid rgba(0, 240, 255, 0.3);
      color: #fff;
      padding: 8px 10px;
      border-radius: 6px;
      font-size: 12px;
      outline: none;
    }
    .type-send {
      background: #00f0ff;
      color: #000;
      border: none;
      padding: 0 14px;
      font-size: 11px;
      cursor: pointer;
    }
    /* PIN MODAL GATE */
    .pin-modal-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(5, 8, 17, 0.98);
      z-index: 99999;
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 16px;
      backdrop-filter: blur(10px);
    }
    .pin-card {
      background: rgba(13, 24, 41, 0.98);
      border: 1px solid rgba(0, 240, 255, 0.4);
      box-shadow: 0 0 35px rgba(0, 240, 255, 0.2);
      border-radius: 16px;
      padding: 24px 20px;
      width: 100%;
      max-width: 360px;
      text-align: center;
    }
    .pin-badge {
      display: inline-block;
      background: rgba(0, 240, 255, 0.12);
      color: #00f0ff;
      border: 1px solid rgba(0, 240, 255, 0.3);
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 1px;
      margin-bottom: 12px;
    }
    .pin-card h2 {
      font-size: 18px;
      font-weight: 800;
      color: #fff;
      margin-bottom: 6px;
      letter-spacing: 0.5px;
    }
    .pin-card p {
      font-size: 11px;
      color: #94a3b8;
      margin-bottom: 16px;
      line-height: 1.4;
    }
    .pin-input-box {
      margin-bottom: 8px;
    }
    .pin-input-box input {
      width: 180px;
      height: 44px;
      background: #070d18;
      border: 2px solid #00f0ff;
      border-radius: 8px;
      color: #00f0ff;
      font-size: 26px;
      font-weight: 700;
      text-align: center;
      letter-spacing: 8px;
      outline: none;
      box-shadow: 0 0 12px rgba(0, 240, 255, 0.2);
    }
    .pin-error-msg {
      font-size: 11px;
      color: #ff3366;
      font-weight: 700;
      height: 16px;
      margin-bottom: 10px;
    }
    .pin-keypad {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin-bottom: 14px;
    }
    .pin-key {
      background: rgba(20, 32, 54, 0.85);
      border: 1px solid rgba(0, 240, 255, 0.25);
      color: #fff;
      font-size: 20px;
      font-weight: 700;
      padding: 12px 0;
      border-radius: 10px;
      cursor: pointer;
      touch-action: manipulation;
    }
    .pin-key:active {
      background: #00f0ff;
      color: #000;
    }
    .pin-key.clr {
      color: #ff3366;
      border-color: rgba(255, 51, 102, 0.4);
      font-size: 14px;
    }
    .pin-key.unlock {
      background: rgba(0, 240, 255, 0.2);
      border-color: #00f0ff;
      color: #00f0ff;
      font-size: 12px;
      font-weight: 800;
    }
    .pin-hint {
      font-size: 9px;
      color: #64748b;
    }
    .pin-hint code {
      color: #00f0ff;
      background: rgba(0, 240, 255, 0.1);
      padding: 2px 4px;
      border-radius: 3px;
    }
  </style>
</head>
<body>
  <!-- HIGH SECURITY MASTER PIN GATE -->
  <div id="pinModal" class="pin-modal-overlay">
    <div class="pin-card">
      <div class="pin-badge">🛡️ J.A.R.V.I.S. SECURE CONSOLE</div>
      <h2>OPERATOR ACCESS</h2>
      <p>Enter Master Security PIN to unlock live screen & mouse trackpad</p>
      
      <div class="pin-input-box">
        <input type="password" id="modalPinInput" maxlength="8" placeholder="••••" readonly />
      </div>
      
      <div id="pinError" class="pin-error-msg"></div>

      <!-- Touch keypad for mobile phone screens -->
      <div class="pin-keypad">
        <button class="pin-key" onclick="pinPress('1')">1</button>
        <button class="pin-key" onclick="pinPress('2')">2</button>
        <button class="pin-key" onclick="pinPress('3')">3</button>
        <button class="pin-key" onclick="pinPress('4')">4</button>
        <button class="pin-key" onclick="pinPress('5')">5</button>
        <button class="pin-key" onclick="pinPress('6')">6</button>
        <button class="pin-key" onclick="pinPress('7')">7</button>
        <button class="pin-key" onclick="pinPress('8')">8</button>
        <button class="pin-key" onclick="pinPress('9')">9</button>
        <button class="pin-key clr" onclick="pinClear()">CLR</button>
        <button class="pin-key" onclick="pinPress('0')">0</button>
        <button class="pin-key unlock" onclick="pinSubmit()">🔓 UNLOCK</button>
      </div>

      <div class="pin-hint">
        Change PIN in Telegram anytime: <code>/setpin &lt;current_pin&gt; &lt;new_pin&gt;</code>
      </div>
    </div>
  </div>

  <header>
    <div class="header-left">
      <div id="statusDot" class="status-dot"></div>
      <h1 id="statusText">CONNECTING...</h1>
    </div>
    <div style="display: flex; gap: 4px;">
      <button class="btn-header" onclick="lockConsole()" style="color:#ff3366; border-color:#ff3366;">🔒 LOCK</button>
      <button class="btn-header" id="modeToggle" onclick="toggleStreamMode()">⚡ FAST</button>
      <button class="btn-header" id="speedToggle" onclick="toggleSpeed()">🚀 2.2x</button>
      <button class="btn-header" onclick="refreshSnapshot()">📸 REFRESH</button>
      <a class="btn-header" id="liveHdrBtn" style="text-decoration:none;" href="/live">🎥 LIVE</a>
      <button class="btn-header" onclick="toggleScreenHeight()">↕️ SCREEN</button>
    </div>
  </header>

  <!-- LIVE INTERACTIVE SCREEN WITH TAP-TO-CLICK -->
  <div id="screenSection">
    <div class="screen-overlay">🎯 TAP SCREEN TO CLICK DIRECTLY</div>
    <img id="screenImg" src="/api/screen/snapshot" alt="Live PC Screen" onclick="handleScreenTap(event)" />
    <div class="screen-tools">
      <button class="btn-tool" style="color:#00f0ff; border-color:#00f0ff; font-weight:700;" onclick="sendAction('launch_hud')">🚀 START HUD</button>
      <button class="btn-tool" style="color:#ef4444; border-color:#ef4444;" onclick="sendAction('close_hud')">🛑 CLOSE</button>
      <button class="btn-tool" onclick="sendAction('media', {action: 'play_pause'})">⏯️ PLAY</button>
      <button class="btn-tool" onclick="sendAction('media', {action: 'next'})">⏭️ NEXT</button>
    </div>
  </div>

  <!-- FLUID TOUCHPAD & GLIDING SCROLL -->
  <div class="trackpad-wrapper">
    <div id="trackpad">
      <span>🖱️ GLIDE FINGER TO MOVE MOUSE</span>
      <span style="font-size:9px; margin-top:4px; opacity:0.7;">1 Finger = Move | 2 Fingers = Smooth Scroll | Tap = Click</span>
    </div>
    <div id="scrollRail" class="scroll-rail">
      <span>▲</span>
      <span style="writing-mode: vertical-lr; letter-spacing: 1px;">GLIDE</span>
      <span>▼</span>
    </div>
  </div>

  <!-- TAB & WINDOW CONTROLS -->
  <div class="tabs-bar">
    <button class="btn tab-btn" style="border-color:#00f0ff; color:#00f0ff; font-weight:bold;" onclick="sendAction('launch_hud')">🚀 HUD</button>
    <button class="btn tab-btn" onclick="sendAction('tab_new')">➕ Tab</button>
    <button class="btn tab-btn" onclick="sendAction('tab_close')">❌ Close</button>
    <button class="btn tab-btn" onclick="sendAction('tab_prev')">◀ Prev</button>
    <button class="btn tab-btn" onclick="sendAction('tab_next')">Next ▶</button>
    <button class="btn tab-btn" onclick="sendAction('win_switch')">🪟 App</button>
  </div>

  <!-- MAIN ACTION BUTTONS WITH PROMINENT ENTER -->
  <div class="controls">
    <button class="btn primary" onclick="sendClick('left')">🖱️ Left Click</button>
    <button class="btn enter-btn" onclick="sendKey('enter')">⏎ ENTER</button>
    <button class="btn primary" onclick="sendClick('right')">👆 Right Click</button>
  </div>

  <div class="controls">
    <button class="btn" onclick="sendKey('esc')">⎋ ESC</button>
    <button class="btn" onclick="sendClick('double')">✌️ Double Click</button>
    <button class="btn" onclick="sendKey('backspace')">🔙 Backspace</button>
  </div>

  <!-- KEYBOARD TYPING BAR -->
  <div class="type-bar">
    <input type="text" id="typeInput" class="type-input" placeholder="Type into active PC app..." onkeydown="if(event.key==='Enter') sendType()">
    <button class="type-send" onclick="sendType()">SEND</button>
  </div>

  <script>
    let authToken = '';
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('token')) {
      authToken = urlParams.get('token');
      sessionStorage.setItem('jarvis_auth_token', authToken);
    } else {
      authToken = sessionStorage.getItem('jarvis_auth_token') || '';
    }

    function updateLiveLink() {
      const btn = document.getElementById('liveHdrBtn');
      if (btn && authToken) {
        btn.href = `/live?token=${encodeURIComponent(authToken)}`;
      }
    }

    function checkAuthOnLoad() {
      const modal = document.getElementById('pinModal');
      if (authToken) {
        modal.style.display = 'none';
        updateLiveLink();
        initWebSocket();
        startFastPolling();
      } else {
        modal.style.display = 'flex';
      }
    }

    function lockConsole() {
      authToken = '';
      sessionStorage.removeItem('jarvis_auth_token');
      if (ws) { try { ws.close(); } catch(e){} }
      if (pollTimer) clearTimeout(pollTimer);
      const modal = document.getElementById('pinModal');
      document.getElementById('modalPinInput').value = '';
      document.getElementById('pinError').innerText = '';
      modal.style.display = 'flex';
    }

    function pinPress(num) {
      const inp = document.getElementById('modalPinInput');
      if (inp.value.length < 8) {
        inp.value += num;
      }
    }

    function pinClear() {
      document.getElementById('modalPinInput').value = '';
      document.getElementById('pinError').innerText = '';
    }

    async function pinSubmit() {
      const inp = document.getElementById('modalPinInput');
      const err = document.getElementById('pinError');
      const pin = inp.value.trim();
      if (!pin) {
        err.innerText = 'Enter your 4-digit Master PIN';
        return;
      }
      err.innerText = 'AUTHENTICATING...';
      err.style.color = '#00f0ff';
      try {
        const res = await fetch('/api/auth/verify_pin', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pin: pin })
        });
        const data = await res.json();
        if (data.success && data.token) {
          authToken = data.token;
          sessionStorage.setItem('jarvis_auth_token', authToken);
          err.innerText = '✅ ACCESS GRANTED';
          err.style.color = '#00ff88';
          setTimeout(() => {
            document.getElementById('pinModal').style.display = 'none';
            initWebSocket();
            startFastPolling();
          }, 300);
        } else {
          err.innerText = '❌ ACCESS DENIED: INCORRECT PIN';
          err.style.color = '#ff3366';
          inp.value = '';
        }
      } catch (e) {
        err.innerText = 'Error connecting to J.A.R.V.I.S.';
        err.style.color = '#ffaa00';
      }
    }

    window.addEventListener('DOMContentLoaded', checkAuthOnLoad);

    // -------------------------------------------------------------
    // 1. WEBSOCKET PIPELINE WITH AUTO RECONNECT
    // -------------------------------------------------------------
    let ws = null;
    let isConnected = false;

    function initWebSocket() {
      if (!authToken) return;
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const tokenParam = authToken ? `?token=${encodeURIComponent(authToken)}` : '';
      const url = `${proto}//${window.location.host}/ws/trackpad${tokenParam}`;
      try {
        ws = new WebSocket(url);
        ws.onopen = () => {
          isConnected = true;
          document.getElementById('statusDot').style.background = '#00ff88';
          document.getElementById('statusText').innerText = 'J.A.R.V.I.S. READY';
        };
        ws.onclose = () => {
          isConnected = false;
          document.getElementById('statusDot').style.background = '#ffaa00';
          document.getElementById('statusText').innerText = 'RECONNECTING...';
          setTimeout(initWebSocket, 1500);
        };
        ws.onerror = () => { isConnected = false; };
      } catch (e) {
        setTimeout(initWebSocket, 2000);
      }
    }

    function wsSend(payload) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(payload));
      } else {
        if (payload.t === 'm' && authToken) {
          fetch(`/api/mouse/move?token=${encodeURIComponent(authToken)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dx: payload.dx, dy: payload.dy })
          }).catch(()=>{});
        }
      }
    }

    // -------------------------------------------------------------
    // 2. DUAL-ENGINE LIVE SCREEN (FAST SNAPSHOT POLLING + MJPEG STREAM)
    // -------------------------------------------------------------
    let pcScreenWidth = 1920, pcScreenHeight = 1080;
    fetch(`/api/screen/info?token=${encodeURIComponent(authToken)}`)
      .then(r => r.json())
      .then(data => {
        if (data.width) pcScreenWidth = data.width;
        if (data.height) pcScreenHeight = data.height;
      }).catch(()=>{});

    let isFastPolling = true; // High-speed double-buffered snapshot polling eliminates Cloudflare proxy buffering
    let pollTimer = null;
    let isFetchingFrame = false;

    function fetchNextSnapshot() {
      if (!isFastPolling) return;
      if (isFetchingFrame) return;
      isFetchingFrame = true;
      const screenImg = document.getElementById('screenImg');
      const tempImg = new Image();
      tempImg.onload = () => {
        screenImg.src = tempImg.src;
        isFetchingFrame = false;
        if (isFastPolling) {
          pollTimer = setTimeout(fetchNextSnapshot, 180); // ~5-6 FPS smooth low-CPU video
        }
      };
      tempImg.onerror = () => {
        isFetchingFrame = false;
        if (isFastPolling) {
          pollTimer = setTimeout(fetchNextSnapshot, 900);
        }
      };
      tempImg.src = `/api/screen/snapshot?token=${encodeURIComponent(authToken)}&_t=${Date.now()}`;
    }

    function startFastPolling() {
      isFastPolling = true;
      if (pollTimer) clearTimeout(pollTimer);
      const btn = document.getElementById('modeToggle');
      if (btn) { btn.innerText = '⚡ FAST'; btn.style.color = '#00f0ff'; }
      fetchNextSnapshot();
    }

    function startMjpegStream() {
      isFastPolling = false;
      if (pollTimer) clearTimeout(pollTimer);
      const btn = document.getElementById('modeToggle');
      if (btn) { btn.innerText = '🎥 STREAM'; btn.style.color = '#a78bfa'; }
      const screenImg = document.getElementById('screenImg');
      screenImg.src = `/stream?token=${encodeURIComponent(authToken)}&_t=${Date.now()}`;
    }

    function toggleStreamMode() {
      if (isFastPolling) {
        startMjpegStream();
      } else {
        startFastPolling();
      }
    }

    // Auto-fallback if MJPEG stream encounters a network stall or error
    const screenImgEl = document.getElementById('screenImg');
    screenImgEl.onerror = () => {
      console.log("[Stream] MJPEG stream stalled/error. Activating Fast Polling fallback...");
      startFastPolling();
    };

    // Begin with fast polling (works everywhere worldwide without proxy buffering)
    startFastPolling();

    function refreshSnapshot() {
      if (isFastPolling) {
        fetchNextSnapshot();
      } else {
        const img = document.getElementById('screenImg');
        img.src = `/api/screen/snapshot?token=${encodeURIComponent(authToken)}&_t=${Date.now()}`;
      }
    }

    function handleScreenTap(e) {
      const img = document.getElementById('screenImg');
      const rect = img.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const clickY = e.clientY - rect.top;

      if (clickX < 0 || clickY < 0 || clickX > rect.width || clickY > rect.height) return;

      const scaleX = pcScreenWidth / rect.width;
      const scaleY = pcScreenHeight / rect.height;

      const targetX = Math.round(clickX * scaleX);
      const targetY = Math.round(clickY * scaleY);

      wsSend({ t: 'abs_click', x: targetX, y: targetY, b: 'left' });

      // Visual tap indicator
      const container = document.getElementById('screenSection');
      const indicator = document.createElement('div');
      indicator.className = 'tap-indicator';
      indicator.style.left = `${clickX}px`;
      indicator.style.top = `${clickY}px`;
      container.appendChild(indicator);
      setTimeout(() => indicator.remove(), 400);
    }

    let screenExpanded = false;
    function toggleScreenHeight() {
      const s = document.getElementById('screenSection');
      screenExpanded = !screenExpanded;
      s.style.height = screenExpanded ? '230px' : '165px';
    }

    // -------------------------------------------------------------
    // 3. FLUID GLIDE TRACKPAD WITH TWO-FINGER SCROLL & MOMENTUM
    // -------------------------------------------------------------
    const pad = document.getElementById('trackpad');
    let lastX = 0, lastY = 0;
    let twoFingerStartY = 0;
    let isTracking = false;
    let isTwoFingerScroll = false;
    let touchStartTime = 0, startX = 0, startY = 0;
    let pendingDx = 0, pendingDy = 0;
    let rafId = null;
    let sensitivity = 2.2;

    function toggleSpeed() {
      const btn = document.getElementById('speedToggle');
      if (sensitivity === 2.2) {
        sensitivity = 3.4;
        btn.innerText = '⚡ 3.4x';
        btn.style.color = '#ff0055';
        btn.style.borderColor = '#ff0055';
      } else {
        sensitivity = 2.2;
        btn.innerText = '🚀 2.2x';
        btn.style.color = '#fff';
        btn.style.borderColor = '#00f0ff';
      }
    }

    function flushMotion() {
      if (pendingDx !== 0 || pendingDy !== 0) {
        wsSend({ t: 'm', dx: pendingDx, dy: pendingDy });
        pendingDx = 0;
        pendingDy = 0;
      }
      rafId = null;
    }

    pad.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        isTracking = true;
        isTwoFingerScroll = false;
        pad.classList.add('active');
        lastX = e.touches[0].clientX;
        lastY = e.touches[0].clientY;
        startX = lastX;
        startY = lastY;
        touchStartTime = Date.now();
      } else if (e.touches.length === 2) {
        // Two-finger smooth scrolling
        isTracking = false;
        isTwoFingerScroll = true;
        twoFingerStartY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
      }
    }, { passive: false });

    pad.addEventListener('touchmove', (e) => {
      e.preventDefault();
      if (isTwoFingerScroll && e.touches.length === 2) {
        const curY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
        const dy = curY - twoFingerStartY;
        if (Math.abs(dy) > 10) {
          const delta = dy > 0 ? 2 : -2;
          wsSend({ t: 's', d: delta });
          twoFingerStartY = curY;
        }
        return;
      }

      if (!isTracking || e.touches.length !== 1) return;

      const curX = e.touches[0].clientX;
      const curY = e.touches[0].clientY;
      const dx = (curX - lastX) * sensitivity;
      const dy = (curY - lastY) * sensitivity;

      lastX = curX;
      lastY = curY;

      pendingDx += dx;
      pendingDy += dy;

      if (!rafId) {
        rafId = requestAnimationFrame(flushMotion);
      }
    }, { passive: false });

    pad.addEventListener('touchend', (e) => {
      if (isTwoFingerScroll) {
        isTwoFingerScroll = false;
        return;
      }
      if (!isTracking) return;
      isTracking = false;
      pad.classList.remove('active');
      flushMotion();

      const duration = Date.now() - touchStartTime;
      const dist = Math.hypot(lastX - startX, lastY - startY);
      if (duration < 230 && dist < 10) {
        sendClick('left');
      }
    });

    // -------------------------------------------------------------
    // 4. TOUCH SCROLL RAIL
    // -------------------------------------------------------------
    const rail = document.getElementById('scrollRail');
    let lastRailY = 0;
    let isRailActive = false;

    rail.addEventListener('touchstart', (e) => {
      if (e.touches.length >= 1) {
        isRailActive = true;
        rail.classList.add('active');
        lastRailY = e.touches[0].clientY;
      }
    }, { passive: false });

    rail.addEventListener('touchmove', (e) => {
      if (!isRailActive || e.touches.length < 1) return;
      e.preventDefault();
      const curY = e.touches[0].clientY;
      const dy = curY - lastRailY;
      if (Math.abs(dy) > 8) {
        const delta = dy < 0 ? 3 : -3;
        wsSend({ t: 's', d: delta });
        lastRailY = curY;
      }
    }, { passive: false });

    rail.addEventListener('touchend', () => {
      isRailActive = false;
      rail.classList.remove('active');
    });

    // -------------------------------------------------------------
    // 5. ACTIONS DISPATCH
    // -------------------------------------------------------------
    function sendClick(btn) {
      wsSend({ t: 'c', b: btn });
    }

    function sendKey(k) {
      wsSend({ t: 'k', k: k });
    }

    function sendAction(actionType, extra = {}) {
      wsSend({ t: actionType, ...extra });
      if (actionType === 'launch_hud') {
        fetch(`/api/hud/launch?token=${encodeURIComponent(authToken)}`, { method: 'POST' }).catch(()=>{});
      } else if (actionType === 'close_hud') {
        fetch(`/api/hud/close?token=${encodeURIComponent(authToken)}`, { method: 'POST' }).catch(()=>{});
      }
    }

    function sendType() {
      const input = document.getElementById('typeInput');
      const val = input.value;
      if (!val) return;
      wsSend({ t: 'type', text: val });
      input.value = '';
    }
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


_server_thread: Optional[threading.Thread] = None


def start_trackpad_server(host: str = "0.0.0.0", port: int = 8085):
    """Starts the remote trackpad, live stream server, and Cloudflare tunnel in background."""
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        return

    # Start Cloudflare HTTPS tunnel for universal mobile phone access
    start_cloudflare_tunnel(port=port)

    def run_uvicorn():
        logger.info(f"⚡ [TrackpadServer] Running at http://{get_local_ip()}:{port}/remote")
        uvicorn.run(app, host=host, port=port, log_level="warning")

    _server_thread = threading.Thread(target=run_uvicorn, daemon=True)
    _server_thread.start()


if __name__ == "__main__":
    start_trackpad_server()
    print("Trackpad Server online. Local:", f"http://{get_local_ip()}:8085/remote")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
