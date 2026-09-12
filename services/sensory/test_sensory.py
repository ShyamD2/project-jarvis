"""
Integration tests for J.A.R.V.I.S. Sensory Layer (Voice, Wake Word, Clap, and Voice Response).
"""

import sys
import os
import unittest
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from clap_detector import ClapDetector
from voice_listener import VoiceListener
from voice_synthesizer import VoiceSynthesizer


class TestJarvisSensory(unittest.IsolatedAsyncioTestCase):
    def test_clap_detection_peaks(self):
        detector = ClapDetector(threshold_energy=0.5, min_interval=0.1, max_interval=0.8)
        loud_samples = [0.9] * 100
        quiet_samples = [0.01] * 100

        # First clap
        r1 = detector.process_audio_chunk(loud_samples, timestamp=1.0)
        self.assertIsNone(r1) # Waiting for potential second clap

        # Quiet in between
        detector.process_audio_chunk(quiet_samples, timestamp=1.2)

        # Second clap at t=1.35 (within 0.8s window)
        r2 = detector.process_audio_chunk(loud_samples, timestamp=1.35)
        self.assertEqual(r2, 2) # Double clap detected!

    def test_voice_listener_wake_word(self):
        listener = VoiceListener()

        # Without wake word -> ignored
        ev_none = listener.process_transcript("good morning world")
        self.assertIsNone(ev_none)

        # With wake word -> event emitted with cleaned instruction
        ev = listener.process_transcript("Hey Jarvis, check server status")
        self.assertIsNotNone(ev)
        self.assertEqual(ev.type, "sensory.voice_transcript")
        self.assertEqual(ev.data["cleaned_instruction"], "check server status")

    async def test_voice_synthesizer_barge_in(self):
        synth = VoiceSynthesizer()
        # Trigger speak
        await synth.speak("Greetings sir, all systems are operational.", play_audio=False)
        self.assertTrue(synth.is_speaking)

        # Barge-in should cancel speech immediately
        synth.interrupt()
        self.assertFalse(synth.is_speaking)

    def test_soundboard_matches(self):
        from soundboard import soundboard
        # Greetings match welcome_back
        wb = soundboard.match_audio_clip("JARVIS, wake up")
        self.assertIsNotNone(wb)
        self.assertEqual(wb["clip_name"], "welcome_back")

        # Diagnostics match simulation
        sim = soundboard.match_audio_clip("JARVIS, status report")
        self.assertIsNotNone(sim)
        self.assertEqual(sim["clip_name"], "simulation")

        # Workspace match flight_plan
        fp = soundboard.match_audio_clip("JARVIS, prepare my workspace")
        self.assertIsNotNone(fp)
        self.assertEqual(fp["clip_name"], "flight_plan")

        # Stand down match alarm
        al = soundboard.match_audio_clip("JARVIS, emergency abort")
        self.assertIsNotNone(al)
        self.assertEqual(al["clip_name"], "alarm")


if __name__ == "__main__":
    unittest.main()
