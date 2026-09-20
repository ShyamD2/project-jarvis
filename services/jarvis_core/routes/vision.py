"""
Computer Vision REST API Router for Project J.A.R.V.I.S.
Exposes screen capture thumbnail streaming and multimodal visual Q&A.
"""

import os
import sys
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/sensory"))

from screen_vision import screen_vision, LATEST_SCREEN_PATH

router = APIRouter(prefix="/api/v1/vision", tags=["Computer Vision"])


class AnalyzeScreenRequest(BaseModel):
    prompt: str = Field(default="What is on my screen?", description="User query about the screen")
    focus_app: Optional[str] = Field(default=None, description="Specific application window name")


@router.get("/screenshot")
async def get_latest_screenshot():
    """Captures and returns the latest desktop screenshot JPEG"""
    img_bytes = screen_vision.capture_screen_thumbnail()
    if img_bytes and os.path.exists(LATEST_SCREEN_PATH):
        return FileResponse(LATEST_SCREEN_PATH, media_type="image/jpeg")

    # If live display is locked/inaccessible, serve previous screen cache if present
    if os.path.exists(LATEST_SCREEN_PATH):
        return FileResponse(
            LATEST_SCREEN_PATH,
            media_type="image/jpeg",
            headers={"X-Screen-Cache": "hit"}
        )

    raise HTTPException(status_code=503, detail="Failed to capture desktop screenshot: display buffer unavailable")


@router.post("/analyze")
async def analyze_screen(req: AnalyzeScreenRequest):
    """Performs multimodal visual question answering over current desktop screen"""
    res = await screen_vision.analyze_screen_context(req.prompt, req.focus_app)
    return res
