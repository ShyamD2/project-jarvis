"""
Global configuration loader for J.A.R.V.I.S. modules.
Reads environment variables with intelligent local/cloud defaults.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Automatically load .env if present
load_dotenv()


@dataclass
class JarvisConfig:
    env: str = os.getenv("JARVIS_ENV", "local")
    log_level: str = os.getenv("JARVIS_LOG_LEVEL", "INFO")
    host: str = os.getenv("JARVIS_HOST", "127.0.0.1")
    port: int = int(os.getenv("JARVIS_PORT", "8000"))

    # Local Fast-Path MQTT
    mqtt_broker: str = os.getenv("LOCAL_MQTT_BROKER", "127.0.0.1")
    mqtt_port: int = int(os.getenv("LOCAL_MQTT_PORT", "1883"))
    mqtt_user: str = os.getenv("LOCAL_MQTT_USER", "")
    mqtt_password: str = os.getenv("LOCAL_MQTT_PASSWORD", "")

    # AWS Settings
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    use_localstack: bool = os.getenv("USE_LOCALSTACK", "true").lower() == "true"
    localstack_endpoint: str = os.getenv("LOCALSTACK_ENDPOINT", "http://127.0.0.1:4566")
    event_bus_name: str = os.getenv("AWS_EVENT_BUS_NAME", "jarvis-event-bus")

    # Redis Cache
    redis_url: str = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

    # Safety & Blast Radius
    emergency_stand_down: bool = os.getenv("EMERGENCY_STAND_DOWN", "false").lower() == "true"
    master_secret: str = ""

    # Voice & Real-Time Conversation Settings
    voice_provider: str = os.getenv("VOICE_PROVIDER", "edge_tts")
    voice_id: str = os.getenv("VOICE_ID", "en-GB-RyanNeural")
    stt_provider: str = os.getenv("STT_PROVIDER", "groq_whisper")
    llm_provider: str = os.getenv("LLM_PROVIDER", "openrouter")
    llm_model: str = os.getenv("LLM_MODEL", "meta-llama/llama-3.3-70b-instruct")
    wake_word: str = os.getenv("WAKE_WORD", "jarvis")
    tts_speed: str = os.getenv("TTS_SPEED", "-2%")
    tts_pitch: str = os.getenv("TTS_PITCH", "-2Hz")
    tts_volume: str = os.getenv("TTS_VOLUME", "+0%")
    vad_threshold: float = float(os.getenv("VAD_THRESHOLD", "0.020"))
    silence_timeout: float = float(os.getenv("SILENCE_TIMEOUT", "1.4"))
    max_context_messages: int = int(os.getenv("MAX_CONTEXT_MESSAGES", "15"))
    interruption_enabled: bool = os.getenv("INTERRUPTION_ENABLED", "true").lower() == "true"
    streaming_enabled: bool = os.getenv("STREAMING_ENABLED", "true").lower() == "true"

    def __post_init__(self):
        secret = os.getenv("JARVIS_MASTER_SECRET", "").strip()
        if not secret:
            raise ValueError(
                "FATAL: JARVIS_MASTER_SECRET is required but unset or empty in the environment. "
                "Please configure JARVIS_MASTER_SECRET in your .env file."
            )
        self.master_secret = secret


# Global singleton instance
config = JarvisConfig()

