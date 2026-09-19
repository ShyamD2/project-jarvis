"""
Streaming Speech-To-Text (STT) Engine & Tanglish/Hinglish Normalizer for Project J.A.R.V.I.S.
Integrates Groq Whisper (whisper-large-v3) with zero-temperature acoustic processing,
hallucination filtering, and mixed-language command normalization.
"""

from __future__ import annotations
import io
import os
import re
import time
from typing import Optional, Dict, Any, List, Tuple
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisSTTEngine")

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    Groq = None
    GROQ_AVAILABLE = False


class STTEngine:
    WHISPER_HALLUCINATIONS = {
        "you", "you.", "you!", "you?", "thank you", "thank you.", "thank you!",
        "thanks", "thanks.", "thanks!", "bye", "bye.", "bye bye", "goodbye",
        "subtitles", "subtitles by", "subscribe", "amara.org", "watching",
        "thank you for watching", "thank you for watching.", "the end", "end.",
        "um", "uh", "oh", "ah", "okay", "ok", "so", "yeah", "yes", "no",
        "silence", "blank audio", "applause", "laughter", "music", "bell ring",
        "muffled", "inaudible", "cough", "clears throat"
    }

    WHISPER_PROMPT = (
        "J.A.R.V.I.S., computer. English commands: volume up, volume down, set volume to 50%, "
        "mute audio, unmute, play music, pause, next track, shut down computer, restart PC, lock screen, "
        "what is my CPU usage, check RAM, free disk space, battery status, network IP address, "
        "open Chrome, open Opera, open calculator, close active tab, show bookmarks, "
        "run terraform plan, terraform apply, Docker status, AWS status, Kubernetes pods."
    )

    # Tanglish, Hinglish, and colloquial pattern mappings to clean English commands
    MULTILINGUAL_PATTERNS = [
        # Tamil / Tanglish: "X open pannu", "X thora", "X start pannu"
        (r"\b(?:enakku\s+)?(\w+)\s+(?:open\s+pannu|thora|start\s+pannu)\b", r"open \1"),
        (r"\b(?:open\s+pannu|thora)\s+(\w+)\b", r"open \1"),

        # Tamil / Tanglish: "X moodu", "X close pannu"
        (r"\b(\w+)\s+(?:close\s+pannu|moodu|off\s+pannu)\b", r"close \1"),
        (r"\b(?:close\s+pannu|moodu)\s+(\w+)\b", r"close \1"),

        # Tamil / Tanglish: Volume adjustments
        (r"\b(?:volume|sound)\s+(?:konjam\s+)?(?:kammi|kura|kami)\s+pannu\b", "decrease volume by 5 steps"),
        (r"\b(?:volume|sound)\s+(?:konjam\s+)?(?:athigam|yethu|koodu)\s+pannu\b", "increase volume by 5 steps"),
        (r"\bkonjam\s+volume\s+(?:kammi|kura)\s+pannu\b", "decrease volume by 5 steps"),
        (r"\bkonjam\s+volume\s+(?:athigam|yethu)\s+pannu\b", "increase volume by 5 steps"),

        # Tamil / Tanglish: Telemetry & queries
        (r"\benakku\s+cpu(?:\s+usage)?\s+(?:sollu|paaru)\b", "what is my cpu usage"),
        (r"\benakku\s+ram(?:\s+usage)?\s+(?:sollu|paaru)\b", "what is my ram usage"),
        (r"\benakku\s+(\w+)\s+sollu\b", r"tell me \1"),

        # Tamil / Tanglish: DevOps & Ops
        (r"\bterraform\s+plan\s+(?:run\s+pannu|podu)\b", "run terraform plan"),
        (r"\bterraform\s+apply\s+(?:run\s+pannu|podu)\b", "run terraform apply"),
        (r"\bdocker\s+(?:containers?\s+)?(?:paaru|check\s+pannu)\b", "check docker containers"),

        # Hindi / Hinglish: "X kholo", "X start karo"
        (r"\b(\w+)\s+(?:kholo|chalao|start\s+karo)\b", r"open \1"),
        (r"\b(?:kholo|chalao)\s+(\w+)\b", r"open \1"),

        # Hindi / Hinglish: "X band karo", "X bandh karo"
        (r"\b(\w+)\s+(?:band\s+karo|bandh\s+karo|roko)\b", r"close \1"),
        (r"\b(?:band\s+karo|bandh\s+karo)\s+(\w+)\b", r"close \1"),

        # Hindi / Hinglish: Volume adjustments
        (r"\b(?:thoda\s+)?volume\s+(?:kam\s+karo|ghatao)\b", "decrease volume by 5 steps"),
        (r"\b(?:thoda\s+)?volume\s+(?:badhao|tez\s+karo)\b", "increase volume by 5 steps"),
        (r"\bawaaz\s+(?:kam\s+karo|ghatao)\b", "decrease volume by 5 steps"),
        (r"\bawaaz\s+(?:badhao|tez\s+karo)\b", "increase volume by 5 steps"),

        # Hindi / Hinglish: Queries
        (r"\bmere\s+cpu\s+usage\s+batao\b", "what is my cpu usage"),
        (r"\bmere\s+ram\s+usage\s+batao\b", "what is my ram usage")
    ]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.groq_client = None
        if GROQ_AVAILABLE and self.api_key:
            try:
                self.groq_client = Groq(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client for STT: {e}")

    def normalize_multilingual(self, text: str) -> str:
        """
        Normalizes Tanglish, Hinglish, and colloquial Indian phrases into standard English commands.
        e.g., 'Chrome open pannu' -> 'open Chrome'
              'volume konjam kammi pannu' -> 'decrease volume by 5 steps'
              'Enakku CPU usage sollu' -> 'what is my cpu usage'
        """
        if not text:
            return ""

        normalized = text.strip()
        for pattern, replacement in self.MULTILINGUAL_PATTERNS:
            subbed, count = re.subn(pattern, replacement, normalized, flags=re.IGNORECASE)
            if count > 0:
                logger.info(f"🌐 [STT Normalizer] Translated '{normalized}' -> '{subbed}'")
                normalized = subbed
                break

        return normalized

    def is_hallucination(self, text: str) -> bool:
        """Checks if the transcription is a common Whisper silence hallucination or punctuation noise."""
        if not text:
            return True
        cleaned = text.strip().lower().rstrip(".,!? ")
        if not cleaned:
            return True
        return cleaned in self.WHISPER_HALLUCINATIONS

    def transcribe_sync(self, audio_bytes: bytes, filename: str = "speech.wav") -> Tuple[str, float]:
        """
        Synchronously transcribes audio bytes to text using Groq Whisper.
        Returns:
            (normalized_text, latency_ms)
        """
        start_time = time.time()
        if not audio_bytes or len(audio_bytes) < 400:
            return "", 0.0

        # Method 1: Groq SDK
        if self.groq_client:
            try:
                audio_stream = io.BytesIO(audio_bytes)
                audio_stream.name = filename

                transcription = self.groq_client.audio.transcriptions.create(
                    file=audio_stream,
                    model="whisper-large-v3",
                    prompt=self.WHISPER_PROMPT,
                    response_format="json",
                    language="en",
                    temperature=0.0
                )

                raw_text = (transcription.text or "").strip()
                latency = (time.time() - start_time) * 1000

                if self.is_hallucination(raw_text):
                    logger.debug(f"[STT] Discarded Whisper hallucination: '{raw_text}'")
                    return "", latency

                normalized = self.normalize_multilingual(raw_text)
                logger.info(f"🎙 [STT Result] '{normalized}' (Raw: '{raw_text}', Latency: {latency:.1f}ms)")
                return normalized, latency
            except Exception as e:
                logger.debug(f"[STT] Groq SDK sync failed: {e}, attempting HTTP fallback...")

        # Method 2: Direct HTTP POST via httpx
        if self.api_key:
            try:
                import httpx
                headers = {"Authorization": f"Bearer {self.api_key}"}
                files = {"file": (filename, audio_bytes, "audio/wav")}
                data = {
                    "model": "whisper-large-v3",
                    "temperature": "0.0",
                    "language": "en",
                    "prompt": self.WHISPER_PROMPT
                }
                with httpx.Client(timeout=8.0) as client:
                    resp = client.post("https://api.groq.com/openai/v1/audio/transcriptions", files=files, data=data, headers=headers)
                    if resp.status_code == 200:
                        raw_text = resp.json().get("text", "").strip()
                        latency = (time.time() - start_time) * 1000
                        if self.is_hallucination(raw_text):
                            return "", latency
                        normalized = self.normalize_multilingual(raw_text)
                        logger.info(f"🎙 [STT Result (HTTP)] '{normalized}' (Latency: {latency:.1f}ms)")
                        return normalized, latency
            except Exception as e_http:
                logger.error(f"[STT] Direct HTTP STT failed: {e_http}")

        return "", (time.time() - start_time) * 1000

    async def transcribe(self, audio_bytes: bytes, filename: str = "speech.wav") -> Tuple[str, float]:
        """
        Asynchronously transcribes audio bytes to text using Groq Whisper.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.transcribe_sync, audio_bytes, filename)


stt_engine = STTEngine()
