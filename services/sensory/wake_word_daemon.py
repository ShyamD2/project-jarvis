"""
Autonomous Hands-Free Wake-Word Daemon for Project J.A.R.V.I.S.
Continuously listens via system microphone for 'Jarvis' / 'Hey Jarvis'
and executes commands hands-free without requiring physical mouse or keyboard clicks.
Supports single-channel authentic soundboard playback, neural TTS, and instant barge-in.
"""

import os
import sys
import time
import re
import threading
import asyncio
from typing import Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/brain"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/sensory"))

from shared.sdk_python.jarvis_sdk.logger import get_logger
from services.sensory.soundboard import soundboard
from services.sensory.voice_synthesizer import voice_synthesizer
from services.brain.agent_runtime import runtime as brain_runtime

logger = get_logger("JarvisWakeWordDaemon")

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False


class WakeWordDaemon:
    def __init__(self, wake_words: Optional[list[str]] = None):
        self.wake_words = wake_words or ["jarvis", "hey jarvis"]
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self.recognizer: Optional[sr.Recognizer] = None
        self.microphone: Optional[sr.Microphone] = None

    def start(self):
        """Starts the continuous hands-free background listener thread"""
        if not SR_AVAILABLE:
            logger.warning("SpeechRecognition not available; WakeWordDaemon cannot start.")
            return False

        if self.is_running:
            logger.info("WakeWordDaemon already running.")
            return True

        self.is_running = True
        self._thread = threading.Thread(target=self._listener_loop, daemon=True, name="JarvisWakeWordThread")
        self._thread.start()
        logger.info("🎙 [WakeWordDaemon] Hands-free acoustic listener started. Speak 'Jarvis' anytime.")
        return True

    def stop(self):
        """Halts the listener thread"""
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("🎙 [WakeWordDaemon] Listener stopped.")

    def _listener_loop(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8

        try:
            self.microphone = sr.Microphone()
        except Exception as e:
            logger.error(f"Failed to access default microphone: {e}")
            self.is_running = False
            return

        with self.microphone as source:
            logger.info("Calibrating microphone for ambient room noise...")
            try:
                self.recognizer.adjust_for_ambient_noise(source, duration=1.2)
                logger.info(f"Ambient calibration complete (energy threshold: {self.recognizer.energy_threshold:.1f})")
            except Exception as e:
                logger.warning(f"Ambient noise calibration warning: {e}")

        while self.is_running:
            try:
                with self.microphone as source:
                    # Non-blocking listen slice
                    audio = self.recognizer.listen(source, timeout=2.5, phrase_time_limit=6.5)

                try:
                    text = self.recognizer.recognize_google(audio, language="en-US").strip()
                except sr.UnknownValueError:
                    continue
                except sr.RequestError:
                    time.sleep(1.0)
                    continue

                if not text:
                    continue

                t_lower = text.lower()
                logger.info(f"Acoustic audio captured: '{text}'")

                # 1. Instant Barge-In / Audio Interruption Check
                if any(w in t_lower for w in ["stop", "cancel", "quiet", "silence", "shut up", "freeze", "abort"]):
                    logger.info("⚡ Barge-in interrupt received via speech. Stopping audio immediately.")
                    soundboard.stop_all()
                    voice_synthesizer.interrupt()
                    continue

                # 2. Wake Word Detection
                wake_match = any(re.search(rf"\b{re.escape(w)}\b", t_lower) for w in self.wake_words)
                if wake_match:
                    logger.info(f"🎤 Wake word triggered! Spoken: '{text}'")

                    # Extract instruction if user spoke it in the same sentence
                    command = t_lower
                    for w in self.wake_words:
                        command = re.sub(rf"^\s*{re.escape(w)}[\s,]*", "", command).strip()

                    # If user just said 'Jarvis', play wake chime and listen for command
                    if not command or len(command) < 3:
                        soundboard.play_clip("wake_chime")
                        logger.info("Awaiting follow-up voice command...")
                        try:
                            with self.microphone as source:
                                cmd_audio = self.recognizer.listen(source, timeout=5.0, phrase_time_limit=7.0)
                                command = self.recognizer.recognize_google(cmd_audio, language="en-US").strip()
                        except Exception:
                            # If no follow-up, play welcome back greeting
                            soundboard.play_clip("welcome_back")
                            continue

                    if command:
                        logger.info(f"⚡ Executing hands-free voice command: '{command}'")
                        self._process_command(command)

            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                logger.warning(f"Wake word loop exception: {e}")
                time.sleep(0.5)

    def _process_command(self, command: str):
        """Executes command through soundboard or brain runtime"""
        matched = soundboard.match_audio_clip(command)
        if matched:
            soundboard.play_clip(matched["clip_name"])
            # Still run brain turn asynchronously for side-effects
            try:
                asyncio.run(brain_runtime.execute_turn(command))
            except Exception as e:
                logger.warning(f"Brain turn error: {e}")
        else:
            try:
                result = asyncio.run(brain_runtime.execute_turn(command))
                response_text = result.get("response", "Instruction completed, sir.")
                asyncio.run(voice_synthesizer.speak(response_text, play_audio=True))
            except Exception as e:
                logger.error(f"Error executing hands-free command: {e}")


wake_word_daemon = WakeWordDaemon()

if __name__ == "__main__":
    daemon = WakeWordDaemon()
    daemon.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        daemon.stop()
