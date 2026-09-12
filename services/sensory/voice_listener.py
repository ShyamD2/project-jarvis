"""
Voice Listener & Wake-Word Engine for J.A.R.V.I.S.
Detects wake words ('Jarvis', 'Hey Jarvis') and transcribes natural speech to text.
Dispatches transcripts to the Real-Time Event Fabric.
"""

from __future__ import annotations
import re
from typing import Callable, Optional
from shared.schemas.event_envelope import JarvisEvent
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisVoiceListener")


class VoiceListener:
    def __init__(self, wake_words: Optional[list[str]] = None):
        self.wake_words = wake_words or ["jarvis", "hey jarvis"]
        self.is_listening = False
        self.on_transcript_received: Optional[Callable[[str], None]] = None

    def process_transcript(self, raw_text: str) -> Optional[JarvisEvent]:
        """
        Checks for wake-word activation and emits sensory.voice_transcript event.
        """
        text_clean = raw_text.strip()
        t_lower = text_clean.lower()

        # Check if wake-word is present
        wake_detected = any(re.search(rf"\b{re.escape(w)}\b", t_lower) for w in self.wake_words)

        if wake_detected:
            # Strip wake word for clean instruction
            cleaned_query = t_lower
            for w in self.wake_words:
                cleaned_query = re.sub(rf"^\s*{re.escape(w)}[\s,]*", "", cleaned_query).strip()

            logger.info(f"🎤 [VoiceListener] Wake word triggered! Instruction: '{cleaned_query or text_clean}'")

            event = JarvisEvent(
                source="sensory.microphone.voice_listener",
                type="sensory.voice_transcript",
                data={
                    "raw_transcript": text_clean,
                    "cleaned_instruction": cleaned_query or text_clean,
                    "wake_word_detected": True,
                    "confidence": 0.98
                }
            )
            mesh.publish(event)
            if self.on_transcript_received:
                self.on_transcript_received(cleaned_query or text_clean)
            return event

        return None

    def simulate_speech(self, spoken_text: str) -> Optional[JarvisEvent]:
        """Simulates spoken input for integration tests and API triggers"""
        return self.process_transcript(spoken_text)


voice_listener = VoiceListener()
