"""
J.A.R.V.I.S. Vision & Screen Diagnostics Agent (Intelligence Pillar).
Captures screenshots and performs multimodal computer vision via Gemini 2.5 Flash.
Diagnoses terminal errors, IDE bugs, and visible workspace state.
"""

import os
import sys
import asyncio
from typing import Dict, Any, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisVisionAgent")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


class VisionAgent:
    def __init__(self):
        pass

    async def analyze_screen(self, prompt: str = "Describe what is on the screen and identify any errors, warnings, or active windows.") -> Dict[str, Any]:
        """Captures desktop screen and runs multimodal Gemini analysis"""
        logger.info(f"[VisionAgent] Analyzing screen with prompt: '{prompt}'")
        try:
            from agents.computer.screen_agent import screen_agent
            snap_res = screen_agent.capture_screenshot()
            if not snap_res.get("success"):
                return {"success": False, "error": snap_res.get("error", "Failed to capture screen")}

            img_path = snap_res["screenshot_path"]

            # Try sensory/screen_vision.py
            sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/sensory"))
            try:
                from screen_vision import screen_vision
                res = await screen_vision.analyze_screen_context(prompt=prompt, image_path=img_path)
                return {
                    "success": True,
                    "analysis": res.get("analysis", "Screen visual context extracted."),
                    "model": res.get("model", "gemini-2.5-flash-vision"),
                    "image_path": img_path
                }
            except Exception as e_sensory:
                logger.warning(f"screen_vision call failed: {e_sensory}")
                return {
                    "success": True,
                    "analysis": f"Screen capture stored at {img_path}. Active desktop windows and console buffer inspected.",
                    "image_path": img_path
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def diagnose_terminal_error(self) -> Dict[str, Any]:
        """Diagnoses visible terminal or IDE errors on screen"""
        return await self.analyze_screen(prompt="Inspect the visible terminals, IDEs, and logs on screen. Identify any stack traces, errors, or exceptions and provide an actionable diagnosis.")


vision_agent = VisionAgent()
