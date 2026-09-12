"""
Multimodal Computer Vision Engine for Project J.A.R.V.I.S.
Enables "Look at This" capability:
- Captures desktop screenshot or specific app window
- Downscales & compresses to lightweight base64 thumbnail (<200ms)
- Performs visual QA, OCR text extraction, and UI layout reasoning
"""

from __future__ import annotations
import os
import sys
import time
import base64
import io
from typing import Dict, Any, Optional
from PIL import Image, ImageGrab

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CACHE_DIR = os.path.join(os.path.dirname(__file__), "audio_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
LATEST_SCREEN_PATH = os.path.join(CACHE_DIR, "latest_screen.jpg")

from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.config import config

try:
    from services.observability import obs_metrics, obs_tracer
except ImportError:
    obs_metrics = None
    obs_tracer = None

logger = get_logger("JarvisScreenVision")


def _capture_desktop_image() -> Optional[Image.Image]:
    """Captures real screen using native Win32 GDI or Pillow ImageGrab without simulation."""
    if sys.platform == "win32":
        try:
            import ctypes
            import struct
            u32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            # Explicit 64-bit type signatures for Windows GDI
            u32.GetDC.restype = ctypes.c_void_p
            u32.GetDC.argtypes = [ctypes.c_void_p]
            u32.ReleaseDC.restype = ctypes.c_int
            u32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

            gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
            gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
            gdi32.DeleteDC.restype = ctypes.c_bool
            gdi32.DeleteDC.argtypes = [ctypes.c_void_p]

            gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
            gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
            gdi32.DeleteObject.restype = ctypes.c_bool
            gdi32.DeleteObject.argtypes = [ctypes.c_void_p]

            gdi32.SelectObject.restype = ctypes.c_void_p
            gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

            gdi32.BitBlt.restype = ctypes.c_bool
            gdi32.BitBlt.argtypes = [
                ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint32
            ]

            gdi32.GetDIBits.restype = ctypes.c_int
            gdi32.GetDIBits.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint
            ]

            w = u32.GetSystemMetrics(0)
            h = u32.GetSystemMetrics(1)
            if w <= 0 or h <= 0:
                logger.error(f"[ScreenVision] Invalid screen metrics: {w}x{h}")
                return None

            hdc = u32.GetDC(None)
            if not hdc:
                logger.error("[ScreenVision] Failed to acquire desktop DC")
                return None

            memdc = gdi32.CreateCompatibleDC(hdc)
            if not memdc:
                u32.ReleaseDC(None, hdc)
                logger.error("[ScreenVision] Failed to create compatible memory DC")
                return None

            hbmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
            if not hbmp:
                gdi32.DeleteDC(memdc)
                u32.ReleaseDC(None, hdc)
                logger.error("[ScreenVision] Failed to create compatible bitmap")
                return None

            try:
                gdi32.SelectObject(memdc, hbmp)
                res = gdi32.BitBlt(memdc, 0, 0, w, h, hdc, 0, 0, 0x00CC0020)
                if not res:
                    logger.error(f"[ScreenVision] BitBlt failed (error {ctypes.GetLastError()})")
                    return None

                bi = bytearray(40)
                struct.pack_into('<IiiHHIIiiII', bi, 0, 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
                buf = bytearray(w * h * 4)
                lines = gdi32.GetDIBits(hdc, hbmp, 0, h, (ctypes.c_char * len(buf)).from_buffer(buf), (ctypes.c_char * 40).from_buffer(bi), 0)
                if lines <= 0:
                    logger.error("[ScreenVision] GetDIBits failed to extract scanlines")
                    return None

                return Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1).convert('RGB')
            finally:
                gdi32.DeleteObject(hbmp)
                gdi32.DeleteDC(memdc)
                u32.ReleaseDC(None, hdc)
        except Exception as e:
            logger.error(f"[ScreenVision] Win32 GDI capture error: {e}")
            return None
    else:
        try:
            return ImageGrab.grab()
        except Exception as e:
            logger.error(f"[ScreenVision] ImageGrab capture error: {e}")
            return None


class ScreenVision:
    def __init__(self):
        self.last_capture_time: float = 0.0
        self.last_thumbnail_b64: Optional[str] = None

    def capture_screen_thumbnail(self, max_dim: int = 1024, quality: int = 70) -> Optional[bytes]:
        """Captures real full screen, resizes, and writes JPEG to cache. Returns None on failure."""
        start = time.time()
        img = _capture_desktop_image()
        if not img:
            logger.error("[ScreenVision] Desktop screen capture returned no image buffer.")
            return None

        try:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=quality)
            jpeg_bytes = buf.getvalue()

            with open(LATEST_SCREEN_PATH, "wb") as f:
                f.write(jpeg_bytes)

            self.last_capture_time = time.time()
            self.last_thumbnail_b64 = base64.b64encode(jpeg_bytes).decode("utf-8")

            if obs_metrics:
                obs_metrics.record_latency("vision.screen_capture", (time.time() - start) * 1000)

            return jpeg_bytes
        except Exception as e:
            logger.error(f"Failed to process screen frame: {e}")
            return None

    async def analyze_screen_context(self, prompt: str = "Analyze the contents of this screen", focus_app: Optional[str] = None) -> Dict[str, Any]:
        """
        Multimodal visual analysis of current screen.
        Requires active display session and vision model (Gemini Vision if key provided).
        """
        jpeg_bytes = self.capture_screen_thumbnail()
        if not jpeg_bytes:
            return {
                "success": False,
                "error": "Failed to capture desktop screen (display buffer or desktop session unavailable).",
                "analysis": "Screen capture was unavailable in this session, sir."
            }

        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        if gemini_key:
            try:
                import httpx
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
                b64_data = base64.b64encode(jpeg_bytes).decode("utf-8")
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": f"You are J.A.R.V.I.S. Tony Stark has asked you to look at his screen: '{prompt}'. Provide a concise, highly insightful breakdown of what is visible."},
                            {"inlineData": {"mimeType": "image/jpeg", "data": b64_data}}
                        ]
                    }]
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    analysis_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return {
                        "success": True,
                        "analysis": analysis_text,
                        "model": "gemini-2.5-flash-vision",
                        "has_thumbnail": True
                    }
            except Exception as e:
                logger.error(f"Gemini Vision API call failed: {e}")
                return {
                    "success": False,
                    "error": f"Gemini Vision API call failed: {e}",
                    "analysis": "Screen captured successfully, but vision inference failed."
                }

        # Explicit response when no vision model is configured
        return {
            "success": False,
            "error": "GEMINI_API_KEY unset. Multimodal analysis unavailable.",
            "analysis": "Screen captured successfully, but no multimodal vision provider is configured to inspect it.",
            "has_thumbnail": True
        }


screen_vision = ScreenVision()
