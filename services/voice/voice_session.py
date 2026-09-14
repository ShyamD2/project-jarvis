"""
Voice Session Coordinator & State Machine for Project J.A.R.V.I.S.
Maintains the 7 live voice states:
IDLE <-> LISTENING -> THINKING -> EXECUTING -> SPEAKING -> SUCCESS / ERROR -> IDLE
Broadcasts state changes and partial STT live to HUD via WebSocket.
"""

from __future__ import annotations
import asyncio
import enum
import time
from typing import Optional, Dict, Any, List, Callable
from shared.sdk_python.jarvis_sdk.logger import get_logger
from services.voice.wake_word import wake_word_detector
from services.voice.vad import vad_detector
from services.voice.stt_engine import stt_engine
from services.voice.tts_engine import tts_engine

logger = get_logger("JarvisVoiceSession")

try:
    from services.jarvis_core.websocket.manager import ws_manager
except ImportError:
    try:
        from websocket.manager import ws_manager
    except ImportError:
        ws_manager = None


class VoiceState(str, enum.Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    EXECUTING = "EXECUTING"
    SPEAKING = "SPEAKING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class VoiceSession:
    def __init__(self):
        self.state: VoiceState = VoiceState.IDLE
        self.active_transcript: str = ""
        self.partial_transcript: str = ""
        self.last_state_change: float = time.time()
        self.last_interaction_time: float = time.time()
        self.state_listeners: List[Callable[[VoiceState, Dict[str, Any]], None]] = []

        # Hook VAD barge-in directly to TTS interrupt
        vad_detector.register_barge_in_callback(self.handle_barge_in)
        tts_engine.register_on_done(self._on_speech_finished)

    def register_state_listener(self, cb: Callable[[VoiceState, Dict[str, Any]], None]):
        """Registers a callback function whenever the voice state changes."""
        self.state_listeners.append(cb)

    def transition_to(self, new_state: VoiceState, details: Optional[Dict[str, Any]] = None):
        """
        Transitions the voice session into a new state, logging and broadcasting to HUD.
        """
        old_state = self.state
        self.state = new_state
        self.last_state_change = time.time()
        payload = {
            "channel": "voice_state",
            "previous_state": old_state.value,
            "current_state": new_state.value,
            "timestamp": self.last_state_change,
            "details": details or {}
        }
        logger.info(f"🎙 [Voice Session State] {old_state.value} ➔ {new_state.value}")

        # Broadcast to WebSocket HUD
        if ws_manager:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(ws_manager.broadcast(payload))
                else:
                    loop.run_until_complete(ws_manager.broadcast(payload))
            except Exception as e:
                logger.debug(f"[VoiceSession] WebSocket broadcast error: {e}")

        # Notify local listeners
        for listener in self.state_listeners:
            try:
                listener(new_state, details or {})
            except Exception as e:
                logger.warning(f"[VoiceSession] Listener error: {e}")

    def handle_barge_in(self):
        """
        Executes on vocal barge-in (<5ms).
        Instantly halts TTS speech and moves state to LISTENING.
        """
        logger.info("⚡ [Voice Session] Vocal barge-in received. Cutting audio output immediately.")
        tts_engine.interrupt()
        if self.state == VoiceState.SPEAKING:
            self.transition_to(VoiceState.LISTENING, {"reason": "barge_in"})

    def _on_speech_finished(self):
        """Called automatically when TTS audio completes."""
        if self.state == VoiceState.SPEAKING:
            # Transition to IDLE, keeping follow-up conversational window active
            wake_word_detector.start_followup_window()
            self.transition_to(VoiceState.IDLE, {"followup_active": True})

    async def update_partial_transcript(self, partial_text: str):
        """Broadcasts streaming/partial STT token updates to the HUD."""
        self.partial_transcript = partial_text
        if ws_manager and partial_text:
            try:
                await ws_manager.broadcast({
                    "channel": "partial_stt",
                    "text": partial_text,
                    "timestamp": time.time()
                })
            except Exception as e:
                logger.debug(f"[VoiceSession] Partial STT broadcast error: {e}")

    def reset(self):
        """Resets the voice session to IDLE."""
        tts_engine.interrupt()
        vad_detector.reset()
        wake_word_detector.cancel_followup_window()
        self.active_transcript = ""
        self.partial_transcript = ""
        self.transition_to(VoiceState.IDLE)


voice_session = VoiceSession()
