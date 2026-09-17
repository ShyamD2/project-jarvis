"""
Project J.A.R.V.I.S. Live Screen Stream & Mobile Touch Trackpad Server.
High-speed, low-latency mobile trackpad with:
1. Ultra-fast WebSocket streaming (/ws/trackpad) for sub-millisecond mouse responsiveness
2. Win32 relative hardware cursor motion (mouse_event MOUSEEVENTF_MOVE)
3. Async non-blocking MJPEG desktop stream (/stream) & single-frame snapshot (/api/screen/snapshot)
4. Mobile-optimized touch surface with requestAnimationFrame batching, two-finger right click, and scroll rail
5. Fallback REST endpoints for all actions
"""
from __future__ import annotations
import os
import sys
import io
import time
import socket
import asyncio
import threading
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

logger = get_logger("JarvisTrackpadServer")

app = FastAPI(title="JARVIS Remote Trackpad & Stream")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_local_ip() -> str:
    """Returns the local LAN/Wi-Fi IPv4 address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class MoveRequest(BaseModel):
    dx: float
    dy: float


class ClickRequest(BaseModel):
    button: str = "left"


class ScrollRequest(BaseModel):
    delta: int = -2


class TypeRequest(BaseModel):
    text: str


class KeyRequest(BaseModel):
    key: str


async def generate_mjpeg_frames():
    """Asynchronously streams JPEG frames of the desktop without blocking event loop."""
    loop = asyncio.get_event_loop()
    while True:
        try:
            # Capture desktop in thread pool so it never blocks WebSocket or HTTP traffic
            img = await loop.run_in_executor(None, lambda: ImageGrab.grab(all_screens=False))
            w, h = img.size
            ratio = 640 / max(w, 1)
            target_size = (640, int(h * ratio))
            img = img.resize(target_size)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=45)
            frame = buf.getvalue()

            header = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
            yield header + frame + b"\r\n"
            await asyncio.sleep(0.08)  # ~12 FPS
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(0.2)


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


@app.websocket("/ws/trackpad")
async def trackpad_websocket(websocket: WebSocket):
    """
    Sub-millisecond full-duplex WebSocket connection for mobile touch trackpad.
    Eliminates all HTTP request queuing and connection limits.
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
                dx = msg.get("dx", 0)
                dy = msg.get("dy", 0)
                mouse_agent.move_relative(dx, dy)
            elif t == "c":
                # Click
                b = msg.get("b", "left")
                mouse_agent.click(button=b)
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
            elif t == "type":
                # Type text
                txt = msg.get("text", "")
                if txt:
                    keyboard_agent.type_text(txt)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"[TrackpadWS] Notice: {e}")


@app.post("/api/mouse/move")
def move_mouse(req: MoveRequest):
    res = mouse_agent.move_relative(req.dx, req.dy)
    return res


@app.post("/api/mouse/click")
def click_mouse(req: ClickRequest):
    btn = req.button.lower()
    res = mouse_agent.click(button=btn)
    return res


@app.post("/api/mouse/scroll")
def scroll_mouse(req: ScrollRequest):
    direction = "down" if req.delta < 0 else "up"
    res = mouse_agent.scroll(clicks=abs(req.delta), direction=direction)
    return res


@app.post("/api/keyboard/type")
def type_text(req: TypeRequest):
    res = keyboard_agent.type_text(req.text)
    return res


@app.post("/api/keyboard/key")
def press_key(req: KeyRequest):
    res = keyboard_agent.press_key(req.key)
    return res


