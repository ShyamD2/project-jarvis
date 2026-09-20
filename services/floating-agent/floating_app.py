"""
Floating 3D Desktop Agent Launcher for Project J.A.R.V.I.S.
Launches the full-screen, solid non-transparent 3D desktop command center.
Supports pywebview with Edge WebView2 runtime and direct backend bridging.
"""

from __future__ import annotations
import os
import sys
import subprocess
import time

if sys.stdout is None:
    try:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass
if sys.stderr is None:
    try:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass
import threading
import ctypes
import urllib.request
import re
import base64
from typing import Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisFloatingApp")

HTML_PATH = os.path.join(PROJECT_ROOT, "services", "floating-agent", "floating_agent.html")
SERVER_URL = "http://127.0.0.1:8000/floating_agent"
HUD_PORT = 8088

import http.server
import socketserver


class JarvisHUDHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/floating_agent", "/index.html"):
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with open(HTML_PATH, "rb") as f:
                self.wfile.write(f.read())
            return
        elif self.path.startswith("/static/"):
            rel_path = self.path[8:]
            target = os.path.join(PROJECT_ROOT, "services", "jarvis-core", "static", rel_path)
            if os.path.exists(target):
                self.send_response(200)
                if target.endswith(".js"):
                    self.send_header("Content-type", "application/javascript")
                elif target.endswith(".css"):
                    self.send_header("Content-type", "text/css")
                self.end_headers()
                with open(target, "rb") as f:
                    self.wfile.write(f.read())
                return
        self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        pass


