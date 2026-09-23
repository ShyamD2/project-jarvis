"""
Sensory Audio Soundboard for Project J.A.R.V.I.S.
Maps and delivers authentic movie audio clips from the audio/ folder:
- welcome_back_jarvis.mp3: Greetings, system startup
- jarvis_on.mp3: Wake-word trigger chime, device activation
- Voicy_I Have Run Simulation .mp3: Status reports, diagnostics, simulations
- Voicy_Creating A Flight Plan.mp3: Workspace preparation, complex tasks, planning
- jarvis_alarm.mp3: Emergency stand-down, security alerts
"""

import os
import re
import time
import threading
from typing import Optional, Dict, Any
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisSoundboard")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
AUDIO_DIR = os.path.join(PROJECT_ROOT, "audio")

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


class AudioSoundboard:
    def __init__(self, audio_dir: str = AUDIO_DIR):
        self.audio_dir = audio_dir
        self.clips = {
            "welcome_back": os.path.join(self.audio_dir, "welcome_back_jarvis.mp3"),
            "wake_chime": os.path.join(self.audio_dir, "jarvis_on.mp3"),
            "simulation": os.path.join(self.audio_dir, "Voicy_I Have Run Simulation .mp3"),
            "flight_plan": os.path.join(self.audio_dir, "Voicy_Creating A Flight Plan.mp3"),
            "alarm": os.path.join(self.audio_dir, "jarvis_alarm.mp3")
        }
        self._mixer_initialized = False
        self._lock = threading.Lock()

    def _ensure_mixer(self):
        if not PYGAME_AVAILABLE:
            return False
        with self._lock:
            if not self._mixer_initialized:
                try:
                    pygame.mixer.init()
                    self._mixer_initialized = True
                except Exception as e:
                    logger.warning(f"Failed to initialize Pygame mixer: {e}")
                    return False
        return True

    def list_clips(self) -> Dict[str, Any]:
        """Lists available soundboard clips and their on-disk status"""
        return {
            name: {"path": path, "exists": os.path.exists(path)}
            for name, path in self.clips.items()
        }

    def stop_all(self):
        """Immediately stops any playing soundboard audio"""
        if PYGAME_AVAILABLE and self._mixer_initialized:
            try:
                pygame.mixer.music.stop()
            except Exception as e:
                logger.debug(f"Error stopping soundboard music: {e}")

    def play_clip(self, clip_name: str, block: bool = False) -> bool:
        """
        Plays an authentic soundboard clip locally on the host machine.
        Single-channel guarantee: cancels any running audio prior to starting.
        """
        clip_path = self.clips.get(clip_name)
        if not clip_path or not os.path.exists(clip_path):
            logger.warning(f"Clip '{clip_name}' not found on disk: {clip_path}")
            return False

        if not self._ensure_mixer():
            return self._fallback_play(clip_path)

        try:
            self.stop_all()
            pygame.mixer.music.load(clip_path)
            pygame.mixer.music.play()
            logger.info(f"🔊 [Soundboard] Playing authentic audio clip: '{clip_name}'")
            if block:
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
            return True
        except Exception as e:
            logger.error(f"Error playing soundboard clip '{clip_name}': {e}")
            return False

    def _fallback_play(self, file_path: str) -> bool:
        import subprocess
        try:
            subprocess.Popen(
                ["powershell", "-c", f"(New-Object Media.SoundPlayer '{file_path}').PlaySync()"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            return False

    def match_audio_clip(self, query: str) -> Optional[Dict[str, str]]:
        """
        Matches a user instruction or event to an authentic J.A.R.V.I.S. voice clip.
        Returns clip info dictionary if a match is found, otherwise None for neural TTS.
        """
        q_lower = query.strip().lower()

        # 1. Wake word / Startup / Greetings (explicit phrases only)
        if any(w in q_lower for w in ["welcome back", "wake up"]):
            clip_path = self.clips.get("welcome_back")
            if clip_path and os.path.exists(clip_path):
                return {
                    "clip_name": "welcome_back",
                    "file_path": clip_path,
                    "url": "/api/v1/query/audio/soundboard/welcome_back",
                    "transcript": "Welcome back, sir."
                }

        # 2. Status Report, Diagnostics & Simulation
        if any(w in q_lower for w in ["status report", "run simulation", "start simulation", "movie simulation", "simulation"]):
            clip_path = self.clips.get("simulation")
            if clip_path and os.path.exists(clip_path):
                return {
                    "clip_name": "simulation",
                    "file_path": clip_path,
                    "url": "/api/v1/query/audio/soundboard/simulation",
                    "transcript": "I have run simulations, sir."
                }

        # 3. Workspace Preparation, Flight Plan
        if any(w in q_lower for w in ["prepare my workspace", "workspace", "flight plan", "create a flight plan", "create flight plan"]):
            clip_path = self.clips.get("flight_plan")
            if clip_path and os.path.exists(clip_path):
                return {
                    "clip_name": "flight_plan",
                    "file_path": clip_path,
                    "url": "/api/v1/query/audio/soundboard/flight_plan",
                    "transcript": "Creating a flight plan, sir."
                }

        # 4. Emergency, Stand-Down & Alarms
        if any(w in q_lower for w in ["emergency abort", "alarm", "sound alarm", "play alarm", "intruder alert", "red alert"]):
            clip_path = self.clips.get("alarm")
            if clip_path and os.path.exists(clip_path):
                return {
                    "clip_name": "alarm",
                    "file_path": clip_path,
                    "url": "/api/v1/query/audio/soundboard/alarm",
                    "transcript": "Emergency protocol engaged, standing down immediately."
                }

        # 5. Device activation / power chime
        if any(w in q_lower for w in ["turn on", "power on", "ignite", "activate"]):
            clip_path = self.clips.get("wake_chime")
            if clip_path and os.path.exists(clip_path):
                return {
                    "clip_name": "wake_chime",
                    "file_path": clip_path,
                    "url": "/api/v1/query/audio/soundboard/wake_chime",
                    "transcript": "Systems active, sir."
                }

        return None


soundboard = AudioSoundboard()
