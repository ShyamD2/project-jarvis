"""
Project J.A.R.V.I.S. Live Screen Stream & Mobile Touch Trackpad Server.
Provides:
1. Real-time MJPEG live screen stream (/stream)
2. Mobile touch trackpad HTML5 web interface (/remote)
3. REST endpoints for cursor movement, clicks, scrolling, and keyboard input
"""
from __future__ import annotations
import os
import sys
import io
import time
import socket
import threading
from typing import Optional, Dict, Any
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from PIL import ImageGrab

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger
from agents.computer.mouse_agent import mouse_agent

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


def generate_mjpeg_frames():
    """Generates continuous JPEG frames of the active display."""
    while True:
        try:
            # Capture full desktop
            img = ImageGrab.grab(all_screens=False)
            # Downscale slightly for smooth 15-20 FPS over Wi-Fi
            w, h = img.size
            ratio = 720 / max(w, 1)
            target_size = (720, int(h * ratio))
            img = img.resize(target_size)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=55)
            frame = buf.getvalue()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
            time.sleep(0.06)  # ~16 FPS
        except Exception as e:
            time.sleep(0.1)


@app.get("/stream")
def stream_screen():
    """Live MJPEG video stream of the Windows desktop."""
    return StreamingResponse(
        generate_mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.post("/api/mouse/move")
def move_mouse(req: MoveRequest):
    cx, cy = mouse_agent.get_cursor_position()
    nx = int(cx + req.dx)
    ny = int(cy + req.dy)
    mouse_agent.move_cursor(nx, ny, smooth=False)
    return {"status": "ok", "x": nx, "y": ny}


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
    from agents.computer.keyboard_agent import keyboard_agent
    res = keyboard_agent.type_text(req.text)
    return res


@app.post("/api/keyboard/key")
def press_key(req: KeyRequest):
    from agents.computer.keyboard_agent import keyboard_agent
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
  <title>J.A.R.V.I.S. Remote Trackpad</title>
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
      padding: 10px 16px;
      background: rgba(10, 20, 35, 0.95);
      border-bottom: 1px solid rgba(0, 240, 255, 0.3);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    header h1 { font-size: 14px; font-weight: 700; letter-spacing: 1px; }
    .stream-toggle {
      background: rgba(0, 240, 255, 0.15);
      border: 1px solid #00f0ff;
      color: #fff;
      padding: 4px 10px;
      border-radius: 4px;
      font-size: 11px;
      cursor: pointer;
    }
    #streamContainer {
      width: 100%;
      height: 180px;
      background: #000;
      display: flex;
      justify-content: center;
      align-items: center;
      border-bottom: 1px solid rgba(0, 240, 255, 0.2);
    }
    #liveStream {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }
    #trackpad {
      flex: 1;
      margin: 12px;
      background: radial-gradient(circle at center, #0f1c30 0%, #080f1a 100%);
      border: 2px dashed rgba(0, 240, 255, 0.4);
      border-radius: 12px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      color: rgba(0, 240, 255, 0.6);
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 1px;
      position: relative;
    }
    #trackpad.active {
      border-color: #00f0ff;
      background: radial-gradient(circle at center, #152744 0%, #0b1524 100%);
    }
    .controls {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      padding: 0 12px 8px 12px;
    }
    .btn {
      background: rgba(0, 240, 255, 0.08);
      border: 1px solid rgba(0, 240, 255, 0.3);
      color: #fff;
      padding: 12px 0;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
      text-align: center;
      cursor: pointer;
    }
    .btn:active { background: #00f0ff; color: #000; }
    .type-bar {
      display: flex;
      padding: 4px 12px 12px 12px;
      gap: 6px;
    }
    .type-input {
      flex: 1;
      background: #0d1829;
      border: 1px solid rgba(0, 240, 255, 0.3);
      color: #fff;
      padding: 10px 12px;
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
    <h1>🛸 J.A.R.V.I.S. TRACKPAD</h1>
    <button class="stream-toggle" onclick="toggleStream()">👁️ TOGGLE SCREEN</button>
  </header>

  <div id="streamContainer">
    <img id="liveStream" src="/stream" alt="Live PC Display">
  </div>

  <div id="trackpad">
    <span>🖱️ Drag Finger to Move Cursor</span>
    <span style="font-size:10px; margin-top:6px; opacity:0.7;">Tap = Left Click | 2-Finger Tap = Right Click</span>
  </div>

  <div class="controls">
    <button class="btn" onclick="sendClick('left')">🖱️ Left Click</button>
    <button class="btn" onclick="sendClick('double')">✌️ Double Click</button>
    <button class="btn" onclick="sendClick('right')">👆 Right Click</button>
    <button class="btn" onclick="sendScroll(3)">📜 Scroll Up</button>
    <button class="btn" onclick="sendKey('backspace')">🔙 Backspace</button>
    <button class="btn" onclick="sendScroll(-3)">📜 Scroll Down</button>
  </div>

  <div class="type-bar">
    <input type="text" id="typeInput" class="type-input" placeholder="Type text into active PC app..." onkeydown="if(event.key==='Enter') sendType()">
    <button class="type-send" onclick="sendType()">SEND</button>
  </div>

  <script>
    function toggleStream() {
      const c = document.getElementById('streamContainer');
      c.style.display = (c.style.display === 'none') ? 'flex' : 'none';
    }

    const pad = document.getElementById('trackpad');
    let lastX = 0, lastY = 0, isMoving = false;
    let touchStartTime = 0, touchStartX = 0, touchStartY = 0;
    const SENSITIVITY = 1.6;

    pad.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        isMoving = true;
        pad.classList.add('active');
        lastX = e.touches[0].clientX;
        lastY = e.touches[0].clientY;
        touchStartX = lastX;
        touchStartY = lastY;
        touchStartTime = Date.now();
      } else if (e.touches.length === 2) {
        // Two-finger tap detection for right click
        sendClick('right');
      }
    }, { passive: false });

    pad.addEventListener('touchmove', (e) => {
      if (!isMoving || e.touches.length !== 1) return;
      e.preventDefault();
      const curX = e.touches[0].clientX;
      const curY = e.touches[0].clientY;
      const dx = (curX - lastX) * SENSITIVITY;
      const dy = (curY - lastY) * SENSITIVITY;

      lastX = curX;
      lastY = curY;

      fetch('/api/mouse/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dx: dx, dy: dy })
      }).catch(()=>{});
    }, { passive: false });

    pad.addEventListener('touchend', (e) => {
      isMoving = false;
      pad.classList.remove('active');
      const duration = Date.now() - touchStartTime;
      const dist = Math.hypot(lastX - touchStartX, lastY - touchStartY);
      // Quick tap without movement triggers click
      if (duration < 220 && dist < 10) {
        sendClick('left');
      }
    });

    function sendClick(btn) {
      fetch('/api/mouse/click', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ button: btn })
      });
    }

    function sendScroll(delta) {
      fetch('/api/mouse/scroll', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ delta: delta })
      });
    }

    function sendType() {
      const input = document.getElementById('typeInput');
      const val = input.value;
      if (!val) return;
      fetch('/api/keyboard/type', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: val })
      }).then(() => { input.value = ''; });
    }

    function sendKey(k) {
      fetch('/api/keyboard/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: k })
      });
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
