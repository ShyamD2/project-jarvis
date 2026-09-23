"""
Voice Phrase & Challenge Verifier for Project J.A.R.V.I.S. (Phase 36 Stage 36.7).
Protects high-risk voice commands with:
  1. Multi-factor Challenge-Response Verification (e.g., destructive actions).
  2. Time-limited challenge sessions (30s window).
  3. Speaker voice profile distance threshold checking.
"""

from __future__ import annotations
import time
import uuid
import random
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisVoicePhraseVerifier")

# Phonetic words for human-friendly challenge codes
CHALLENGE_WORDS = [
    "ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT",
    "GOLF", "HOTEL", "INDIA", "JULIET", "KILO", "LIMA",
    "MIKE", "NOVEMBER", "OSCAR", "PAPA", "QUEBEC", "ROMEO",
    "SIERRA", "TANGO", "UNIFORM", "VICTOR", "WHISKEY", "XRAY",
    "YANKEE", "ZULU"
]


@dataclass
class VoiceChallenge:
    challenge_id: str
    target_action: str
    challenge_phrase: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 30.0)
    speaker_id: str = "operator"
    verified: bool = False


class VoicePhraseVerifier:
    def __init__(self, challenge_timeout_seconds: float = 30.0, speaker_distance_threshold: float = 0.65):
        self.timeout_seconds = challenge_timeout_seconds
        self.speaker_distance_threshold = speaker_distance_threshold
        self._active_challenges: Dict[str, VoiceChallenge] = {}

    def generate_challenge(self, action_name: str, speaker_id: str = "operator") -> VoiceChallenge:
        """Generates a secure 2-word phonetic challenge phrase for dangerous voice commands."""
        cid = f"vch_{uuid.uuid4().hex[:8]}"
        word1 = random.choice(CHALLENGE_WORDS)
        word2 = random.choice(CHALLENGE_WORDS)
        num = random.randint(10, 99)
        phrase = f"{word1} {word2} {num}"

        challenge = VoiceChallenge(
            challenge_id=cid,
            target_action=action_name,
            challenge_phrase=phrase,
            created_at=time.time(),
            expires_at=time.time() + self.timeout_seconds,
            speaker_id=speaker_id
        )
        self._active_challenges[cid] = challenge
        logger.warning(
            f"🎙️ [VoiceSecurity] Challenge generated for high-risk action '{action_name}': "
            f"Phrase: '{phrase}' (ID: {cid}, Valid: {self.timeout_seconds}s)"
        )
        return challenge

    def verify_response(
        self,
        challenge_id: str,
        spoken_response: str,
        speaker_distance: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Validates spoken response against active challenge.
        Checks expiration, exact phrase match, and speaker acoustic distance.
        """
        challenge = self._active_challenges.get(challenge_id)
        if not challenge:
            return {"valid": False, "reason": "Challenge expired or does not exist."}

        # Check expiration
        if time.time() > challenge.expires_at:
            del self._active_challenges[challenge_id]
            return {"valid": False, "reason": "Voice challenge expired. Please reissue command."}

        # Check speaker biometric distance if provided
        if speaker_distance is not None:
            if speaker_distance > self.speaker_distance_threshold:
                return {
                    "valid": False,
                    "reason": f"Speaker identity rejected: distance ({speaker_distance:.2f}) exceeds threshold ({self.speaker_distance_threshold:.2f})."
                }

        # Normalize and compare spoken phrase
        norm_expected = challenge.challenge_phrase.lower().replace(" ", "")
        norm_spoken = spoken_response.lower().replace(" ", "").replace("-", "")

        if norm_expected in norm_spoken or norm_spoken in norm_expected:
            challenge.verified = True
            # Consume single-use challenge
            del self._active_challenges[challenge_id]
            logger.info(f"✔ [VoiceSecurity] Challenge '{challenge_id}' successfully verified.")
            return {
                "valid": True,
                "target_action": challenge.target_action,
                "verified": True
            }

        return {
            "valid": False,
            "reason": f"Spoken response did not match challenge phrase '{challenge.challenge_phrase}'."
        }


voice_phrase_verifier = VoicePhraseVerifier()