@app.get("/remote", response_class=HTMLResponse)
def remote_trackpad_page():
    """High-speed mobile touch trackpad and live stream interface."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>J.A.R.V.I.S. Touch Trackpad</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
    body {
      background: #060913;
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
      padding: 8px 14px;
      background: rgba(10, 20, 35, 0.95);
      border-bottom: 1px solid rgba(0, 240, 255, 0.3);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
    }
    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .status-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #ffaa00;
      box-shadow: 0 0 8px currentColor;
      transition: background 0.3s;
    }
    header h1 { font-size: 13px; font-weight: 700; letter-spacing: 0.5px; }
    .btn-header {
      background: rgba(0, 240, 255, 0.15);
      border: 1px solid #00f0ff;
      color: #fff;
      padding: 5px 10px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
    }
    #streamContainer {
      display: none;
      width: 100%;
      height: 160px;
      background: #000;
      justify-content: center;
      align-items: center;
      border-bottom: 1px solid rgba(0, 240, 255, 0.3);
      position: relative;
      flex-shrink: 0;
    }
    #liveStream {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }
    .trackpad-wrapper {
      flex: 1;
      display: flex;
      margin: 8px 10px;
      gap: 8px;
      position: relative;
      overflow: hidden;
    }
    #trackpad {
      flex: 1;
      background: radial-gradient(circle at center, #0f1f38 0%, #08111e 100%);
      border: 2px solid rgba(0, 240, 255, 0.4);
      border-radius: 12px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      color: rgba(0, 240, 255, 0.7);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 1px;
      position: relative;
      transition: border-color 0.15s, background 0.15s;
    }
    #trackpad.active {
      border-color: #00f0ff;
      background: radial-gradient(circle at center, #1b355e 0%, #0d1a2d 100%);
      box-shadow: inset 0 0 20px rgba(0, 240, 255, 0.3);
    }
    .scroll-rail {
      width: 44px;
      background: #0a1424;
      border: 1px solid rgba(0, 240, 255, 0.3);
      border-radius: 12px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      align-items: center;
      padding: 10px 0;
      color: rgba(0, 240, 255, 0.6);
      font-size: 11px;
    }
    .scroll-rail.active {
      border-color: #00f0ff;
      background: #11223b;
      color: #00f0ff;
    }
    .controls {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6px;
      padding: 0 10px 6px 10px;
      flex-shrink: 0;
    }
    .btn {
      background: rgba(0, 240, 255, 0.08);
      border: 1px solid rgba(0, 240, 255, 0.3);
      color: #fff;
      padding: 10px 0;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
      text-align: center;
      cursor: pointer;
    }
    .btn:active { background: #00f0ff; color: #000; }
    .btn.primary {
      background: rgba(0, 240, 255, 0.25);
      border-color: #00f0ff;
    }
    .type-bar {
      display: flex;
      padding: 2px 10px 10px 10px;
      gap: 6px;
      flex-shrink: 0;
    }
    .type-input {
      flex: 1;
      background: #0d1829;
      border: 1px solid rgba(0, 240, 255, 0.3);
      color: #fff;
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 13px;
      outline: none;
    }
    .type-send {
      background: #00f0ff;
      color: #000;
      border: none;
      padding: 0 16px;
      border-radius: 6px;
      font-weight: 700;
      font-size: 12px;
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
    <div style="display: flex; gap: 6px;">
      <button class="btn-header" id="speedToggle" onclick="toggleSpeed()">🚀 FAST</button>
      <button class="btn-header" onclick="toggleStream()">👁️ SCREEN</button>
    </div>
  </header>

  <div id="streamContainer">
    <img id="liveStream" alt="Live PC Display">
  </div>

  <div class="trackpad-wrapper">
    <div id="trackpad">
      <span>🖱️ Drag to Move Mouse</span>
      <span style="font-size:10px; margin-top:6px; opacity:0.65;">Tap = Left Click | 2-Finger = Right Click</span>
    </div>
    <div id="scrollRail" class="scroll-rail">
      <span>▲</span>
      <span style="writing-mode: vertical-lr; letter-spacing: 2px;">SCROLL</span>
      <span>▼</span>
    </div>
  </div>

  <div class="controls">
    <button class="btn primary" onclick="sendClick('left')">🖱️ Left Click</button>
    <button class="btn" onclick="sendClick('double')">✌️ Double Click</button>
    <button class="btn primary" onclick="sendClick('right')">👆 Right Click</button>
    <button class="btn" onclick="sendScroll(3)">🔼 Scroll Up</button>
    <button class="btn" onclick="sendKey('backspace')">🔙 Backspace</button>
    <button class="btn" onclick="sendScroll(-3)">🔽 Scroll Down</button>
  </div>

  <div class="type-bar">
    <input type="text" id="typeInput" class="type-input" placeholder="Type into active PC app..." onkeydown="if(event.key==='Enter') sendType()">
    <button class="type-send" onclick="sendType()">SEND</button>
  </div>

  <script>
    // -------------------------------------------------------------
    // 1. HIGH-SPEED WEBSOCKET CLIENT WITH AUTOMATIC RECONNECT
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
          document.getElementById('statusText').innerText = 'J.A.R.V.I.S. ACTIVE';
        };
        ws.onclose = () => {
          isConnected = false;
          document.getElementById('statusDot').style.background = '#ffaa00';
          document.getElementById('statusText').innerText = 'RECONNECTING...';
          setTimeout(initWebSocket, 1200);
        };
        ws.onerror = () => {
          isConnected = false;
        };
      } catch (e) {
        setTimeout(initWebSocket, 2000);
      }
    }
    initWebSocket();

    function wsSend(payload) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(payload));
      } else {
        // Fallback HTTP
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
    // 2. SPEED & STREAM TOGGLES
    // -------------------------------------------------------------
    let sensitivity = 1.8;
    function toggleSpeed() {
      const btn = document.getElementById('speedToggle');
      if (sensitivity === 1.8) {
        sensitivity = 2.8;
        btn.innerText = '⚡ TURBO';
        btn.style.color = '#ff0055';
        btn.style.borderColor = '#ff0055';
      } else {
        sensitivity = 1.8;
        btn.innerText = '🚀 FAST';
        btn.style.color = '#fff';
        btn.style.borderColor = '#00f0ff';
      }
    }

    let streamActive = false;
    function toggleStream() {
      const c = document.getElementById('streamContainer');
      const img = document.getElementById('liveStream');
      streamActive = !streamActive;
      if (streamActive) {
        c.style.display = 'flex';
        img.src = '/stream?t=' + Date.now();
      } else {
        c.style.display = 'none';
        img.src = '';
      }
    }

    // -------------------------------------------------------------
    // 3. FLUID TOUCH TRACKPAD (requestAnimationFrame BATCHING)
    // -------------------------------------------------------------
    const pad = document.getElementById('trackpad');
    let lastTouchX = 0, lastTouchY = 0;
    let isTracking = false;
    let touchStartTime = 0, startX = 0, startY = 0;
    let pendingDx = 0, pendingDy = 0;
    let rafId = null;

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
        pad.classList.add('active');
        lastTouchX = e.touches[0].clientX;
        lastTouchY = e.touches[0].clientY;
        startX = lastTouchX;
        startY = lastTouchY;
        touchStartTime = Date.now();
      } else if (e.touches.length === 2) {
        // Two-finger tap for right click
        isTracking = false;
        pad.classList.remove('active');
        sendClick('right');
      }
    }, { passive: false });

    pad.addEventListener('touchmove', (e) => {
      if (!isTracking || e.touches.length !== 1) return;
      e.preventDefault();

      const curX = e.touches[0].clientX;
      const curY = e.touches[0].clientY;
      const deltaX = (curX - lastTouchX) * sensitivity;
      const deltaY = (curY - lastTouchY) * sensitivity;

      lastTouchX = curX;
      lastTouchY = curY;

      pendingDx += deltaX;
      pendingDy += deltaY;

      if (!rafId) {
        rafId = requestAnimationFrame(flushMotion);
      }
    }, { passive: false });

    pad.addEventListener('touchend', (e) => {
      if (!isTracking) return;
      isTracking = false;
      pad.classList.remove('active');
      flushMotion();

      const duration = Date.now() - touchStartTime;
      const dist = Math.hypot(lastTouchX - startX, lastTouchY - startY);
      // Quick tap without significant drag triggers left click
      if (duration < 240 && dist < 12) {
        sendClick('left');
      }
    }, { passive: false });

    // -------------------------------------------------------------
    // 4. TOUCH SCROLL RAIL (SLIDE ON THE RIGHT EDGE)
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
      if (Math.abs(dy) > 12) {
        const delta = dy < 0 ? 3 : -3;
        sendScroll(delta);
        lastRailY = curY;
      }
    }, { passive: false });

    rail.addEventListener('touchend', () => {
      isRailActive = false;
      rail.classList.remove('active');
    }, { passive: false });

    // -------------------------------------------------------------
    // 5. ACTION DISPATCHERS
    // -------------------------------------------------------------
    function sendClick(btn) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ t: 'c', b: btn }));
      } else {
        fetch('/api/mouse/click', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ button: btn })
        }).catch(()=>{});
      }
    }

    function sendScroll(delta) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ t: 's', d: delta }));
      } else {
        fetch('/api/mouse/scroll', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ delta: delta })
        }).catch(()=>{});
      }
    }

    function sendType() {
      const input = document.getElementById('typeInput');
      const val = input.value;
      if (!val) return;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ t: 'type', text: val }));
      } else {
        fetch('/api/keyboard/type', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: val })
        }).catch(()=>{});
      }
      input.value = '';
    }

    function sendKey(k) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ t: 'k', k: k }));
      } else {
        fetch('/api/keyboard/key', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key: k })
        }).catch(()=>{});
      }
    }
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


_server_thread: Optional[threading.Thread] = None


def start_trackpad_server(host: str = "0.0.0.0", port: int = 8085):
    """Starts the remote trackpad and live stream server in a background daemon thread."""
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        return

    def run_uvicorn():
        logger.info(f"⚡ [TrackpadServer] Live Screen & Mobile Touchpad running at http://{get_local_ip()}:{port}/remote")
        uvicorn.run(app, host=host, port=port, log_level="warning")

    _server_thread = threading.Thread(target=run_uvicorn, daemon=True)
    _server_thread.start()


if __name__ == "__main__":
    start_trackpad_server()
    print(f"Trackpad Server online at: http://{get_local_ip()}:8085/remote")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
