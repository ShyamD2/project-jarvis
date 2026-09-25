"""
Sensory Audio Processing Router for J.A.R.V.I.S. Core.
Accepts client audio recordings, performs speech-to-text, and returns transcriptions.
Includes audio gain normalization, silence rejection, Groq Whisper prompt tuning, and hallucination filtering.
"""

from fastapi import APIRouter, UploadFile, File, Request, HTTPException
import io
import os
import sys
import re
from typing import Dict, Any
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisSensoryAPI")
router = APIRouter(prefix="/api/v1/sensory", tags=["Sensory"])

try:
    import speech_recognition as sr
    RECOGNIZER = sr.Recognizer()
except ImportError:
    RECOGNIZER = None

try:
    import soundfile as sf
    import numpy as np
except ImportError:
    sf = None
    np = None

sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/brain"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/voice"))
from services.brain.ml_operator_learner import ml_learner
from services.voice.stt_engine import stt_engine
from services.voice.wake_word import wake_word_detector
from services.voice.voice_session import voice_session, VoiceState

WHISPER_HALLUCINATIONS = {
    "you", "you.", "you!", "you?", "thank you", "thank you.", "thank you!",
    "thanks", "thanks.", "thanks!", "bye", "bye.", "bye bye", "goodbye",
    "subtitles", "subtitles by", "subscribe", "amara.org", "watching",
    "thank you for watching", "thank you for watching.", "the end", "end.",
    "um", "uh", "oh", "ah", "okay", "ok", "so", "yeah", "yes", "no",
    "silence", "blank audio", "applause", "laughter", "music", "bell ring",
    "muffled", "inaudible", "cough", "clears throat"
}

WHISPER_PROMPT = (
    "J.A.R.V.I.S., computer. English voice instructions: volume up, volume down, set volume to 50%, "
    "mute audio, unmute, play music, pause, next track, shut down computer, restart PC, lock screen, "
    "what is my CPU usage, check RAM, free disk space, battery status, network IP address, "
    "open Opera browser, open calculator, close active tab, show bookmarks, send WhatsApp message, "
    "check messages, take a note, add task, Docker containers, AWS status, Kubernetes pods."
)


try:
    import python_multipart
    MULTIPART_AVAILABLE = True
except ImportError:
    try:
        from multipart.multipart import parse_options_header
        MULTIPART_AVAILABLE = True
    except ImportError:
        MULTIPART_AVAILABLE = False


