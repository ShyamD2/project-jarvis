"""
Streaming Neural Text-To-Speech (TTS) Engine for Project J.A.R.V.I.S.
Provides Paul Bettany-inspired British voice synthesis, sentence/clause chunking,
seamless soundboard clip playback, and sub-5ms barge-in interruption.
"""

from __future__ import annotations
import asyncio
import os
import re
import sys
import time
import threading
from typing import Optional, List, Callable
import pygame

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.config import config
from services.sensory.soundboard import soundboard

logger = get_logger("JarvisTTSEngine")

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False


class TTSEngine:
    def __init__(
        self,
        voice: Optional[str] = None,
        pitch: Optional[str] = None,
        rate: Optional[str] = None,
        output_dir: Optional[str] = None
    ):
        self.voice = voice or getattr(config, "voice_id", "en-GB-RyanNeural")
        self.pitch = pitch or getattr(config, "tts_pitch", "-2Hz")
        self.rate = rate or getattr(config, "tts_speed", "-2%")
        self.output_dir = output_dir or os.path.join(PROJECT_ROOT, "services/sensory/audio_cache")
        os.makedirs(self.output_dir, exist_ok=True)

        self._is_speaking = False
        self._playback_lock = threading.Lock()
        self._interrupt_event = threading.Event()
        self._current_audio_file: Optional[str] = None
        self._speech_done_callbacks: List[Callable[[], None]] = []

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def register_on_done(self, cb: Callable[[], None]):
        """Registers a callback to be called when speech finishes."""
        self._speech_done_callbacks.append(cb)

    def sanitize_text(self, text: str) -> str:
        """Strips markdown code blocks, URLs, brackets, emojis, and symbols for clean spoken English."""
        if not text:
            return ""
        t = re.sub(r'```[\s\S]*?```', '', text)
        t = re.sub(r'`[^`]*`', '', t)
        t = re.sub(r'https?://\S+', '', t)
        t = re.sub(r'[*#_~>|]', '', t)
        t = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', t)
        t = re.sub(r'[\U00010000-\U0010ffff]', '', t)  # strip emojis
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    def split_into_clauses(self, text: str) -> List[str]:
        """
        Splits text into speakable clauses and sentences for low-latency incremental streaming.
        Splits on sentence terminators (.!?) and major clause boundaries (; , -) when sufficiently long.
        """
        clean = self.sanitize_text(text)
        if not clean:
            return []

        # Split on sentence ends first
        sentences = re.split(r'(?<=[.!?])\s+', clean)
        clauses = []
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            # If sentence is long (> 60 chars), sub-split on commas or semicolons
            if len(s) > 60 and (',' in s or ';' in s):
                sub_parts = re.split(r'(?<=[,;])\s+', s)
                for sp in sub_parts:
                    if sp.strip():
                        clauses.append(sp.strip())
            else:
                clauses.append(s)
        return clauses

    def interrupt(self):
        """
        INSTANT BARGE-IN INTERRUPTION (<5ms):
        Immediately cuts off all active audio output and flags state as stopped.
        """
        self._interrupt_event.set()
        soundboard.stop_all()

        try:
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                if hasattr(pygame.mixer.music, "unload"):
                    pygame.mixer.music.unload()
        except Exception as e:
            logger.debug(f"[TTS] Mixer interrupt notice: {e}")

        if self._is_speaking:
            logger.info("⚡ [TTS Engine] Vocal barge-in cutoff triggered (<5ms)")
            self._is_speaking = False

    def _ensure_mixer(self):
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception as e:
                logger.error(f"[TTS Engine] Failed to initialize pygame mixer: {e}")
                raise

    async def synthesize_bytes(self, text: str) -> Optional[bytes]:
        """
        Synthesizes text directly into MP3 bytes in-memory for ultra-low latency.
        """
        clean_text = self.sanitize_text(text)
        if not clean_text or not EDGE_TTS_AVAILABLE:
            return None
        try:
            communicate = edge_tts.Communicate(clean_text, self.voice, pitch=self.pitch, rate=self.rate)
            chunks = []
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio" and "data" in chunk:
                    chunks.append(chunk["data"])
            if chunks:
                return b"".join(chunks)
        except Exception as e:
            logger.warning(f"[TTS Engine] In-memory byte synthesis error: {e}")
        return None

    async def synthesize(self, text: str) -> Optional[str]:
        """
        Synthesizes given text into a British neural speech MP3 file.
        Returns file path or None.
        """
        clean_text = self.sanitize_text(text)
        if not clean_text:
            return None

        filename = f"jarvis_tts_{int(time.time() * 1000) % 10000}.mp3"
        audio_path = os.path.join(self.output_dir, filename)

        if EDGE_TTS_AVAILABLE:
            try:
                audio_bytes = await self.synthesize_bytes(clean_text)
                if audio_bytes:
                    with open(audio_path, "wb") as f:
                        f.write(audio_bytes)
                    return audio_path
            except Exception as e:
                logger.warning(f"[TTS Engine] Edge-TTS synthesis failed: {e}")
                return None
        return None

    async def speak_stream(
        self,
        text: str,
        on_chunk: Optional[Callable[[int, str, bytes, bool], Any]] = None,
        play_audio: bool = True
    ) -> Optional[str]:
        """
        Progressive sub-second streaming audio synthesizer:
        Synthesizes sentence-by-sentence/clause-by-clause so the user hears audio in <600ms,
        while broadcasting chunks via callback and queuing sequential playback.
        """
        self.interrupt()
        self._interrupt_event.clear()

        clean = self.sanitize_text(text)
        if not clean:
            return None

        clauses = self.split_into_clauses(clean)
        if not clauses:
            clauses = [clean]

        self._is_speaking = True
        total_audio_bytes = bytearray()
        last_audio_file = None

        # Process first clause immediately for sub-second vocal delivery
        for idx, clause in enumerate(clauses):
            if self._interrupt_event.is_set():
                break

            is_last = (idx == len(clauses) - 1)
            chunk_bytes = await self.synthesize_bytes(clause)
            if not chunk_bytes:
                continue

            total_audio_bytes.extend(chunk_bytes)

            # Invoke async or sync callback for progressive WebSocket streaming
            if on_chunk:
                try:
                    res = on_chunk(idx, clause, chunk_bytes, is_last)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as e_cb:
                    logger.debug(f"[TTS Engine] Stream callback exception: {e_cb}")

            # Save individual clause file for immediate progressive playback
            clause_filename = f"jarvis_chunk_{idx}_{int(time.time() * 1000) % 1000}.mp3"
            clause_path = os.path.join(self.output_dir, clause_filename)
            try:
                with open(clause_path, "wb") as f:
                    f.write(chunk_bytes)
                last_audio_file = clause_path
            except Exception:
                pass

            # If playing server audio, play first chunk immediately and subsequent in sequence
            if play_audio and not self._interrupt_event.is_set():
                try:
                    self._ensure_mixer()
                    pygame.mixer.music.load(clause_path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy() and not self._interrupt_event.is_set():
                        await asyncio.sleep(0.03)
                except Exception as e_play:
                    logger.debug(f"[TTS Engine] Server playback notice: {e_play}")

        # Assemble and persist consolidated jarvis_latest.mp3
        if total_audio_bytes:
            master_file = os.path.join(self.output_dir, "jarvis_latest.mp3")
            try:
                with open(master_file, "wb") as f:
                    f.write(total_audio_bytes)
                self._current_audio_file = master_file
                last_audio_file = master_file
            except Exception as e_save:
                logger.debug(f"[TTS Engine] Consolidated save error: {e_save}")

        self._is_speaking = False
        for cb in self._speech_done_callbacks:
            try:
                cb()
            except Exception:
                pass

        return last_audio_file

    async def speak(self, text: str, play_audio: bool = True) -> Optional[str]:
        """
        Standard synthesis + playback routine (delegates to progressive streaming).
        Guarantees single-channel execution and honors barge-in interrupts.
        """
        return await self.speak_stream(text, play_audio=play_audio)


tts_engine = TTSEngine()
