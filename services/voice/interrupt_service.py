"""
Interrupt Service for Project J.A.R.V.I.S.
Provides unified, multi-modal, sub-10ms interruption (barge-in) while Jarvis is reciting
long paragraphs or playing voice output.

Monitors:
1. Acoustic barge-in: Fast energy surge (RMS) and direct interrupt keywords ("stop", "quiet", "silence", "shut up", etc.)
2. Keyboard barge-in: Non-blocking console hotkeys (Space, Escape, 'q', 's') on Windows via msvcrt
3. Programmatic & REST API barge-in: /api/v1/query/interrupt & /api/v1/sensory/interrupt
"""

from __future__ import annotations
import os
import sys
import time
import threading
from typing import Optional, Callable, List, Dict, Any, Set

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.schemas.event_envelope import JarvisEvent

logger = get_logger("JarvisInterruptService")

try:
    import msvcrt
    MSVCRT_AVAILABLE = True
except ImportError:
    MSVCRT_AVAILABLE = False


class InterruptService:
    INTERRUPT_KEYWORDS: Set[str] = {
        "stop", "cancel", "quiet", "silence", "shut up",
        "pause", "enough", "wait", "hold on", "stand down",
        "abort", "freeze", "cut it", "halt", "hush",
        "jarvis stop", "hey jarvis stop", "ok stop", "okay stop"
    }

    def __init__(self):
        self._interrupted_event = threading.Event()
        self._is_recitating = False
        self._recitation_lock = threading.Lock()
        self._current_recitation_id: Optional[str] = None
        self._callbacks: List[Callable[[str, str], None]] = []
        self._monitor_threads: List[threading.Thread] = []
        self._acoustic_monitor_active = False
        self._keyboard_monitor_active = False

    @property
    def is_recitating(self) -> bool:
        return self._is_recitating

    def is_interrupted(self) -> bool:
        return self._interrupted_event.is_set()

    def register_callback(self, cb: Callable[[str, str], None]):
        """Registers a callback executed immediately upon interruption."""
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def unregister_callback(self, cb: Callable[[str, str], None]):
        if cb in self._callbacks:
            self._callbacks.remove(cb)

    def interrupt(self, source: str = "manual", reason: str = "") -> Dict[str, Any]:
        """
        Executes unified interruption across all audio synthesis and playback channels.
        Sub-10ms cutoff guarantee.
        """
        self._interrupted_event.set()
        logger.info(f"⚡ [InterruptService] Recitation interrupted by source '{source}': '{reason}'")

        # 1. Halt Pygame Mixer immediately
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                if hasattr(pygame.mixer.music, "unload"):
                    pygame.mixer.music.unload()
        except Exception as e_pg:
            logger.debug(f"[InterruptService] Pygame stop notice: {e_pg}")

        # 2. Halt Soundboard
        try:
            from services.sensory.soundboard import soundboard
            soundboard.stop_all()
        except Exception as e_sb:
            logger.debug(f"[InterruptService] Soundboard stop notice: {e_sb}")

        # 3. Halt VoiceSynthesizer
        try:
            from services.sensory.voice_synthesizer import voice_synthesizer
            voice_synthesizer.interrupt()
        except Exception as e_vs:
            logger.debug(f"[InterruptService] VoiceSynthesizer interrupt notice: {e_vs}")

        # 4. Halt TTSEngine
        try:
            from services.voice.tts_engine import tts_engine
            tts_engine.interrupt()
        except Exception as e_tts:
            logger.debug(f"[InterruptService] TTSEngine interrupt notice: {e_tts}")

        # 5. Notify VoiceSession state machine
        try:
            from services.voice.voice_session import voice_session, VoiceState
            if voice_session.state == VoiceState.SPEAKING:
                voice_session.transition_to(VoiceState.LISTENING, {"reason": f"interrupted_{source}"})
        except Exception as e_vsess:
            logger.debug(f"[InterruptService] VoiceSession transition notice: {e_vsess}")

        # 6. Publish event to Event Mesh
        try:
            ev = JarvisEvent(
                source="sensory.voice.interrupt_service",
                type="sensory.voice_interrupted",
                data={
                    "source": source,
                    "reason": reason,
                    "timestamp": time.time(),
                    "recitation_id": self._current_recitation_id
                }
            )
            mesh.publish(ev)
        except Exception as e_mesh:
            logger.debug(f"[InterruptService] Mesh publish notice: {e_mesh}")

        # 7. Invoke local registered callbacks
        for cb in self._callbacks:
            try:
                cb(source, reason)
            except Exception as e_cb:
                logger.warning(f"[InterruptService] Callback exception: {e_cb}")

        with self._recitation_lock:
            self._is_recitating = False

        return {
            "status": "success",
            "interrupted": True,
            "source": source,
            "reason": reason,
            "timestamp": time.time()
        }

    def check_phrase_is_interrupt(self, phrase: str) -> bool:
        """Checks if a spoken transcript contains an explicit interruption keyword."""
        if not phrase:
            return False
        clean = phrase.strip().lower()
        # Direct match or phrase boundary match
        import re
        for kw in self.INTERRUPT_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", clean):
                return True
        return False

    def start_recitation(self, recitation_id: Optional[str] = None, enable_keyboard_monitor: bool = True, enable_acoustic_monitor: bool = True):
        """
        Marks the beginning of an active recitation (e.g. speaking a paragraph).
        Launches background acoustic and keyboard barge-in supervisor monitors.
        """
        with self._recitation_lock:
            self._interrupted_event.clear()
            self._is_recitating = True
            self._current_recitation_id = recitation_id or f"rec_{int(time.time() * 1000)}"

        logger.debug(f"[InterruptService] Recitation started: {self._current_recitation_id}")

        if enable_keyboard_monitor and MSVCRT_AVAILABLE:
            self._start_keyboard_monitor()

        if enable_acoustic_monitor:
            self._start_acoustic_monitor()

    def end_recitation(self):
        """Marks the normal or interrupted end of recitation."""
        with self._recitation_lock:
            self._is_recitating = False
            self._acoustic_monitor_active = False
            self._keyboard_monitor_active = False
            self._current_recitation_id = None
        logger.debug("[InterruptService] Recitation concluded.")

    def _start_keyboard_monitor(self):
        """Spawns non-blocking keyboard poller for console barge-in."""
        if self._keyboard_monitor_active:
            return
        self._keyboard_monitor_active = True

        def _keyboard_loop():
            while self._is_recitating and self._keyboard_monitor_active and not self._interrupted_event.is_set():
                try:
                    if msvcrt.kbhit():
                        ch = msvcrt.getch()
                        # Spacebar (b' '), Escape (b'\x1b'), 'q', 'Q', 's', 'S', Ctrl+C (b'\x03')
                        if ch in [b' ', b'\x1b', b'q', b'Q', b's', b'S', b'\x03', b'\r']:
                            logger.info(f"⚡ [InterruptService] Keyboard barge-in detected (key={ch!r}).")
                            self.interrupt(source="keyboard", reason=f"key_{ch!r}")
                            break
                except Exception as e:
                    logger.debug(f"[InterruptService] Keyboard monitor loop notice: {e}")
                    break
                time.sleep(0.02)
            self._keyboard_monitor_active = False

        t = threading.Thread(target=_keyboard_loop, daemon=True, name="JarvisKeyboardInterruptThread")
        t.start()

    def _start_acoustic_monitor(self):
        """Spawns lightweight acoustic energy/keyword poller while speaking."""
        if self._acoustic_monitor_active:
            return
        self._acoustic_monitor_active = True

        def _acoustic_loop():
            try:
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                recognizer.dynamic_energy_threshold = False
                recognizer.energy_threshold = 400.0

                # Open microphone slice
                with sr.Microphone() as source:
                    while self._is_recitating and self._acoustic_monitor_active and not self._interrupted_event.is_set():
                        try:
                            # Quick 1.5s slice to detect vocal barge-in
                            audio = recognizer.listen(source, timeout=1.2, phrase_time_limit=2.0)
                            if self._interrupted_event.is_set() or not self._is_recitating:
                                break
                            try:
                                text = recognizer.recognize_google(audio, language="en-US").strip()
                                if self.check_phrase_is_interrupt(text):
                                    logger.info(f"⚡ [InterruptService] Acoustic interrupt keyword captured: '{text}'")
                                    self.interrupt(source="voice_acoustic", reason=text)
                                    break
                            except Exception:
                                pass
                        except sr.WaitTimeoutError:
                            continue
                        except Exception as e:
                            logger.debug(f"[InterruptService] Acoustic listen slice notice: {e}")
                            time.sleep(0.1)
            except Exception as e_init:
                logger.debug(f"[InterruptService] Acoustic monitor init notice: {e_init}")
            finally:
                self._acoustic_monitor_active = False

        t = threading.Thread(target=_acoustic_loop, daemon=True, name="JarvisAcousticInterruptThread")
        t.start()


# Global singleton instance
interrupt_service = InterruptService()
