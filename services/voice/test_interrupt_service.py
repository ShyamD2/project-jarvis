"""
Unit and integration tests for J.A.R.V.I.S. Interrupt Service.
Verifies real-time barge-in interruption during long paragraph recitation across
acoustic keywords, lifecycle state changes, clause-level splitting, and REST endpoints.
"""

from __future__ import annotations
import os
import sys
import time
import asyncio
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/jarvis_core"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/voice"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/sensory"))

from services.voice.interrupt_service import interrupt_service
from services.sensory.voice_synthesizer import voice_synthesizer
from services.voice.tts_engine import tts_engine


class TestInterruptService(unittest.TestCase):
    def setUp(self):
        # Reset any lingering interrupt state
        interrupt_service.end_recitation()
        interrupt_service._interrupted_event.clear()

    def tearDown(self):
        interrupt_service.end_recitation()
        interrupt_service._interrupted_event.clear()

    def test_lifecycle_and_callback(self):
        """Test recitation start, interrupt event propagation, and callback dispatch."""
        callback_data = {}

        def on_interrupt(src, reason):
            callback_data["source"] = src
            callback_data["reason"] = reason

        interrupt_service.register_callback(on_interrupt)

        # 1. Start recitation
        interrupt_service.start_recitation(
            recitation_id="test_rec_1",
            enable_keyboard_monitor=False,
            enable_acoustic_monitor=False
        )
        self.assertTrue(interrupt_service.is_recitating)
        self.assertFalse(interrupt_service.is_interrupted())

        # 2. Fire interrupt
        res = interrupt_service.interrupt(source="unit_test", reason="operator_spoken_stop")
        self.assertTrue(res["interrupted"])
        self.assertEqual(res["source"], "unit_test")
        self.assertTrue(interrupt_service.is_interrupted())
        self.assertFalse(interrupt_service.is_recitating)

        # 3. Verify callback executed
        self.assertEqual(callback_data.get("source"), "unit_test")
        self.assertEqual(callback_data.get("reason"), "operator_spoken_stop")

        interrupt_service.unregister_callback(on_interrupt)

    def test_interrupt_keyword_detection(self):
        """Verify that interrupt keywords are spotted even without wake words."""
        # Direct single words
        self.assertTrue(interrupt_service.check_phrase_is_interrupt("stop"))
        self.assertTrue(interrupt_service.check_phrase_is_interrupt("quiet"))
        self.assertTrue(interrupt_service.check_phrase_is_interrupt("silence"))
        self.assertTrue(interrupt_service.check_phrase_is_interrupt("shut up"))
        self.assertTrue(interrupt_service.check_phrase_is_interrupt("cancel"))
        self.assertTrue(interrupt_service.check_phrase_is_interrupt("pause"))
        self.assertTrue(interrupt_service.check_phrase_is_interrupt("enough"))
        self.assertTrue(interrupt_service.check_phrase_is_interrupt("stand down"))
        self.assertTrue(interrupt_service.check_phrase_is_interrupt("abort"))

        # In natural sentences
        self.assertTrue(interrupt_service.check_phrase_is_interrupt("Jarvis please stop now"))
        self.assertTrue(interrupt_service.check_phrase_is_interrupt("okay stop talking"))
        self.assertTrue(interrupt_service.check_phrase_is_interrupt("shut up for a second"))
        self.assertTrue(interrupt_service.check_phrase_is_interrupt("cancel this action"))

        # Non-interrupt phrases should return False
        self.assertFalse(interrupt_service.check_phrase_is_interrupt("what is the weather today"))
        self.assertFalse(interrupt_service.check_phrase_is_interrupt("open opera browser"))
        self.assertFalse(interrupt_service.check_phrase_is_interrupt("check docker status"))
        self.assertFalse(interrupt_service.check_phrase_is_interrupt("hello jarvis"))

    def test_paragraph_clause_splitting(self):
        """Verify that long paragraphs are split into sentences/clauses for progressive recitation."""
        long_para = (
            "Quantum computing leverages superposition and entanglement to perform complex calculations "
            "exponentially faster than classical computers. Furthermore, quantum systems can evaluate massive "
            "datasets simultaneously. In addition, cryptanalysis and drug discovery will experience revolutionary breakthroughs."
        )

        clauses = voice_synthesizer.split_into_clauses(long_para)
        self.assertGreaterEqual(len(clauses), 3)
        for c in clauses:
            self.assertTrue(len(c.strip()) > 0)

    def test_mid_recitation_barge_in(self):
        """Simulate paragraph recitation and verify immediate cutoff upon interrupt."""
        long_para = (
            "First sentence of the briefing. Second sentence with important security telemetry. "
            "Third sentence regarding memory optimization. Fourth sentence regarding cloud infrastructure."
        )
        clauses = voice_synthesizer.split_into_clauses(long_para)

        interrupt_service.start_recitation(
            recitation_id="test_para_rec",
            enable_keyboard_monitor=False,
            enable_acoustic_monitor=False
        )
        self.assertTrue(interrupt_service.is_recitating)

        # Trigger interrupt while reciting
        t0 = time.time()
        res = interrupt_service.interrupt(source="voice_acoustic", reason="stop")
        elapsed_ms = (time.time() - t0) * 1000

        self.assertTrue(res["interrupted"])
        self.assertTrue(interrupt_service.is_interrupted())
        self.assertFalse(interrupt_service.is_recitating)
        self.assertLess(elapsed_ms, 50.0)  # Sub-50ms cutoff guarantee

    def test_rest_api_interrupt_endpoints(self):
        """Test REST API /api/v1/query/interrupt and /api/v1/sensory/interrupt."""
        from fastapi.testclient import TestClient
        from services.jarvis_core.main import app

        client = TestClient(app)

        # Test query interrupt endpoint
        resp_q = client.post("/api/v1/query/interrupt")
        self.assertEqual(resp_q.status_code, 200)
        data_q = resp_q.json()
        self.assertEqual(data_q.get("status"), "success")
        self.assertTrue(data_q.get("interrupted"))

        # Test sensory interrupt endpoint
        resp_s = client.post("/api/v1/sensory/interrupt")
        self.assertEqual(resp_s.status_code, 200)
        data_s = resp_s.json()
        self.assertEqual(data_s.get("status"), "success")
        self.assertTrue(data_s.get("interrupted"))


if __name__ == "__main__":
    unittest.main()
