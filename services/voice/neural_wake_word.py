"""
Local Neural Wake-Word Engine for Project J.A.R.V.I.S.
Employs openWakeWord with local ONNX acoustic models (hey_jarvis_v0.1.onnx, silero_vad.onnx).
Operates 100% on-device on CPU with zero cloud cost and low resource footprint.
"""

from __future__ import annotations
import os
import time
import threading
from typing import Optional, Callable, Dict, Any
import numpy as np

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("NeuralWakeWord")

try:
    import openwakeword
    from openwakeword.model import Model
    OPENWAKEWORD_AVAILABLE = True
except ImportError:
    OPENWAKEWORD_AVAILABLE = False
    logger.warning("[NeuralWakeWord] openwakeword package not available.")


class NeuralWakeWordDetector:
    """
    High-performance on-device neural acoustic wake-word detector.
    Continuously listens for 'Hey Jarvis' or 'Jarvis' with sub-10ms local ONNX inference.
    """

    def __init__(
        self,
        wake_words: Optional[list[str]] = None,
        threshold: float = 0.35,
        hold_timeout: float = 8.0,
        sample_rate: int = 16000
    ):
        self.threshold = threshold
        self.hold_timeout = hold_timeout
        self.sample_rate = sample_rate
        self.model: Optional[Model] = None
        self._is_listening = False
        self._last_active_time: float = 0.0
        self._followup_active: bool = False
        self._stream = None
        self._thread: Optional[threading.Thread] = None
        self._on_wake_callback: Optional[Callable[[], None]] = None

        self._init_model(wake_words or ["hey_jarvis"])

    def _init_model(self, model_names: list[str]):
        if not OPENWAKEWORD_AVAILABLE:
            return
        try:
            # Initialize openwakeword with onnx framework
            self.model = Model(wakeword_models=model_names, inference_framework="onnx")
            logger.info(f"[NeuralWakeWord] Initialized local ONNX wake-word model for: {model_names}")
        except Exception as e:
            logger.error(f"[NeuralWakeWord] Failed to load ONNX model ({e}). Attempting fallback download...")
            try:
                openwakeword.utils.download_models()
                self.model = Model(wakeword_models=model_names, inference_framework="onnx")
                logger.info(f"[NeuralWakeWord] ONNX models downloaded and loaded successfully.")
            except Exception as e2:
                logger.error(f"[NeuralWakeWord] Could not initialize model: {e2}")

    def process_frame(self, audio_chunk: np.ndarray) -> Dict[str, float]:
        """
        Processes a single 16kHz audio frame (typically 1280 samples = 80ms).
        Returns dictionary of model predictions: {'hey_jarvis': float_score}.
        """
        if self.model is None:
            return {}

        # Ensure correct dtype
        if audio_chunk.dtype != np.int16:
            if audio_chunk.dtype in [np.float32, np.float64]:
                audio_chunk = (audio_chunk * 32767).astype(np.int16)
            else:
                audio_chunk = audio_chunk.astype(np.int16)

        try:
            prediction = self.model.predict(audio_chunk)
            return prediction
        except Exception as e:
            logger.debug(f"[NeuralWakeWord] Inference notice: {e}")
            return {}

    def evaluate_audio_slice(self, raw_pcm_bytes: bytes, sample_rate: int = 16000) -> bool:
        """
        Evaluates a complete audio buffer (e.g. from SpeechRecognition or PyAudio)
        by slicing it into 80ms chunks and running local ONNX inference on each.
        """
        if not raw_pcm_bytes:
            return False
        arr = np.frombuffer(raw_pcm_bytes, dtype=np.int16)
        chunk_size = 1280
        for i in range(0, len(arr) - chunk_size + 1, chunk_size):
            chunk = arr[i : i + chunk_size]
            if self.is_wake_detected(chunk):
                return True
        return False

    def is_wake_detected(self, audio_chunk: np.ndarray) -> bool:
        """
        Evaluates whether wake word confidence exceeds threshold or follow-up window is active.
        """
        if self.is_in_followup_window():
            return True

        scores = self.process_frame(audio_chunk)
        for name, score in scores.items():
            if score >= self.threshold:
                logger.info(f"🎤 [NeuralWakeWord] Wake word detected: '{name}' (confidence: {score:.3f})")
                self.start_followup_window()
                return True
        return False

    def start_followup_window(self, duration: Optional[float] = None):
        """Extends or starts continuous conversational follow-up window."""
        timeout = duration if duration is not None else self.hold_timeout
        self._last_active_time = time.time() + timeout
        self._followup_active = True
        logger.debug(f"[NeuralWakeWord] Conversational follow-up active for {timeout}s")

    def is_in_followup_window(self) -> bool:
        if not self._followup_active:
            return False
        if time.time() <= self._last_active_time:
            return True
        self._followup_active = False
        return False

    def cancel_followup_window(self):
        self._followup_active = False
        self._last_active_time = 0.0

    def start_listening(self, callback: Callable[[], None]):
        """Starts background acoustic capture thread."""
        if self._is_listening:
            return
        self._on_wake_callback = callback
        self._is_listening = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="NeuralWakeWordWorker")
        self._thread.start()
        logger.info("🎙 [NeuralWakeWord] Continuous local acoustic listener thread started.")

    def stop_listening(self):
        self._is_listening = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("🎙 [NeuralWakeWord] Listener thread stopped.")

    def _capture_loop(self):
        """Acoustic streaming loop reading 80ms chunks (1280 samples at 16kHz)."""
        try:
            import sounddevice as sd
            chunk_size = 1280  # 80ms at 16kHz
            with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='int16', blocksize=chunk_size) as stream:
                while self._is_listening:
                    audio_data, overflowed = stream.read(chunk_size)
                    if overflowed:
                        continue
                    chunk = audio_data.flatten()
                    if self.is_wake_detected(chunk):
                        if self._on_wake_callback:
                            try:
                                self._on_wake_callback()
                            except Exception as cb_err:
                                logger.error(f"Wake callback error: {cb_err}")
        except Exception as e:
            logger.warning(f"[NeuralWakeWord] Sounddevice capture loop notice: {e}")


neural_wake_word = NeuralWakeWordDetector()
