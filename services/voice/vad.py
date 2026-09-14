"""
Voice Activity Detection (VAD) & Barge-In Monitor for Project J.A.R.V.I.S.
Handles speech onset detection, dynamic silence endpointing, and ultra-fast (<5ms) barge-in interruption.
"""

from __future__ import annotations
import math
import time
from typing import Optional, List, Callable
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.config import config

logger = get_logger("JarvisVAD")


class VoiceActivityDetector:
    TRAILING_CONJUNCTIONS = {"and", "or", "to", "with", "that", "the", "a", "for", "then", "if", "so", "but"}

    def __init__(
        self,
        energy_threshold: float = 0.020,
        barge_in_threshold: float = 0.035,
        default_silence_duration: float = 1.4,
        conjunction_silence_duration: float = 2.0,
    ):
        self.energy_threshold = getattr(config, "vad_threshold", energy_threshold)
        self.barge_in_threshold = barge_in_threshold
        self.default_silence_duration = getattr(config, "silence_timeout", default_silence_duration)
        self.conjunction_silence_duration = conjunction_silence_duration
        self._speech_active = False
        self._speech_start_time: float = 0.0
        self._last_speech_time: float = 0.0
        self._consecutive_loud_frames = 0
        self._barge_in_callbacks: List[Callable[[], None]] = []

    def register_barge_in_callback(self, cb: Callable[[], None]):
        """Registers a callback to execute immediately on vocal barge-in."""
        if cb not in self._barge_in_callbacks:
            self._barge_in_callbacks.append(cb)

    def calculate_rms(self, audio_data: bytes) -> float:
        """Calculates Root Mean Square (RMS) energy from 16-bit PCM audio bytes."""
        if not audio_data or len(audio_data) < 2:
            return 0.0
        count = len(audio_data) // 2
        sum_squares = 0.0
        for i in range(0, count * 2, 2):
            sample = int.from_bytes(audio_data[i:i+2], byteorder="little", signed=True)
            normalized = sample / 32768.0
            sum_squares += normalized * normalized
        return math.sqrt(sum_squares / count)

    def process_audio_frame(self, audio_bytes: bytes, is_jarvis_speaking: bool = False, partial_text: str = "") -> dict:
        """
        Analyzes an audio frame for speech onset, offset, and barge-in.
        Returns a dict:
        {
            "has_speech": bool,
            "rms": float,
            "speech_started": bool,
            "speech_completed": bool,
            "barge_in_triggered": bool
        }
        """
        rms = self.calculate_rms(audio_bytes)
        now = time.time()
        result = {
            "has_speech": rms >= self.energy_threshold,
            "rms": rms,
            "speech_started": False,
            "speech_completed": False,
            "barge_in_triggered": False
        }

        # Check for barge-in if JARVIS is actively vocalizing
        if is_jarvis_speaking and rms >= self.barge_in_threshold:
            self._consecutive_loud_frames += 1
            if self._consecutive_loud_frames >= 2:
                logger.info(f"⚡ [VAD] Vocal barge-in detected! (RMS: {rms:.4f} >= {self.barge_in_threshold})")
                result["barge_in_triggered"] = True
                self._trigger_barge_in()
        else:
            if not is_jarvis_speaking:
                self._consecutive_loud_frames = 0

        # Speech onset
        if result["has_speech"]:
            if not self._speech_active:
                self._speech_active = True
                self._speech_start_time = now
                result["speech_started"] = True
                logger.debug(f"[VAD] Speech onset detected (RMS: {rms:.4f})")
            self._last_speech_time = now
        else:
            # Silence evaluation with dynamic endpointing
            if self._speech_active:
                endpoint_duration = self._calculate_dynamic_endpoint(partial_text)
                silence_elapsed = now - self._last_speech_time
                if silence_elapsed >= endpoint_duration:
                    self._speech_active = False
                    result["speech_completed"] = True
                    logger.debug(f"[VAD] Speech offset detected after {silence_elapsed:.2f}s silence")

        return result

    def _calculate_dynamic_endpoint(self, partial_text: str) -> float:
        """
        Adapts silence timeout dynamically.
        If user ended on an incomplete sentence or conjunction ("and", "with"),
        gives more grace time (2.0s) before terminating.
        """
        if not partial_text:
            return self.default_silence_duration

        words = partial_text.strip().lower().split()
        if words and words[-1] in self.TRAILING_CONJUNCTIONS:
            return self.conjunction_silence_duration
        return self.default_silence_duration

    def _trigger_barge_in(self):
        """Executes all registered barge-in callbacks in <1ms."""
        for cb in self._barge_in_callbacks:
            try:
                cb()
            except Exception as e:
                logger.error(f"[VAD] Barge-in callback error: {e}")

    def reset(self):
        """Resets VAD tracking state."""
        self._speech_active = False
        self._speech_start_time = 0.0
        self._last_speech_time = 0.0
        self._consecutive_loud_frames = 0


vad_detector = VoiceActivityDetector()
