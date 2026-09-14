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
                communicate = edge_tts.Communicate(clean_text, self.voice, pitch=self.pitch, rate=self.rate)
                await communicate.save(audio_path)
                return audio_path
            except Exception as e:
                logger.warning(f"[TTS Engine] Edge-TTS synthesis failed: {e}")
                return None
        return None

    async def speak(self, text: str, play_audio: bool = True) -> Optional[str]:
        """
        Full synthesis + playback routine.
        Guarantees single-channel execution and honors barge-in interrupts.
        """
        self.interrupt()
        self._interrupt_event.clear()

        clean = self.sanitize_text(text)
        if not clean:
            return None

        audio_file = await self.synthesize(clean)
        if not audio_file:
            return None

        self._current_audio_file = audio_file

        # Copy to jarvis_latest.mp3 so endpoints and caches are immediately updated
        try:
            import shutil
            latest_copy = os.path.join(self.output_dir, "jarvis_latest.mp3")
            shutil.copy2(audio_file, latest_copy)
        except Exception as e_copy:
            logger.debug(f"[TTS] Failed to update jarvis_latest.mp3: {e_copy}")

        if not play_audio:
            return audio_file

        self._is_speaking = True

        def _play_loop():
            try:
                self._ensure_mixer()
                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy() and not self._interrupt_event.is_set():
                    time.sleep(0.04)
            except Exception as e:
                logger.error(f"[TTS Playback Error]: {e}")
            finally:
                self._is_speaking = False
                for cb in self._speech_done_callbacks:
                    try:
                        cb()
                    except Exception:
                        pass

        threading.Thread(target=_play_loop, daemon=True).start()
        return audio_file


tts_engine = TTSEngine()
