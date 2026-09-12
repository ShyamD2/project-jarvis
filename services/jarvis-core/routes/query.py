"""
Query & Voice Interaction Router for J.A.R.V.I.S. Core.
Directs natural language and voice queries into the Brain Agent Runtime and delivers voice audio.
"""

import os
import sys
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/brain"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/sensory"))

from services.brain.agent_runtime import runtime as brain_runtime
from services.sensory.voice_synthesizer import voice_synthesizer
from services.sensory.soundboard import soundboard
from services.memory.short_term import short_term_memory
from shared.sdk_python.jarvis_sdk.logger import get_logger
try:
    from websocket.manager import ws_manager
except ImportError:
    try:
        from services.jarvis_core.websocket.manager import ws_manager
    except ImportError:
        from services.jarvis_core.websocket.manager import ws_manager

logger = get_logger("JarvisQueryAPI")
router = APIRouter(prefix="/api/v1/query", tags=["Query"])


class QueryRequest(BaseModel):
    query: str = Field(..., description="User instruction or question")
    speak: bool = Field(default=True, description="Whether to generate voice audio")
    play_server_audio: bool = Field(default=False, description="Whether server plays audio locally")


@router.post("")
async def process_user_query(req: QueryRequest, background_tasks: BackgroundTasks):
    """
    Processes natural language instruction through the full J.A.R.V.I.S. Brain loop:
    UNDERSTAND -> PLAN -> AUTHORIZE -> EXECUTE -> VERIFY -> RESPOND
    """
    logger.info(f"Received query: '{req.query}'")
    short_term_memory.add_turn(role="user", content=req.query)

    # 1. Check for Authentic Movie Soundboard Clip Match
    matched_clip = soundboard.match_audio_clip(req.query)
    soundboard_url = None
    clip_name = None

    # 2. Execute Brain Turn
    result = await brain_runtime.execute_turn(req.query)

    response_text = result.get("response")
    if not response_text or not response_text.strip():
        response_text = "Instruction processed, sir."

    short_term_memory.add_turn(
        role="jarvis",
        content=response_text,
        intent=result.get("intent"),
        actions_taken=[a.get("tool") for a in result.get("actions_executed", [])]
    )

    # 3. Audio Delivery (Authentic Movie Clip or Neural TTS)
    audio_file = None
    if matched_clip:
        soundboard_url = matched_clip["url"]
        clip_name = matched_clip["clip_name"]
        audio_file = matched_clip["file_path"]
        if req.play_server_audio:
            soundboard.play_clip(clip_name)
    elif req.speak and response_text and response_text.strip():
        try:
            audio_file = await voice_synthesizer.speak(response_text, play_audio=req.play_server_audio)
        except Exception as e:
            logger.warning(f"Voice synthesis error: {e}")

    # 4. Broadcast to Live HUD Terminal
    background_tasks.add_task(
        ws_manager.broadcast,
        {
            "channel": "chat",
            "user": req.query,
            "jarvis": response_text,
            "intent": result.get("intent"),
            "verified": result.get("verified"),
            "soundboard_clip": clip_name
        }
    )

    return {
        "status": "success",
        "query": req.query,
        "response": response_text,
        "intent": result.get("intent"),
        "model": result.get("model"),
        "actions_executed": result.get("actions_executed", []),
        "verified": result.get("verified", True),
        "latency_ms": result.get("latency_ms", 0.0),
        "has_audio": audio_file is not None and os.path.exists(audio_file),
        "soundboard_url": soundboard_url,
        "clip_name": clip_name
    }


@router.get("/audio/latest")
async def get_latest_voice_audio():
    """Returns the latest synthesized voice audio file for browser playback"""
    audio_cache = os.path.join(PROJECT_ROOT, "services/sensory/audio_cache")
    mp3_file = os.path.join(audio_cache, "jarvis_latest.mp3")
    wav_file = os.path.join(audio_cache, "jarvis_latest.wav")

    if os.path.exists(mp3_file):
        return FileResponse(mp3_file, media_type="audio/mpeg")
    elif os.path.exists(wav_file):
        return FileResponse(wav_file, media_type="audio/wav")
    else:
        raise HTTPException(status_code=404, detail="No voice audio cached yet")


@router.get("/audio/soundboard/{clip_name}")
async def get_soundboard_audio(clip_name: str):
    """Returns authentic J.A.R.V.I.S. movie audio clip for browser playback"""
    clip_path = soundboard.clips.get(clip_name)
    if clip_path and os.path.exists(clip_path):
        return FileResponse(clip_path, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail=f"Soundboard clip '{clip_name}' not found")
