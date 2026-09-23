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
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/voice"))

from services.brain.agent_runtime import runtime as brain_runtime
from services.brain.conversation_engine import conversation_engine
from services.voice.voice_session import voice_session, VoiceState
from services.voice.tts_engine import tts_engine
from services.sensory.voice_synthesizer import voice_synthesizer
from services.sensory.soundboard import soundboard
from services.voice.interrupt_service import interrupt_service
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
    play_server_audio: bool = Field(default=True, description="Whether server plays audio locally")


@router.post("")
async def process_user_query(req: QueryRequest, background_tasks: BackgroundTasks):
    """
    Processes natural language instruction through the real-time Conversational Brain loop:
    UNDERSTAND -> CONTEXT RESOLVE -> PLAN -> AUTHORIZE -> EXECUTE -> VERIFY -> RESPOND
    """
    logger.info(f"Received query: '{req.query}'")
    short_term_memory.add_turn(role="user", content=req.query)

    # Transition to THINKING state
    voice_session.transition_to(VoiceState.THINKING, {"query": req.query})

    # 1. Check for Authentic Movie Soundboard Clip Match
    matched_clip = soundboard.match_audio_clip(req.query)
    soundboard_url = None
    clip_name = None

    # 2. Execute Conversational Brain Turn
    result = await conversation_engine.process_turn(req.query)

    actions_executed = result.get("actions_executed", [])
    if actions_executed:
        voice_session.transition_to(VoiceState.EXECUTING, {"actions": [a.get("tool") for a in actions_executed]})

    response_text = result.get("response")
    if not response_text or not response_text.strip():
        response_text = "Instruction processed, sir."

    short_term_memory.add_turn(
        role="jarvis",
        content=response_text,
        intent=result.get("intent"),
        actions_taken=[a.get("tool") for a in actions_executed]
    )

    # 3. Audio Delivery (Authentic Movie Clip or British Neural TTS)
    audio_file = None
    audio_url = None
    if matched_clip:
        soundboard_url = matched_clip["url"]
        clip_name = matched_clip["clip_name"]
        audio_file = matched_clip["file_path"]
        audio_url = soundboard_url
        voice_session.transition_to(VoiceState.SPEAKING, {"clip": clip_name})
        if req.play_server_audio:
            soundboard.play_clip(clip_name)
    elif req.speak and response_text and response_text.strip():
        try:
            import asyncio
            import base64
            voice_session.transition_to(VoiceState.SPEAKING, {"text_preview": response_text[:40]})

            async def _stream_callback(idx: int, clause: str, chunk_bytes: bytes, is_last: bool):
                try:
                    b64_audio = base64.b64encode(chunk_bytes).decode("utf-8")
                    await ws_manager.broadcast_audio_chunk(
                        audio_b64=b64_audio,
                        chunk_idx=idx,
                        is_final=is_last,
                        text_segment=clause
                    )
                except Exception as e_stream:
                    logger.debug(f"[QueryAPI] Stream chunk broadcast notice: {e_stream}")

            audio_file = await tts_engine.speak_stream(
                response_text,
                on_chunk=_stream_callback,
                play_audio=req.play_server_audio
            )
            # Fallback to voice_synthesizer if tts_engine produced no audio
            if not audio_file:
                audio_file = await voice_synthesizer.speak(response_text, play_audio=req.play_server_audio)

            if audio_file and os.path.exists(audio_file):
                voice_synthesizer.latest_audio_path = audio_file
                audio_filename = os.path.basename(audio_file)
                audio_url = f"/api/v1/query/audio/file/{audio_filename}"
        except Exception as e:
            logger.warning(f"Voice synthesis error: {e}")

    # If not speaking audio, transition to SUCCESS
    if not req.speak and not matched_clip:
        voice_session.transition_to(VoiceState.SUCCESS)

    # 4. Broadcast to Live HUD Terminal
    background_tasks.add_task(
        ws_manager.broadcast,
        {
            "channel": "chat",
            "user": req.query,
            "jarvis": response_text,
            "intent": result.get("intent"),
            "verified": result.get("verified"),
            "soundboard_clip": clip_name,
            "audio_url": audio_url
        }
    )

    return {
        "status": "success",
        "query": req.query,
        "response": response_text,
        "intent": result.get("intent"),
        "model": result.get("model"),
        "actions_executed": actions_executed,
        "verified": result.get("verified", True),
        "latency_ms": result.get("latency_ms", 0.0),
        "has_audio": audio_file is not None and os.path.exists(audio_file),
        "audio_url": audio_url,
        "soundboard_url": soundboard_url,
        "clip_name": clip_name
    }