def ensure_hud_server() -> str:
    """Ensures local HTTP server is active so WebView2 operates in a Secure Context with full Web Audio & Mic support."""
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/health", headers={"User-Agent": "JarvisLauncher"})
        with urllib.request.urlopen(req, timeout=0.15) as resp:
            if resp.status == 200:
                return SERVER_URL
    except Exception:
        pass

    try:
        server = socketserver.TCPServer(("127.0.0.1", HUD_PORT), JarvisHUDHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        logger.info(f"⚡ [FloatingApp] Embedded HUD server active at http://127.0.0.1:{HUD_PORT}/floating_agent")
        return f"http://127.0.0.1:{HUD_PORT}/floating_agent"
    except OSError:
        # Port already bound or running
        return f"http://127.0.0.1:{HUD_PORT}/floating_agent"
    except Exception as e:
        logger.warning(f"[FloatingApp] Embedded server note: {e}")
        return f"file:///{HTML_PATH.replace(os.sep, '/')}"


def get_target_url() -> str:
    """Returns local server URL (providing Secure Context for Web Audio & Mic)."""
    return ensure_hud_server()


def ensure_interactive_desktop():
    """Binds calling thread to active input desktop so GUI windows appear on active display."""
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
            if not hdesk:
                hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
        except Exception:
            pass


def get_best_hardware_microphone() -> tuple[Optional[int], int]:
    """
    Scans system audio input devices, actively probes their real RMS audio signal,
    and returns (device_index, sample_rate) for the active physical hardware microphone.
    """
    try:
        import pyaudio
        import audioop
        p = pyaudio.PyAudio()
        candidates = []
        for i in range(p.get_device_count()):
            try:
                info = p.get_device_info_by_index(i)
            except Exception:
                continue
            max_in = int(info.get("maxInputChannels", 0))
            if max_in <= 0:
                continue
            name = info.get("name", "")
            name_low = name.lower()
            if any(bad in name_low for bad in ["droidcam", "virtual", "stereo mix", "steam", "mapper", "hands-free"]):
                continue
            sr = int(info.get("defaultSampleRate", 44100))

            rms = 0
            try:
                stream = p.open(format=pyaudio.paInt16, channels=1, rate=sr, input=True, input_device_index=i, frames_per_buffer=1024)
                data = stream.read(1024, exception_on_overflow=False)
                rms = audioop.rms(data, 2)
                stream.stop_stream()
                stream.close()
            except Exception:
                continue

            score = 0
            # Primary physical microphone array boost
            if "microphone array" in name_low:
                score += 350
            if "intel" in name_low or "smart sound" in name_low:
                score += 200
            if "realtek" in name_low:
                score += 150

            # Reward healthy acoustic room floor (30 - 2000 RMS)
            if 30 <= rms <= 2000:
                score += 200
            elif rms > 4000:
                score -= 200  # Penalize distorted/loopback hiss
            elif rms == 0:
                score -= 200  # Penalize dead/silent stream

            # Host API 0 (MME) is most stable with PyAudio on Windows
            if info.get("hostApi") == 0:
                score += 50

            candidates.append((score, i, name, sr, rms))
        p.terminate()
        candidates.sort(key=lambda x: x[0], reverse=True)
        if candidates and candidates[0][0] > 0:
            best = candidates[0]
            safe_name = best[2].encode('ascii', 'ignore').decode('ascii')
            logger.info(f"🎙️ [VoiceBridge] Selected active hardware mic [{best[1]}]: '{safe_name}' (Rate: {best[3]}Hz, RMS: {best[4]}, Score: {best[0]})")
            return (best[1], best[3])
    except Exception as e:
        logger.warning(f"[VoiceBridge] Microphone resolution notice: {e}")
    return (None, 44100)


def get_best_hardware_microphone_index() -> Optional[int]:
    idx, _ = get_best_hardware_microphone()
    return idx


class FloatingAgentAPI:
    def __init__(self):
        self._window = None
        self._recognizer = None
        self._microphone = None
        self._is_listening = False
        self._listen_thread = None
        self._is_speaking_tts = False

    def set_tts_speaking(self, is_speaking: bool):
        """Notifies the VAD engine whether TTS audio is currently speaking to prevent acoustic loop."""
        self._is_speaking_tts = bool(is_speaking)

    def bind_window(self, window):
        self._window = window

    def set_window_size(self, width: int, height: int):
        """Dynamically resizes the window."""
        if self._window:
            try:
                self._window.resize(width, height)
            except Exception as e:
                logger.debug(f"[FloatingApp] Window resize notice: {e}")

    def toggle_mini_mode(self, is_mini: bool):
        """Switches between compact HUD (420x560) and sleek Mini Orb (96x96)."""
        if self._window:
            try:
                if is_mini:
                    self._window.resize(96, 96)
                else:
                    self._window.resize(420, 560)
            except Exception as e:
                logger.debug(f"[FloatingApp] Mini mode resize error: {e}")

    def toggle_fullscreen(self):
        """Toggles fullscreen state."""
        if self._window:
            try:
                self._window.toggle_fullscreen()
            except Exception as e:
                logger.debug(f"[FloatingApp] Fullscreen toggle: {e}")

    def minimize(self):
        """Minimizes the window to taskbar."""
        if self._window:
            try:
                self._window.minimize()
            except Exception as e:
                logger.debug(f"[FloatingApp] Minimize: {e}")

    def close(self):
        """Closes the window."""
        if self._window:
            try:
                self._window.destroy()
            except Exception as e:
                pass

    def _init_audio(self):
        """Pre-probes and caches the best hardware microphone."""
        if self._microphone is None:
            try:
                best_idx, best_sr = get_best_hardware_microphone()
                self._microphone = (best_idx, best_sr)
                logger.info(f"🎙️ [VoiceBridge] Pre-initialized hardware mic on index {best_idx} ({best_sr}Hz).")
            except Exception as e:
                logger.error(f"[VoiceBridge] Microphone initialization notice: {e}")

    def toggle_voice_capture(self, state: Optional[bool] = None) -> dict:
        """Toggles hardware microphone listening on or off."""
        if state is None:
            new_state = not self._is_listening
        else:
            new_state = bool(state)

        if new_state:
            return self.start_voice_listening()
        else:
            return self.stop_voice_listening()

    def start_voice_listening(self) -> dict:
        """Starts continuous hardware microphone capture loop in background thread."""
        if self._is_listening:
            if self._window:
                try:
                    self._window.evaluate_js("window.onVoiceStatusChanged && window.onVoiceStatusChanged(true)")
                except Exception:
                    pass
            return {"success": True, "listening": True}

        self._is_listening = True

        def _mic_worker():
            import pyaudio
            import audioop
            import io
            import wave
            import json
            from services.voice.stt_engine import stt_engine

            best_idx, best_sr = get_best_hardware_microphone()
            target_sr = 16000

            logger.info(f"🎙️ [VoiceBridge] Continuous hardware microphone capture active on Device {best_idx} ({target_sr}Hz).")

            # Signal UI that mic is active (retrying up to 12s until WebView2 window is ready)
            def _signal_ui_ready():
                for _ in range(24):
                    if not self._is_listening:
                        break
                    if self._window:
                        try:
                            self._window.evaluate_js("window.onVoiceStatusChanged && window.onVoiceStatusChanged(true)")
                            break
                        except Exception:
                            pass
                    time.sleep(0.5)

            threading.Thread(target=_signal_ui_ready, daemon=True).start()

            p = pyaudio.PyAudio()
            try:
                actual_sr = 16000
                try:
                    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, input_device_index=best_idx, frames_per_buffer=1024)
                except Exception:
                    actual_sr = best_sr if best_sr else 44100
                    stream = p.open(format=pyaudio.paInt16, channels=1, rate=actual_sr, input=True, input_device_index=best_idx, frames_per_buffer=1024)

                logger.info(f"🎙️ [VoiceBridge] Audio stream opened at {actual_sr}Hz on device {best_idx}.")

                # Calibrate ambient noise baseline (10 chunks = ~0.64s)
                baseline_rms = 0.0
                for _ in range(10):
                    data = stream.read(1024, exception_on_overflow=False)
                    baseline_rms += audioop.rms(data, 2)
                baseline_rms = max(100.0, baseline_rms / 10.0)
                speech_threshold = max(350, int(baseline_rms * 1.45))
                logger.info(f"🎙️ [VoiceBridge] Calibrated baseline RMS: {baseline_rms:.1f}, Speech threshold: {speech_threshold}")

                is_capturing = False
                speech_chunks = []
                silence_chunks = 0
                max_silence = 10  # ~0.64s of silence concludes phrase

                while self._is_listening:
                    try:
                        data = stream.read(1024, exception_on_overflow=False)
                        if self._is_speaking_tts:
                            # Echo cancellation: suppress mic capture during Jarvis's own voice playback
                            time.sleep(0.01)
                            continue

                        rms = audioop.rms(data, 2)

                        if not is_capturing:
                            if rms > speech_threshold:
                                is_capturing = True
                                speech_chunks = [data]
                                silence_chunks = 0
                                if self._window:
                                    try:
                                        self._window.evaluate_js("window.onVoiceActivity && window.onVoiceActivity(true)")
                                    except Exception:
                                        pass
                            else:
                                # Slowly adapt baseline to shifting room acoustics
                                baseline_rms = baseline_rms * 0.97 + rms * 0.03
                                speech_threshold = max(350, int(baseline_rms * 1.45))
                                # Send energy for subtle idle wave bar movement
                                if self._window and rms > 120:
                                    try:
                                        norm_e = min(1.0, rms / 1500.0)
                                        self._window.evaluate_js(f"window.updateAudioEnergy && window.updateAudioEnergy({norm_e:.3f})")
                                    except Exception:
                                        pass
                        else:
                            # Capturing active speech
                            speech_chunks.append(data)
                            if self._window:
                                try:
                                    norm_e = min(1.0, max(0.25, rms / 2000.0))
                                    self._window.evaluate_js(f"window.updateAudioEnergy && window.updateAudioEnergy({norm_e:.3f})")
                                except Exception:
                                    pass

                            if rms > speech_threshold * 0.70:
                                silence_chunks = 0
                            else:
                                silence_chunks += 1
                                if silence_chunks >= max_silence:
                                    is_capturing = False
                                    total_frames = len(speech_chunks)
                                    captured_audio = b"".join(speech_chunks)
                                    speech_chunks = []
                                    silence_chunks = 0

                                    if self._window:
                                        try:
                                            self._window.evaluate_js("window.onVoiceActivity && window.onVoiceActivity(false)")
                                        except Exception:
                                            pass

                                    # Need at least ~0.32s of speech (5 chunks)
                                    if total_frames >= 5:
                                        buf = io.BytesIO()
                                        with wave.open(buf, 'wb') as wf:
                                            wf.setnchannels(1)
                                            wf.setsampwidth(2)
                                            wf.setframerate(actual_sr)
                                            wf.writeframes(captured_audio)
                                        wav_bytes = buf.getvalue()

                                        # Transcribe via Groq Whisper (<300ms)
                                        try:
                                            transcription, latency = stt_engine.transcribe_sync(wav_bytes)
                                        except Exception as stt_err:
                                            logger.debug(f"[VoiceBridge] STT error: {stt_err}")
                                            transcription = ""

                                        if transcription:
                                            logger.info(f"🎙️ [VoiceBridge] Captured speech: '{transcription}' ({latency:.1f}ms)")
                                            clean_cmd = re.sub(r"^(?:hey\s+|hi\s+|ok\s+)?jarvis[,:\s]*", "", transcription, flags=re.IGNORECASE).strip(" .,!?")
                                            if not clean_cmd:
                                                clean_cmd = "hello jarvis"

                                            if self._window:
                                                safe_text = json.dumps(clean_cmd)
                                                self._window.evaluate_js(f"window.onVoiceTranscriptReceived && window.onVoiceTranscriptReceived({safe_text}, true)")
                    except Exception as stream_e:
                        logger.debug(f"[VoiceBridge] Stream cycle note: {stream_e}")
                        time.sleep(0.05)

                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            except Exception as outer_e:
                logger.error(f"[VoiceBridge] Hardware mic session error: {outer_e}")
            finally:
                p.terminate()

            if self._window:
                try:
                    self._window.evaluate_js("window.onVoiceStatusChanged && window.onVoiceStatusChanged(false)")
                except Exception:
                    pass
            logger.info("🎙️ [VoiceBridge] Microphone loop stopped.")

        self._listen_thread = threading.Thread(target=_mic_worker, daemon=True)
        self._listen_thread.start()
        return {"success": True, "listening": True}

    def stop_voice_listening(self) -> dict:
        """Stops hardware microphone listening."""
        self._is_listening = False
        logger.info("🎙️ [VoiceBridge] Hardware microphone stopped.")
        if self._window:
            try:
                self._window.evaluate_js("window.onVoiceStatusChanged && window.onVoiceStatusChanged(false)")
            except Exception:
                pass
        return {"success": True, "listening": False}

    def transcribe_audio_blob(self, b64_wav: str) -> dict:
        """Transcribes base64-encoded audio WAV blob sent from frontend Web Audio API."""
        try:
            from services.voice.stt_engine import stt_engine
            raw_b64 = b64_wav.split(",", 1)[1] if "," in b64_wav else b64_wav
            audio_bytes = base64.b64decode(raw_b64)
            text, latency = stt_engine.transcribe_sync(audio_bytes)
            clean_cmd = re.sub(r"^(?:hey\s+|hi\s+|ok\s+)?jarvis[,:\s]*", "", text, flags=re.IGNORECASE).strip(" .,!?")
            return {"success": bool(clean_cmd), "text": clean_cmd, "latency_ms": latency}
        except Exception as e:
            logger.error(f"[FloatingApp] transcribe_audio_blob error: {e}")
            return {"success": False, "error": str(e), "text": ""}

    def listen_once(self) -> dict:
        """Single phrase capture directly from hardware microphone."""
        self._init_audio()
        if not self._microphone:
            return {"success": False, "error": "Microphone not available"}

        import speech_recognition as sr
        try:
            with self._microphone as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.4)
                self._recognizer.energy_threshold = max(self._recognizer.energy_threshold, 300.0)
                logger.info(f"🎙️ [VoiceBridge] Single listen ambient threshold: {self._recognizer.energy_threshold:.1f}")
                audio = self._recognizer.listen(source, timeout=4.0, phrase_time_limit=10.0)

                text = ""
                try:
                    from services.voice.stt_engine import stt_engine
                    wav_bytes = audio.get_wav_data()
                    if wav_bytes:
                        t, _ = stt_engine.transcribe_sync(wav_bytes)
                        text = t.strip()
                except Exception as e:
                    logger.debug(f"[VoiceBridge] STT sync notice: {e}")

                if not text:
                    text = self._recognizer.recognize_google(audio, language="en-US").strip()

                clean = re.sub(r"^(?:hey\s+|hi\s+|ok\s+)?jarvis[,:\s]*", "", text, flags=re.IGNORECASE).strip()
                logger.info(f"🎙️ [VoiceBridge] Captured single utterance: '{clean}'")
                return {"success": True, "text": clean}
        except sr.WaitTimeoutError:
            return {"success": False, "error": "Listening timed out"}
        except sr.UnknownValueError:
            return {"success": False, "error": "Could not understand audio"}
        except Exception as e:
            logger.error(f"[VoiceBridge] Single listen error: {e}")
            return {"success": False, "error": str(e)}

    def execute_command(self, query: str) -> dict:
        """
        Executes user command directly through the J.A.R.V.I.S. Conversational Brain:
        - Music streaming (YouTube, Amazon Music, Spotify)
        - Smart web applications (Prime Video, IBM careers, etc.)
        - Desktop application controls (open/close apps, tabs, windows)
        - System operations (volume, screenshots, clipboard diagnostics)
        - Sub-second instantaneous UI text return with asynchronous speech synthesis
        """
        import asyncio
        from services.brain.conversation_engine import conversation_engine
        from services.sensory.soundboard import soundboard
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            matched_clip = soundboard.match_audio_clip(query)
            soundboard_url = matched_clip.get("url") if matched_clip else None

            res = loop.run_until_complete(conversation_engine.process_turn(query))
            response_text = res.get("response", "Instruction processed, sir.")
            actions = res.get("actions_executed", [])

            # If an instantaneous soundboard clip matched, return it (<5ms)
            audio_b64 = ""
            if soundboard_url and matched_clip and matched_clip.get("file_path"):
                clip_path = matched_clip["file_path"]
                if os.path.exists(clip_path):
                    with open(clip_path, "rb") as af:
                        b64 = base64.b64encode(af.read()).decode("utf-8")
                        audio_b64 = f"data:audio/wav;base64,{b64}"

            loop.close()
            # Return immediately so the UI displays text in <300ms; UI synthesizes speech in background
            return {
                "success": True,
                "message": response_text,
                "response": response_text,
                "intent": res.get("intent"),
                "actions_executed": actions,
                "audio_b64": audio_b64,
                "soundboard_url": soundboard_url
            }
        except Exception as e:
            logger.error(f"[FloatingApp] Brain execution error: {e}")
            return {
                "success": False,
                "message": f"Execution error: {str(e)}",
                "response": f"Execution error: {str(e)}",
                "actions_executed": [],
                "audio_b64": ""
            }

    def analyze_screen_vision(self, prompt: str = "Analyze what is on my screen") -> dict:
        """Multimodal Screen Vision bridge using real desktop capture + AI analysis."""
        import asyncio
        from services.sensory.screen_vision import screen_vision
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(screen_vision.analyze_screen_context(prompt))
            loop.close()
            return res
        except Exception as e:
            logger.error(f"[FloatingApp] Screen vision bridge error: {e}")
            return {"success": False, "analysis": f"Screen vision error: {str(e)}"}

    def synthesize_speech(self, text: str) -> dict:
        """Synthesizes Paul Bettany British neural speech using Edge-TTS and returns base64 MP3."""
        import asyncio
        try:
            import edge_tts
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            clean_text = text[:450]
            clean_text = re.sub(r'[*#_~`\[\]]', '', clean_text)
            async def _synth():
                communicate = edge_tts.Communicate(clean_text, "en-GB-RyanNeural", pitch="-2Hz", rate="-2%")
                chunks = []
                async for chunk in communicate.stream():
                    if chunk.get("type") == "audio":
                        chunks.append(chunk["data"])
                return b"".join(chunks)
            audio_bytes = loop.run_until_complete(_synth())
            loop.close()
            if audio_bytes:
                b64 = base64.b64encode(audio_bytes).decode("utf-8")
                return {"success": True, "audio_b64": f"data:audio/mp3;base64,{b64}"}
        except Exception as e:
            logger.debug(f"[FloatingApp] Speech synthesis error: {e}")
        return {"success": False, "audio_b64": ""}

    def analyze_dropped_file(self, filename: str, content_b64: str) -> dict:
        """Processes files dropped onto the 3D Arc Reactor."""
        try:
            raw_bytes = base64.b64decode(content_b64)
            ext = os.path.splitext(filename)[1].lower()

            if ext in [".py", ".js", ".html", ".css", ".json", ".md", ".txt", ".log", ".bat", ".sh", ".yaml", ".yml", ".env"]:
                text_content = raw_bytes.decode("utf-8", errors="replace")
                lines = text_content.splitlines()
                num_lines = len(lines)
                size_kb = round(len(raw_bytes) / 1024, 1)

                analysis = f"Ingested {filename} ({num_lines} lines, {size_kb} KB). Code syntax and parameters locked into active buffer, sir."
                return {
                    "success": True,
                    "filename": filename,
                    "lines": num_lines,
                    "analysis": analysis
                }
            elif ext in [".png", ".jpg", ".jpeg", ".webp"]:
                return {
                    "success": True,
                    "filename": filename,
                    "analysis": f"Visual imagery '{filename}' ingested into Stark sensory buffer. Resolution and telemetry locked, sir."
                }
            else:
                return {
                    "success": True,
                    "filename": filename,
                    "analysis": f"Binary asset '{filename}' ({len(raw_bytes)} bytes) ingested into Stark tactical cache, sir."
                }
        except Exception as e:
            return {"success": False, "filename": filename, "analysis": f"File ingestion notice: {str(e)}"}

    def execute_device_action(self, action: str, params: dict = None) -> dict:
        """Native Windows UI automation bridge for clicks, scrolls, and typing."""
        params = params or {}
        try:
            from services.device_agents.windows.windows_device_agent import windows_agent
            if action == "click":
                return windows_agent.left_click(params.get("x", 0), params.get("y", 0))
            elif action == "type":
                return windows_agent.type_text(params.get("text", ""))
            elif action == "press":
                return windows_agent.press_key(params.get("key", "enter"))
            elif action == "scroll":
                return windows_agent.scroll_page(params.get("direction", "down"), params.get("clicks", 3))
            return {"success": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


def start_global_hotkey_listener(window):
    """
    Background daemon monitoring Alt + J (0x12 + 0x4A) via user32.GetAsyncKeyState.
    Toggles the floating window between foreground active and minimized globally.
    """
    if sys.platform != "win32":
        return

    def _loop():
        user32 = ctypes.windll.user32
        VK_MENU = 0x12  # Alt
        VK_J = 0x4A     # 'J'
        is_hidden = False

        while True:
            try:
                alt_down = bool(user32.GetAsyncKeyState(VK_MENU) & 0x8000)
                j_down = bool(user32.GetAsyncKeyState(VK_J) & 0x8000)

                if alt_down and j_down:
                    logger.info("⚡ [FloatingApp] Global Hotkey Alt+J triggered!")
                    hwnd = user32.FindWindowW(None, "J.A.R.V.I.S. Floating Agent")
                    if is_hidden:
                        if hwnd:
                            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                            user32.SetForegroundWindow(hwnd)
                        try:
                            window.restore()
                        except Exception:
                            pass
                        is_hidden = False
                    else:
                        try:
                            window.minimize()
                        except Exception:
                            if hwnd:
                                user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
                        is_hidden = True

                    time.sleep(0.4)
            except Exception as e:
                logger.debug(f"[FloatingApp] Hotkey check notice: {e}")
            time.sleep(0.05)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    logger.info("⚡ [FloatingApp] Global Alt+J hotkey listener activated.")


def focus_on_start():
    """Brings window to foreground and ensures HWND_TOPMOST once displayed."""
    for _ in range(16):
        time.sleep(0.3)
        if sys.platform == "win32":
            try:
                ensure_interactive_desktop()
                user32 = ctypes.windll.user32
                hwnd = user32.FindWindowW(None, "J.A.R.V.I.S. Floating Agent")
                if hwnd and user32.IsWindowVisible(hwnd):
                    HWND_TOPMOST = ctypes.c_void_p(-1)
                    SWP_NOMOVE = 0x0002
                    SWP_NOSIZE = 0x0001
                    SWP_SHOWWINDOW = 0x0040
                    user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
                    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    logger.info(f"⚡ [FloatingApp] Window pinned TOPMOST and focused (HWND: {hwnd})")
                    break
            except Exception as e:
                logger.debug(f"[FloatingApp] Focus attempt notice: {e}")


def main():
    logger.info("==================================================")
    logger.info("   J.A.R.V.I.S. COMPUTER AGENT COMMAND CENTER")
    logger.info("   Full-Screen Solid HUD (Zero Transparency)")
    logger.info("==================================================")

    # 1. Bind to active user desktop
    ensure_interactive_desktop()

    # 2. Isolate WebView2 profile with unique directory to prevent 0x800700AA resource locked error
    import tempfile
    profile_dir = os.path.join(tempfile.gettempdir(), f"jarvis_hud_{os.getpid()}")
    os.makedirs(profile_dir, exist_ok=True)
    os.environ["WEBVIEW2_USER_DATA_FOLDER"] = profile_dir
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--use-fake-ui-for-media-stream --disable-features=msSmartScreenProtection"

    # 4. Compact Floating Window Geometry (NOT full screen)
    user32 = ctypes.windll.user32 if sys.platform == "win32" else None
    screen_w = user32.GetSystemMetrics(0) if user32 else 1536
    screen_h = user32.GetSystemMetrics(1) if user32 else 864

    win_w = 420
    win_h = 560
    win_x = max(20, screen_w - win_w - 30)
    win_y = max(20, screen_h - win_h - 60)

    logger.info(f"📍 [FloatingApp] Opening compact floating agent: {win_w}x{win_h} at ({win_x}, {win_y})")

    try:
        import webview
        api = FloatingAgentAPI()
        target_url = get_target_url()

        window = webview.create_window(
            title="J.A.R.V.I.S. Floating Agent",
            url=target_url,
            width=win_w,
            height=win_h,
            x=win_x,
            y=win_y,
            frameless=True,
            fullscreen=False,
            on_top=True,
            resizable=True,
            transparent=False,
            background_color="#060e1c",
            js_api=api
        )
        api.bind_window(window)
        start_global_hotkey_listener(window)

        threading.Thread(target=focus_on_start, daemon=True).start()
        # Automatically launch hardware streaming voice capture immediately
        threading.Thread(target=api.start_voice_listening, daemon=True).start()

        logger.info(f"⚡ [FloatingApp] Spawning compact floating J.A.R.V.I.S. agent from {target_url}...")
        webview.start()

    except Exception as e:
        logger.error(f"[FloatingApp] Desktop agent error: {e}")
        import traceback
        with open(r"d:\Project J.A.R.V.I.S\services\sensory\screenshots\floating_app_error.log", "w") as f:
            traceback.print_exc(file=f)
        try:
            from agents.computer.windows_agent import windows_agent
            windows_agent.open_url(get_target_url())
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        with open(r"d:\Project J.A.R.V.I.S\services\sensory\screenshots\floating_app_error.log", "w") as f:
            traceback.print_exc(file=f)
