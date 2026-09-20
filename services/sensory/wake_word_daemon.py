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
            import pyaudio
            p = pyaudio.PyAudio()
            best_idx = None
            candidates = []
            for i in range(p.get_device_count()):
                try:
                    info = p.get_device_info_by_index(i)
                except Exception:
                    continue
                name = info.get("name", "")
                max_in = int(info.get("maxInputChannels", 0))
                if max_in > 0:
                    name_low = name.lower()
                    if any(bad in name_low for bad in ["droidcam", "virtual", "stereo mix", "steam", "cable", "mapper", "hands-free"]):
                        continue
                    score = 0
                    if "array" in name_low: score += 100
                    if "intel" in name_low: score += 50
                    if "realtek" in name_low: score += 30
                    if info.get("hostApi") == 0: score += 40  # MME HostAPI is most reliable on Windows
                    candidates.append((score, i, name))
            p.terminate()
            candidates.sort(key=lambda x: x[0], reverse=True)
            if candidates and candidates[0][0] > 0:
                best_idx = candidates[0][1]
                safe_name = candidates[0][2].encode('ascii', 'ignore').decode('ascii')
                logger.info(f"🎙 [WakeWordDaemon] Bound to hardware microphone [{best_idx}]: '{safe_name}'")

            if best_idx is not None:
                self.microphone = sr.Microphone(device_index=best_idx)
            else:
                self.microphone = sr.Microphone()
        except Exception as e:
            logger.error(f"Failed to access microphone: {e}")
            try:
                self.microphone = sr.Microphone()
            except Exception:
                self.is_running = False
                return

        with self.microphone as source:
            logger.info("Calibrating microphone for ambient room noise...")
            try:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
                self.recognizer.energy_threshold = min(max(self.recognizer.energy_threshold, 150.0), 550.0)
                logger.info(f"Ambient calibration complete (energy threshold: {self.recognizer.energy_threshold:.1f})")
            except Exception as e:
                logger.warning(f"Ambient noise calibration warning: {e}")

        while self.is_running:
            try:
                with self.microphone as source:
                    # Non-blocking listen slice
                    audio = self.recognizer.listen(source, timeout=2.5, phrase_time_limit=6.5)

                raw_bytes = audio.get_raw_data(convert_rate=16000, convert_width=2)
                from services.voice.neural_wake_word import neural_wake_word
                wake_match = neural_wake_word.evaluate_audio_slice(raw_bytes)

                text = ""
                # If local neural wake word triggered
                if wake_match:
                    logger.info("🎤 [WakeWordDaemon] Neural ONNX acoustic model confirmed wake word!")
                else:
                    # Quick speech check fallback for natural speaking cadence
                    try:
                        text = self.recognizer.recognize_google(audio, language="en-US").strip()
                        t_check = text.lower()
                        if any(w in t_check for w in ["jarvis", "service", "travis", "javis", "harvis"]):
                            wake_match = True
                            logger.info(f"🎤 [WakeWordDaemon] Fallback confirmed wake word from: '{text}'")
                    except Exception:
                        pass

                if not wake_match:
                    continue

                # If text wasn't already transcribed, transcribe it now
                if not text:
                    try:
                        text = self.recognizer.recognize_google(audio, language="en-US").strip()
                    except Exception:
                        text = ""

                t_lower = text.lower() if text else ""
                if text:
                    logger.info(f"Acoustic audio captured: '{text}'")

                # 1. Instant Barge-In / Audio Interruption Check
                if any(w in t_lower for w in ["stop", "cancel", "quiet", "silence", "shut up", "freeze", "abort"]):
                    logger.info("⚡ Barge-in interrupt received via speech. Stopping audio immediately.")
                    soundboard.stop_all()
                    voice_synthesizer.interrupt()
                    continue

                # 2. Clean command extraction & wake-word prefix stripping
                command = t_lower.strip()
                wake_prefixes = [
                    r"^(?:hey|hi|hello|ok)?\s*jarvis[\s,:]*",
                    r"^(?:hey|hi|hello|ok)?\s*service[\s,:]*",
                    r"^(?:hey|hi|hello|ok)?\s*travis[\s,:]*",
                    r"^(?:hey|hi|hello|ok)?\s*javis[\s,:]*",
                ]
                for pat in wake_prefixes:
                    if re.search(pat, command, re.IGNORECASE):
                        command = re.sub(pat, "", command, count=1, flags=re.IGNORECASE).strip()
                        break

                # If user just said 'Jarvis' or 'Hey Jarvis' with no trailing command:
                if not command or len(command) < 2:
                    logger.info("🎤 Wake word confirmed. Playing activation chime and awaiting prompt...")
                    soundboard.play_clip("wake_chime")
                    try:
                        with self.microphone as source:
                            cmd_audio = self.recognizer.listen(source, timeout=6.0, phrase_time_limit=8.0)
                            command = self.recognizer.recognize_google(cmd_audio, language="en-US").strip()
                    except Exception:
                        # If no follow-up within timeout, play greeting
                        logger.info("No follow-up voice prompt received within timeout.")
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
        """Executes command through soundboard or conversation engine"""
        # Check if user asked to open or show HUD
        if any(w in command.lower() for w in ["show hud", "open hud", "start hud", "open floating", "show floating", "launch hud"]):
            try:
                import subprocess
                hud_script = os.path.join(PROJECT_ROOT, "run_floating_agent.bat")
                subprocess.Popen(["cmd.exe", "/c", hud_script], cwd=PROJECT_ROOT)
                soundboard.play_clip("welcome_back")
                return
            except Exception as e:
                logger.error(f"Error launching HUD: {e}")

        matched = soundboard.match_audio_clip(command)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from services.brain.conversation_engine import conversation_engine
            if matched:
                soundboard.play_clip(matched["clip_name"])
                loop.run_until_complete(conversation_engine.process_turn(command))
            else:
                result = loop.run_until_complete(conversation_engine.process_turn(command))
                response_text = result.get("response", "Instruction completed, sir.")
                loop.run_until_complete(voice_synthesizer.speak(response_text, play_audio=True))
        except Exception as e:
            logger.error(f"[WakeWordDaemon] Error executing hands-free command: {e}")
        finally:
            try:
                loop.close()
            except Exception:
                pass


wake_word_daemon = WakeWordDaemon()

if __name__ == "__main__":
    daemon = WakeWordDaemon()
    daemon.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        daemon.stop()
