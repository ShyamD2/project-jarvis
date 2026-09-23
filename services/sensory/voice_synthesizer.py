"""
JARVIS Voice Synthesis Engine (TTS).
Produces refined British neural speech with full-duplex Barge-In interruption support
and clause-by-clause streaming for long paragraph recitation.
"""

from __future__ import annotations
import asyncio
import os
import re
import subprocess
import threading
import time
from typing import Optional, List
import pygame
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisVoiceSynthesizer")

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False


class VoiceSynthesizer:
    def __init__(self, voice: str = "en-GB-RyanNeural", pitch: str = "-2Hz", rate: str = "-2%", output_dir: Optional[str] = None):
        self.voice = voice
        self.pitch = pitch
        self.rate = rate
        self.output_dir = output_dir or os.path.join(os.path.dirname(__file__), "audio_cache")
        os.makedirs(self.output_dir, exist_ok=True)
        self._is_speaking = False
        self._current_process: Optional[subprocess.Popen] = None
        self.latest_audio_path: str = os.path.join(self.output_dir, "jarvis_latest.mp3")

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def _sanitize_text(self, text: str) -> str:
        """Strips markdown code blocks, URLs, asterisks, and brackets for clean speech."""
        t = re.sub(r'```[\s\S]*?```', '', text)
        t = re.sub(r'`[^`]*`', '', t)
        t = re.sub(r'https?://\S+', '', t)
        t = re.sub(r'[*#_~>|]', '', t)
        t = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', t)
        t = re.sub(r'[\U00010000-\U0010ffff]', '', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    def split_into_clauses(self, text: str) -> List[str]:
        """
        Splits text into speakable clauses and sentences for low-latency incremental recitation.
        Splits on sentence terminators (.!?) and major clause boundaries (, ;) when sufficiently long.
        """
        clean = self._sanitize_text(text)
        if not clean:
            return []

        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean) if s.strip()]
        clauses = []
        for s in sentences:
            if len(s) > 70 and (',' in s or ';' in s):
                sub = [sp.strip() for sp in re.split(r'(?<=[,;])\s+', s) if sp.strip()]
                clauses.extend(sub)
            else:
                clauses.append(s)
        return clauses or [clean]

    def _ensure_mixer(self):
        """Ensures pygame.mixer is initialized for audio playback."""
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception as e:
                logger.error(f"[VoiceSynthesizer] Failed to initialize pygame.mixer: {e}")
                raise

    def interrupt(self):
        """
        BARGE-IN CIRCUIT:
        Immediately halts any running audio playback when the user interrupts or speaks.
        """
        try:
            from services.sensory.soundboard import soundboard
            soundboard.stop_all()
        except Exception as e:
            logger.debug(f"[VoiceSynthesizer] Soundboard stop error: {e}")

        try:
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                if hasattr(pygame.mixer.music, "unload"):
                    pygame.mixer.music.unload()
        except Exception as e:
            logger.warning(f"[VoiceSynthesizer] Mixer stop error: {e}")

        if self._current_process:
            try:
                self._current_process.terminate()
            except Exception as e:
                logger.warning(f"[VoiceSynthesizer] Process termination error: {e}")
            self._current_process = None

        if self._is_speaking:
            logger.info("⚡ [VoiceSynthesizer] Barge-in detected! Halting speech immediately.")
            self._is_speaking = False

    async def speak(self, text: str, play_audio: bool = True, block_until_done: bool = False) -> str:
        """
        Synthesizes text into natural British speech.
        If text is a long paragraph (>1 sentence or >90 chars), recites clause-by-clause
        with continuous interruption supervision by InterruptService.
        """
        # Halt previous speech cleanly
        self.interrupt()

        self._is_speaking = True
        clean_text = self._sanitize_text(text)
        if not clean_text:
            clean_text = "Instruction processed, sir."
        logger.info(f"🎙 [JARVIS Voice]: \"{clean_text}\"")

        # For long paragraphs, use clause-by-clause supervised recitation
        clauses = self.split_into_clauses(clean_text)
        if len(clauses) > 1 and play_audio:
            return await self._recite_paragraph(clauses, block_until_done=block_until_done)

        # Single clause or short response
        filename = f"jarvis_{int(time.time() * 1000) % 10000}.mp3"
        audio_file = os.path.join(self.output_dir, filename)
        self.latest_audio_path = audio_file

        if EDGE_TTS_AVAILABLE:
            try:
                communicate = edge_tts.Communicate(clean_text, self.voice, pitch=self.pitch, rate=self.rate)
                await communicate.save(audio_file)
            except Exception as e:
                logger.warning(f"Edge-TTS failed: {e}. Using Windows SAPI fallback.")
                return self._fallback_speak(clean_text, play_audio)
        else:
            return self._fallback_speak(clean_text, play_audio)

        if not play_audio:
            # Keep _is_speaking = True for barge-in test verification until interrupt is called
            return audio_file

        if play_audio and os.path.exists(audio_file):
            def play():
                try:
                    self._ensure_mixer()
                    pygame.mixer.music.load(audio_file)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        if not self._is_speaking:
                            pygame.mixer.music.stop()
                            break
                        time.sleep(0.02)
                except Exception as e:
                    logger.error(f"[VoiceSynthesizer] Audio playback error: {e}")
                finally:
                    self._is_speaking = False

            t = threading.Thread(target=play, daemon=True)
            t.start()
            if block_until_done:
                t.join()

        return audio_file

    async def _recite_paragraph(self, clauses: List[str], block_until_done: bool = False) -> str:
        """
        Progressively recites a multi-sentence/long paragraph clause-by-clause.
        Actively checks interrupt_service and VoiceSynthesizer state before each clause
        and every 25ms during playback, immediately breaking on user barge-in.
        """
        from services.voice.interrupt_service import interrupt_service

        interrupt_service.start_recitation(enable_keyboard_monitor=True, enable_acoustic_monitor=True)
        master_filename = f"jarvis_para_{int(time.time() * 1000) % 10000}.mp3"
        master_path = os.path.join(self.output_dir, master_filename)
        self.latest_audio_path = master_path

        def recite_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                for idx, clause in enumerate(clauses):
                    if not self._is_speaking or interrupt_service.is_interrupted():
                        logger.info(f"⚡ [VoiceSynthesizer] Paragraph recitation aborted at clause {idx+1}/{len(clauses)}.")
                        break

                    chunk_file = os.path.join(self.output_dir, f"jarvis_part_{idx}_{int(time.time() * 1000) % 1000}.mp3")
                    try:
                        if EDGE_TTS_AVAILABLE:
                            comm = edge_tts.Communicate(clause, self.voice, pitch=self.pitch, rate=self.rate)
                            loop.run_until_complete(comm.save(chunk_file))
                        else:
                            self._fallback_speak(clause, play_audio=False)
                            chunk_file = os.path.join(self.output_dir, "jarvis_latest.wav")
                    except Exception as e_comm:
                        logger.debug(f"[VoiceSynthesizer] Clause synthesis error: {e_comm}")
                        continue

                    if not self._is_speaking or interrupt_service.is_interrupted():
                        break

                    if os.path.exists(chunk_file):
                        try:
                            self._ensure_mixer()
                            pygame.mixer.music.load(chunk_file)
                            pygame.mixer.music.play()
                            while pygame.mixer.music.get_busy():
                                if not self._is_speaking or interrupt_service.is_interrupted():
                                    pygame.mixer.music.stop()
                                    if hasattr(pygame.mixer.music, "unload"):
                                        pygame.mixer.music.unload()
                                    break
                                time.sleep(0.02)
                        except Exception as e_play:
                            logger.debug(f"[VoiceSynthesizer] Clause play notice: {e_play}")

                loop.close()
            finally:
                self._is_speaking = False
                interrupt_service.end_recitation()

        t = threading.Thread(target=recite_thread, daemon=True, name="JarvisParagraphRecitationThread")
        t.start()
        if block_until_done:
            t.join()

        return master_path

    def _fallback_speak(self, text: str, play_audio: bool) -> str:
        """Windows Native SAPI Speech Synthesizer fallback"""
        audio_file = os.path.join(self.output_dir, "jarvis_latest.wav")
        clean_text = text.replace("'", " ").replace('"', " ").replace("`", " ")
        ps_cmd = (
            f"Add-Type -AssemblyName System.speech; "
            f"$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$speak.SetOutputToWaveFile('{audio_file}'); "
            f"$speak.Speak('{clean_text}'); "
            f"$speak.Dispose();"
        )
        try:
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=10)
            if res.returncode != 0:
                logger.error(f"[VoiceSynthesizer] SAPI fallback script failed: {res.stderr}")
        except Exception as e:
            logger.error(f"[VoiceSynthesizer] SAPI fallback execution error: {e}")

        if play_audio and os.path.exists(audio_file):
            def play():
                try:
                    self._ensure_mixer()
                    pygame.mixer.music.load(audio_file)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy() and self._is_speaking:
                        time.sleep(0.05)
                except Exception as e:
                    logger.error(f"[VoiceSynthesizer] SAPI audio playback error: {e}")
                finally:
                    self._is_speaking = False

            threading.Thread(target=play, daemon=True).start()

        return audio_file


voice_synthesizer = VoiceSynthesizer()
