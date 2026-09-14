"""
Wake-Word and Activation Detector for Project J.A.R.V.I.S.
Handles wake-word spotting ("Jarvis", "Hey Jarvis", "Computer"),
instruction prefix sanitization, and continuous conversational hold windows.
"""

from __future__ import annotations
import re
import time
from typing import Tuple, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.config import config

logger = get_logger("JarvisWakeWord")


class WakeWordDetector:
    DEFAULT_WAKE_WORDS = ["jarvis", "hey jarvis", "hi jarvis", "ok jarvis", "okay jarvis", "computer"]

    def __init__(self, wake_words: Optional[List[str]] = None, hold_timeout: float = 8.0):
        self.wake_words = [w.lower().strip() for w in (wake_words or self.DEFAULT_WAKE_WORDS)]
        primary = getattr(config, "wake_word", "jarvis").lower().strip()
        if primary and primary not in self.wake_words:
            self.wake_words.insert(0, primary)

        self.hold_timeout = hold_timeout
        self._last_active_time: float = 0.0
        self._followup_active: bool = False

    def is_wake_word_triggered(self, transcript: str) -> bool:
        """
        Returns True if transcript starts with or contains any configured wake-word,
        OR if the session is currently within an active conversational follow-up window.
        """
        if not transcript or not transcript.strip():
            return False

        if self.is_in_followup_window():
            return True

        norm = transcript.lower().strip()
        for w in self.wake_words:
            pattern = rf"(^|\b){re.escape(w)}(\b|[,\.!\?])"
            if re.search(pattern, norm):
                return True
        return False

    def extract_instruction(self, transcript: str) -> Tuple[bool, str]:
        """
        Checks if wake word is present or follow-up window is active.
        Returns:
            (activated: bool, clean_instruction: str)
        """
        if not transcript or not transcript.strip():
            return False, ""

        norm = transcript.strip()
        lower_norm = norm.lower()

        in_followup = self.is_in_followup_window()

        for w in self.wake_words:
            pattern = rf"^(?:hey\s+|hi\s+|ok\s+|okay\s+)?{re.escape(w)}[,\s\.\!\?\-:]*"
            match = re.match(pattern, lower_norm, flags=re.IGNORECASE)
            if match:
                end_pos = match.end()
                clean = norm[end_pos:].strip()
                clean = re.sub(r"^(?:please\s+|could\s+you\s+|can\s+you\s+)", "", clean, flags=re.IGNORECASE).strip()
                self.start_followup_window()
                return True, clean or norm

        if in_followup:
            clean = re.sub(r"^(?:please\s+|could\s+you\s+|can\s+you\s+)", "", norm, flags=re.IGNORECASE).strip()
            self.start_followup_window()
            return True, clean

        return False, norm

    def start_followup_window(self, duration: Optional[float] = None):
        """Extends or starts continuous conversational follow-up window."""
        timeout = duration if duration is not None else self.hold_timeout
        self._last_active_time = time.time() + timeout
        self._followup_active = True
        logger.debug(f"[WakeWord] Follow-up window active for {timeout}s")

    def is_in_followup_window(self) -> bool:
        """Checks if the conversational follow-up window is currently active."""
        if not self._followup_active:
            return False
        if time.time() <= self._last_active_time:
            return True
        self._followup_active = False
        return False

    def cancel_followup_window(self):
        """Immediately closes follow-up window (e.g. on stand-down or error)."""
        self._followup_active = False
        self._last_active_time = 0.0


wake_word_detector = WakeWordDetector()