async def _transcribe_impl(audio_bytes: bytes) -> Dict[str, Any]:
    """
    Transcribes audio recording (WAV) from raw bytes into text.
    Applies audio energy filtering, gain normalization, and Groq Whisper with zero temperature.
    """
    try:
        if not audio_bytes or len(audio_bytes) < 300:
            return {"status": "error", "message": "Audio stream too short or empty", "transcript": ""}

        # 0. Audio Preprocessing: Silence detection & Automatic Gain Control (AGC)
        if sf and np:
            try:
                buf = io.BytesIO(audio_bytes)
                audio_arr, sr_rate = sf.read(buf)
                if len(audio_arr.shape) > 1:
                    audio_arr = np.mean(audio_arr, axis=1)

                rms = float(np.sqrt(np.mean(audio_arr**2)))
                max_val = float(np.max(np.abs(audio_arr)))

                # If sound is just background mic hiss or silence, reject immediately
                if rms < 0.005 or max_val < 0.015:
                    logger.debug(f"🎤 [Sensory] Audio discarded: Silence/Hiss (RMS: {rms:.4f}, Peak: {max_val:.4f})")
                    return {"status": "error", "transcript": "", "message": "Silence / ambient noise discarded"}

                # Amplify quiet speech so Whisper hears loud, crisp phonemes
                if max_val < 0.80:
                    gain = min(10.0, 0.90 / max(max_val, 0.01))
                    audio_arr = audio_arr * gain
                    clean_wav = io.BytesIO()
                    sf.write(clean_wav, audio_arr, sr_rate, format='WAV', subtype='PCM_16')
                    clean_wav.seek(0)
                    audio_bytes = clean_wav.read()
                    logger.debug(f"🎤 [Sensory] Normalized audio gain: {gain:.2f}x (New Peak: {float(np.max(np.abs(audio_arr))):.2f})")
            except Exception as e_prep:
                logger.debug(f"Audio preprocessing notice: {e_prep}")

        # 1. Ultra-Fast Cloud Whisper STT via Groq (150-300ms latency)
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        if groq_key and not groq_key.startswith("PASTE_"):
            try:
                import httpx
                files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
                data = {
                    "model": "whisper-large-v3",
                    "temperature": "0.0",
                    "language": "en",
                    "prompt": WHISPER_PROMPT
                }
                headers = {"Authorization": f"Bearer {groq_key}"}
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        files=files,
                        data=data,
                        headers=headers
                    )
                    if resp.status_code == 200:
                        res_json = resp.json()
                        text = res_json.get("text", "").strip()

                        # Strip bracketed/parenthesized noise descriptions e.g. [BLANK_AUDIO], (muffled sounds)
                        cleaned_text = re.sub(r"\[.*?\]|\(.*?\)", "", text).strip()
                        clean_lower = cleaned_text.lower().strip().rstrip(".,!?")

                        # Hallucination filter
                        if not clean_lower or clean_lower in WHISPER_HALLUCINATIONS or len(clean_lower) <= 2:
                            logger.info(f"🎤 [Sensory: Whisper] Discarded noise artifact/hallucination: '{text}'")
                            return {"status": "error", "transcript": "", "message": "Noise artifact filtered"}

                        if cleaned_text:
                            normalized_text = stt_engine.normalize_multilingual(cleaned_text)
                            wake_triggered, clean_instruction = wake_word_detector.extract_instruction(normalized_text)
                            voice_session.transition_to(VoiceState.LISTENING, {"transcript": normalized_text})

                            is_complete, conf, reason = ml_learner.is_sentence_complete(normalized_text)
                            logger.info(f"🎤 [Sensory: Groq Whisper] Transcribed voice: '{normalized_text}' (Raw: '{cleaned_text}', Complete: {is_complete})")
                            return {
                                "status": "success",
                                "transcript": normalized_text,
                                "raw_transcript": cleaned_text,
                                "clean_instruction": clean_instruction,
                                "wake_triggered": wake_triggered,
                                "engine": "groq_whisper",
                                "is_complete": is_complete,
                                "completeness_confidence": conf,
                                "completeness_reason": reason
                            }
            except Exception as e_groq:
                logger.warning(f"Groq Whisper transcription notice: {e_groq}, falling back to SpeechRecognition.")

        # 2. Local SpeechRecognition / Google STT Fallback
        if RECOGNIZER:
            buf = io.BytesIO(audio_bytes)
            try:
                with sr.AudioFile(buf) as source:
                    audio_data = RECOGNIZER.record(source)
            except Exception as read_err:
                if sf:
                    buf.seek(0)
                    data, samplerate = sf.read(buf)
                    wav_io = io.BytesIO()
                    sf.write(wav_io, data, samplerate, format='WAV', subtype='PCM_16')
                    wav_io.seek(0)
                    with sr.AudioFile(wav_io) as source:
                        audio_data = RECOGNIZER.record(source)
                else:
                    return {"status": "error", "transcript": "", "message": str(read_err)}

            try:
                try:
                    transcript = RECOGNIZER.recognize_google(audio_data, language="en-US")
                except sr.UnknownValueError:
                    transcript = RECOGNIZER.recognize_google(audio_data, language="en-GB")

                clean_lower = transcript.lower().strip()
                if clean_lower not in WHISPER_HALLUCINATIONS and len(clean_lower) > 2:
                    normalized_text = stt_engine.normalize_multilingual(transcript)
                    wake_triggered, clean_instruction = wake_word_detector.extract_instruction(normalized_text)
                    voice_session.transition_to(VoiceState.LISTENING, {"transcript": normalized_text})

                    is_complete, conf, reason = ml_learner.is_sentence_complete(normalized_text)
                    logger.info(f"🎤 [Sensory: Google STT] Transcribed user voice: '{normalized_text}' (Complete: {is_complete})")
                    return {
                        "status": "success",
                        "transcript": normalized_text,
                        "raw_transcript": transcript,
                        "clean_instruction": clean_instruction,
                        "wake_triggered": wake_triggered,
                        "engine": "google_stt",
                        "is_complete": is_complete,
                        "completeness_confidence": conf,
                        "completeness_reason": reason
                    }
            except Exception as e_sr:
                logger.debug(f"Google STT notice: {e_sr}")

        return {"status": "error", "transcript": "", "message": "Speech unintelligible or noise"}

    except Exception as e:
        logger.error(f"Transcribe error: {e}")
        return {"status": "error", "message": str(e), "transcript": ""}


if MULTIPART_AVAILABLE:
    @router.post("/transcribe")
    async def transcribe_audio(request: Request, file: UploadFile = File(None)):
        """
        Transcribes audio recording (WAV) from browser microphone into text.
        Accepts multipart file upload or direct binary body.
        """
        if file:
            audio_bytes = await file.read()
        else:
            audio_bytes = await request.body()
        return await _transcribe_impl(audio_bytes)
else:
    @router.post("/transcribe")
    async def transcribe_audio(request: Request):
        """
        Transcribes audio recording (WAV) from raw body when python-multipart is absent.
        """
        audio_bytes = await request.body()
        return await _transcribe_impl(audio_bytes)


@router.post("/interrupt")
async def interrupt_sensory_audio():
    """
    Halts all active sensory recitation and audio playback immediately.
    """
    from services.voice.interrupt_service import interrupt_service
    res = interrupt_service.interrupt(source="sensory_api", reason="user_barge_in")
    return {"status": "success", "interrupted": True, "detail": res}