@router.get("/audio/file/{filename}")
async def get_audio_file_by_name(filename: str):
    """Serves a specific synthesized voice audio file by name for immediate web playback."""
    safe_name = os.path.basename(filename)
    audio_cache = os.path.join(PROJECT_ROOT, "services/sensory/audio_cache")
    file_path = os.path.join(audio_cache, safe_name)
    if os.path.exists(file_path):
        media_type = "audio/mpeg" if safe_name.endswith(".mp3") else "audio/wav"
        return FileResponse(
            file_path,
            media_type=media_type,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    raise HTTPException(status_code=404, detail="Audio file not found")


@router.get("/audio/latest")
async def get_latest_voice_audio():
    """Returns the latest synthesized voice audio file for browser playback"""
    # 1. Check tts_engine current audio file
    current_tts = getattr(tts_engine, "_current_audio_file", None)
    if current_tts and os.path.exists(current_tts):
        return FileResponse(current_tts, media_type="audio/mpeg", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    # 2. Check voice_synthesizer latest audio path
    latest = getattr(voice_synthesizer, "latest_audio_path", None)
    if latest and os.path.exists(latest):
        return FileResponse(latest, media_type="audio/mpeg", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    # 3. Scan audio cache for newest generated file
    audio_cache = os.path.join(PROJECT_ROOT, "services/sensory/audio_cache")
    if os.path.exists(audio_cache):
        candidates = [
            os.path.join(audio_cache, f)
            for f in os.listdir(audio_cache)
            if (f.startswith("jarvis_tts_") or f.startswith("jarvis_")) and f.endswith(".mp3") and f != "jarvis_latest.mp3"
        ]
        if candidates:
            newest = max(candidates, key=os.path.getmtime)
            return FileResponse(newest, media_type="audio/mpeg", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    mp3_file = os.path.join(audio_cache, "jarvis_latest.mp3")
    wav_file = os.path.join(audio_cache, "jarvis_latest.wav")

    if os.path.exists(mp3_file):
        return FileResponse(mp3_file, media_type="audio/mpeg", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    elif os.path.exists(wav_file):
        return FileResponse(wav_file, media_type="audio/wav", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    else:
        raise HTTPException(status_code=404, detail="No voice audio cached yet")


@router.get("/audio/soundboard/{clip_name}")
async def get_soundboard_audio(clip_name: str):
    """Returns authentic J.A.R.V.I.S. movie audio clip for browser playback"""
    clip_path = soundboard.clips.get(clip_name)
    if clip_path and os.path.exists(clip_path):
        return FileResponse(clip_path, media_type="audio/mpeg", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    raise HTTPException(status_code=404, detail=f"Soundboard clip '{clip_name}' not found")


class SwitchEngineRequest(BaseModel):
    engine: str = Field(..., description="openrouter, groq, or gemini")


@router.post("/engine")
async def switch_ai_engine(req: SwitchEngineRequest):
    """Switches active primary AI engine between OpenRouter, Groq, and Gemini"""
    from services.brain.providers.ai_manager import ai_manager
    ai_manager.set_primary_provider(req.engine.lower())
    return {"status": "success", "primary_engine": ai_manager.preferred_provider}


@router.get("/engine")
async def get_ai_engine():
    """Returns current active AI engine and provider health"""
    from services.brain.providers.ai_manager import ai_manager
    return ai_manager.get_key_status()


@router.post("/interrupt")
async def interrupt_speech():
    """
    Immediate Barge-In Interrupt endpoint.
    Halts all active audio playback, TTS synthesis, recitation loops, and soundboard clips.
    """
    try:
        res = interrupt_service.interrupt(source="rest_api", reason="user_barge_in_endpoint")
        logger.info("⚡ [QueryAPI] Barge-in interrupt triggered: all vocal playback halted.")
        return {"status": "success", "interrupted": True, "message": "Speech recitation halted immediately."}
    except Exception as e:
        logger.warning(f"Error executing vocal interrupt: {e}")
        return {"status": "error", "message": str(e)}
