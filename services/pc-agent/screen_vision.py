"""
Screen Vision & UI Understanding Agent for J.A.R.V.I.S.
Captures screen frames and analyzes UI elements using Multimodal Vision AI.
"""

from __future__ import annotations
import os
import sys
import time
from typing import Dict, Any, Optional
from PIL import Image
import io
import base64
from shared.sdk_python.jarvis_sdk.logger import get_logger

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../sensory")))
try:
    from screen_vision import _capture_desktop_image
except ImportError:
    from services.sensory.screen_vision import _capture_desktop_image

logger = get_logger("JarvisScreenVisionAgent")


class ScreenVisionAgent:
    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(__file__), "vision_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def capture_screenshot(self) -> Optional[str]:
        """Captures real full-screen screenshot and saves to cache directory. Returns None on failure."""
        screenshot_path = os.path.join(self.cache_dir, "screen_latest.png")
        img = _capture_desktop_image()
        if not img:
            logger.error("[ScreenVision] Screen capture failed; no display buffer available.")
            return None

        try:
            img.save(screenshot_path, "PNG")
            logger.info(f"[ScreenVision] Captured real screen snapshot ({img.width}x{img.height}): {screenshot_path}")
            return screenshot_path
        except Exception as e:
            logger.error(f"[ScreenVision] Failed to save screenshot: {e}")
            return None

    async def analyze_screen(self, question: str = "What is currently visible on the screen?") -> Dict[str, Any]:
        """
        Analyzes the captured screenshot using Multimodal Vision.
        Requires GEMINI_API_KEY and active desktop display.
        """
        screenshot_path = self.capture_screenshot()
        if not screenshot_path:
            return {
                "success": False,
                "error": "Desktop screen capture unavailable in current session",
                "image_path": None,
                "query": question,
                "analysis": "Screen capture failed."
            }

        logger.info(f"[ScreenVision] Analyzing screen with query: '{question}'")
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not gemini_key:
            return {
                "success": False,
                "error": "GEMINI_API_KEY unset. Multimodal analysis unavailable.",
                "image_path": screenshot_path,
                "query": question,
                "analysis": "Screen captured successfully, but vision provider is not configured."
            }

        try:
            import httpx
            with open(screenshot_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": question},
                        {"inlineData": {"mimeType": "image/png", "data": b64_data}}
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
                    "image_path": screenshot_path,
                    "query": question,
                    "analysis": analysis_text
                }
        except Exception as e:
            logger.error(f"[ScreenVision] Vision analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "image_path": screenshot_path,
                "query": question,
                "analysis": "Vision analysis request failed."
            }


screen_vision = ScreenVisionAgent()
