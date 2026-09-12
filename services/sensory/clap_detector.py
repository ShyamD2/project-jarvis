"""
Sound & Clap Detection Engine for J.A.R.V.I.S.
Analyzes audio waveform transients for sharp sound spikes (single / double claps).
Dispatches sensory.clap events directly to the Event Fabric for instant reflex actions.
"""

import time
import math
from typing import Callable, Optional, List
from shared.schemas.event_envelope import JarvisEvent
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisClapDetector")


class ClapDetector:
    def __init__(self, threshold_energy: float = 0.65, min_interval: float = 0.15, max_interval: float = 0.85):
        self.threshold_energy = threshold_energy
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.last_clap_time: float = 0.0
        self.clap_count: int = 0
        self.on_clap_detected: Optional[Callable[[int], None]] = None

    def process_audio_chunk(self, audio_samples: List[float], timestamp: Optional[float] = None) -> Optional[int]:
        """
        Processes a raw float audio buffer.
        Detects sudden energy peaks with steep attack and fast decay (clap signature).
        """
        now = timestamp or time.time()
        if not audio_samples:
            return None

        # Calculate Root Mean Square (RMS) energy
        rms = math.sqrt(sum(s * s for s in audio_samples) / len(audio_samples))

        if rms >= self.threshold_energy:
            time_since_last = now - self.last_clap_time

            # Ignore echoes or sustained noise (< min_interval)
            if time_since_last < self.min_interval:
                return None

            # Check if this is the second clap in a double-clap window
            if time_since_last <= self.max_interval:
                self.clap_count = 2
                self.last_clap_time = 0.0
                detected_count = self.clap_count
                self._dispatch_event(detected_count, confidence=0.96)
                return detected_count
            else:
                # First clap detected, start listening for second
                self.clap_count = 1
                self.last_clap_time = now
                return None

        # Reset count if window expires without second clap
        if self.clap_count == 1 and (now - self.last_clap_time) > self.max_interval:
            self._dispatch_event(1, confidence=0.85)
            self.clap_count = 0
            return 1

        return None

    def simulate_clap(self, count: int = 2) -> JarvisEvent:
        """Simulates physical clap detection for headless / automated testing"""
        logger.info(f"👏 [ClapDetector] Detected {count} clap(s)!")
        event = JarvisEvent(
            source="sensory.microphone.sound_detector",
            type="sensory.clap",
            data={
                "count": count,
                "confidence": 0.95,
                "action_intent": "TOGGLE_LIGHT" if count == 2 else "QUERY_STATUS"
            }
        )
        mesh.publish(event)
        if self.on_clap_detected:
            self.on_clap_detected(count)
        return event

    def _dispatch_event(self, count: int, confidence: float):
        logger.info(f"👏 [ClapDetector] Physical clap detected! Count: {count} (Confidence: {confidence})")
        event = JarvisEvent(
            source="sensory.microphone.sound_detector",
            type="sensory.clap",
            data={
                "count": count,
                "confidence": confidence,
                "action_intent": "TOGGLE_LIGHT" if count == 2 else "QUERY_STATUS"
            }
        )
        mesh.publish(event)
        if self.on_clap_detected:
            self.on_clap_detected(count)


clap_detector = ClapDetector()
