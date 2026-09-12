"""
Sensory Audio Processing Router for J.A.R.V.I.S. Core.
Accepts client audio recordings, performs speech-to-text, and returns transcriptions.
"""

from fastapi import APIRouter, UploadFile, File, Request, HTTPException
import io
import os
from typing import Dict, Any

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisSensoryAPI")
router = APIRouter(prefix="/api/v1/sensory", tags=["Sensory"])

try:
    import speech_recognition as sr
    RECOGNIZER = sr.Recognizer()
except ImportError:
    RECOGNIZER = None


@router.post("/transcribe")
async def transcribe_audio(request: Request, file: UploadFile = File(None)):
    """
    Transcribes audio recording (WAV) from browser microphone into text.
    Works seamlessly with Opera, Chrome, Edge, and mobile browsers.
    """
    if not RECOGNIZER:
        raise HTTPException(status_code=500, detail="SpeechRecognition module not available")

    try:
        if file:
            audio_bytes = await file.read()
        else:
            audio_bytes = await request.body()

        if not audio_bytes or len(audio_bytes) < 100:
            return {"status": "error", "message": "Audio stream too short or empty", "transcript": ""}

        buf = io.BytesIO(audio_bytes)

        with sr.AudioFile(buf) as source:
            audio_data = RECOGNIZER.record(source)

        try:
            try:
                transcript = RECOGNIZER.recognize_google(audio_data, language="en-IN")
            except sr.UnknownValueError:
                transcript = RECOGNIZER.recognize_google(audio_data, language="en-US")

            logger.info(f"🎤 [Sensory STT] Transcribed user voice: '{transcript}'")
            return {
                "status": "success",
                "transcript": transcript
            }
        except sr.UnknownValueError:
            logger.info("🎤 [Sensory STT] Audio was unintelligible")
            return {
                "status": "unintelligible",
                "transcript": "",
                "message": "Speech was not clear, sir."
            }
        except sr.RequestError as re:
            logger.warning(f"🎤 [Sensory STT] STT service request error: {re}")
            return {
                "status": "service_unavailable",
                "transcript": "",
                "message": str(re)
            }
    except Exception as e:
        logger.error(f"Failed to process audio transcription: {e}")
        return {
            "status": "error",
            "transcript": "",
            "message": str(e)
        }
