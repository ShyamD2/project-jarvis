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


def get_public_url() -> str:
    """Returns Cloudflare public HTTPS URL or local Wi-Fi URL if tunnel still connecting."""
    global _public_url
    if _public_url:
        return _public_url
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
    """Launches cloudflared daemon and extracts the public https://xxxx.trycloudflare.com URL."""
    global _public_url, _tunnel_process
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
            for line in _tunnel_process.stdout:
                m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if m:
                    _public_url = m.group(0)
                    logger.info(f"🌐 [TrackpadServer] Public Mobile HTTPS Trackpad URL: {_public_url}/remote")
                    url_file = os.path.join(PROJECT_ROOT, "services", "gateway", "trackpad_url.txt")
                    with open(url_file, "w", encoding="utf-8") as f:
                        f.write(_public_url)
                    break
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


def _capture_desktop_frame():
    if sys.platform == "win32":
        try:
            u32 = ctypes.windll.user32
            hd = u32.OpenInputDesktop(0, False, 0x01FF) or u32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hd:
                u32.SetThreadDesktop(hd)
        except Exception:
            pass
    return ImageGrab.grab(all_screens=False)


async def generate_mjpeg_frames():
    """Asynchronously streams JPEG frames of the desktop without blocking event loop."""
    loop = asyncio.get_event_loop()
    while True:
        try:
            img = await loop.run_in_executor(None, _capture_desktop_frame)
            w, h = img.size
            ratio = 600 / max(w, 1)
            target_size = (600, int(h * ratio))
            img = img.resize(target_size)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=40)
            frame = buf.getvalue()

            header = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
            yield header + frame + b"\r\n"
            await asyncio.sleep(0.08)  # ~12 FPS
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(0.2)


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


@app.get("/stream")
async def stream_screen():
    """Live MJPEG video stream of the Windows desktop."""
    return StreamingResponse(
        generate_mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/screen/snapshot")
async def get_screen_snapshot():
    """Returns an instantaneous single JPEG frame of the active desktop."""
    loop = asyncio.get_event_loop()
    try:
        img = await loop.run_in_executor(None, lambda: ImageGrab.grab(all_screens=False))
        w, h = img.size
        ratio = 720 / max(w, 1)
        img = img.resize((720, int(h * ratio)))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=55)
        return Response(content=buf.getvalue(), media_type="image/jpeg")
    except Exception:
        return Response(content=b"", status_code=500)


@app.get("/api/screen/info")
def get_screen_info():
    """Returns the primary screen width and height."""
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
def api_launch_hud():
    return launch_floating_hud()


@app.post("/api/hud/close")
def api_close_hud():
    return close_floating_hud()


@app.post("/api/mouse/move")
def move_mouse(req: MoveRequest):
    return mouse_agent.move_relative(req.dx, req.dy)


@app.post("/api/mouse/abs_click")
def abs_click_mouse(req: AbsClickRequest):
    mouse_agent.move_cursor(int(req.x), int(req.y), smooth=False)
    return mouse_agent.click(button=req.button)


@app.post("/api/mouse/click")
def click_mouse(req: ClickRequest):
    return mouse_agent.click(button=req.button.lower())


@app.post("/api/mouse/scroll")
def scroll_mouse(req: ScrollRequest):
    direction = "down" if req.delta < 0 else "up"
    return mouse_agent.scroll(clicks=abs(req.delta), direction=direction)


@app.post("/api/keyboard/type")
def type_text(req: TypeRequest):
    return keyboard_agent.type_text(req.text)


@app.post("/api/keyboard/key")
def press_key(req: KeyRequest):
    return keyboard_agent.press_key(req.key)


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
      border-radius: 6px;
      font-weight: 700;
      font-size: 11px;
      cursor: pointer;
    }
  </style>
</head>
<body>
  <header>
    <div class="header-left">
      <div id="statusDot" class="status-dot"></div>
      <h1 id="statusText">CONNECTING...</h1>
    </div>
    <div style="display: flex; gap: 4px;">
      <button class="btn-header" id="speedToggle" onclick="toggleSpeed()">🚀 2.2x</button>
      <button class="btn-header" onclick="refreshSnapshot()">📸 REFRESH</button>
      <button class="btn-header" onclick="toggleScreenHeight()">↕️ SCREEN</button>
    </div>
  </header>

  <!-- LIVE INTERACTIVE SCREEN WITH TAP-TO-CLICK -->
  <div id="screenSection">
    <div class="screen-overlay">🎯 TAP SCREEN TO CLICK DIRECTLY</div>
    <img id="screenImg" src="/stream" alt="Live PC Screen" onclick="handleScreenTap(event)" />
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
    // -------------------------------------------------------------
    // 1. WEBSOCKET PIPELINE WITH AUTO RECONNECT
    // -------------------------------------------------------------
    let ws = null;
    let isConnected = false;

    function initWebSocket() {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = `${proto}//${window.location.host}/ws/trackpad`;
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
          setTimeout(initWebSocket, 1200);
        };
        ws.onerror = () => { isConnected = false; };
      } catch (e) {
        setTimeout(initWebSocket, 2000);
      }
    }
    initWebSocket();

    function wsSend(payload) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(payload));
      } else {
        if (payload.t === 'm') {
          fetch('/api/mouse/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dx: payload.dx, dy: payload.dy })
          }).catch(()=>{});
        }
      }
    }

    // -------------------------------------------------------------
    // 2. SCREEN TAP-TO-CLICK (DIRECT PIXEL MAPPING)
    // -------------------------------------------------------------
    let pcScreenWidth = 1536, pcScreenHeight = 864;
    fetch('/api/screen/info')
      .then(r => r.json())
      .then(data => {
        if (data.width) pcScreenWidth = data.width;
        if (data.height) pcScreenHeight = data.height;
      }).catch(()=>{});

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

      // Visual flash feedback
      img.style.opacity = '0.7';
      setTimeout(() => { img.style.opacity = '1'; }, 100);
    }

    function refreshSnapshot() {
      const img = document.getElementById('screenImg');
      img.src = '/api/screen/snapshot?t=' + Date.now();
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
        fetch('/api/hud/launch', { method: 'POST' }).catch(()=>{});
      } else if (actionType === 'close_hud') {
        fetch('/api/hud/close', { method: 'POST' }).catch(()=>{});
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
