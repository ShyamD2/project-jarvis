"""
Unit Test Suite for Voice, Device, IoT & Browser Intelligence (Phase 36 Stage 36.7).
Verifies:
  1. Multi-factor voice challenge verification and speaker distance threshold checking.
  2. Browser security guard URL validation, SSRF blocking, and sensitive payment form detection (Item 119).
  3. IoT MQTT offline message buffering and FIFO reconnect draining.
"""

import unittest
import time
from services.voice.phrase_verifier import voice_phrase_verifier
from agents.computer.browser_guard import browser_guard
from services.iot_agent.mqtt_buffer import mqtt_buffer


class TestPhase36VoiceDevice(unittest.TestCase):
    def test_voice_challenge_verification_lifecycle(self):
        """Verifies voice challenge generation, exact match verification, and rejection on mismatch."""
        ch = voice_phrase_verifier.generate_challenge("destroy_database", speaker_id="operator")
        self.assertIsNotNone(ch.challenge_id)
        self.assertIn(" ", ch.challenge_phrase)

        # Mismatched response rejected
        bad_res = voice_phrase_verifier.verify_response(ch.challenge_id, "wrong phrase")
        self.assertFalse(bad_res["valid"])

        # Correct response accepted and consumed
        good_res = voice_phrase_verifier.verify_response(ch.challenge_id, ch.challenge_phrase)
        self.assertTrue(good_res["valid"])
        self.assertEqual(good_res["target_action"], "destroy_database")

        # Second attempt must fail as challenge was consumed
        consumed_res = voice_phrase_verifier.verify_response(ch.challenge_id, ch.challenge_phrase)
        self.assertFalse(consumed_res["valid"])

    def test_voice_speaker_distance_rejection(self):
        """Verifies speaker biometric distance check rejects imposters above threshold."""
        ch = voice_phrase_verifier.generate_challenge("power_off")

        # Imposter with acoustic distance 0.85 (> 0.65 threshold)
        imposter_res = voice_phrase_verifier.verify_response(
            ch.challenge_id,
            ch.challenge_phrase,
            speaker_distance=0.85
        )
        self.assertFalse(imposter_res["valid"])
        self.assertIn("Speaker identity rejected", imposter_res["reason"])

    def test_browser_guard_ssrf_and_protocol_blocking(self):
        """Verifies browser guard blocks SSRF, metadata IPs, and dangerous schemes (Item 119)."""
        # Cloud metadata blocked
        res_meta = browser_guard.validate_url("http://169.254.169.254/latest/meta-data")
        self.assertFalse(res_meta["valid"])
        self.assertIn("Cloud Metadata", res_meta["reason"])

        # Loopback blocked
        res_loop = browser_guard.validate_url("http://127.0.0.1:8080/admin")
        self.assertFalse(res_loop["valid"])
        self.assertIn("Loopback", res_loop["reason"])

        # File scheme blocked
        res_file = browser_guard.validate_url("file:///C:/Windows/System32/calc.exe")
        self.assertFalse(res_file["valid"])
        self.assertIn("Disallowed URL scheme", res_file["reason"])

        # Javascript scheme blocked
        res_js = browser_guard.validate_url("javascript:alert(document.cookie)")
        self.assertFalse(res_js["valid"])

        # Valid public URL allowed
        res_ok = browser_guard.validate_url("https://www.google.com/search?q=test")
        self.assertTrue(res_ok["valid"])

    def test_browser_guard_sensitive_payment_form(self):
        """Verifies payment / checkout URLs require interactive confirmation before form actions."""
        res_checkout = browser_guard.check_form_action("https://store.example.com/checkout/payment")
        self.assertFalse(res_checkout["allowed"])
        self.assertTrue(res_checkout["requires_confirmation"])
        self.assertEqual(res_checkout["risk"], "HIGH_FINANCIAL_OR_CREDENTIAL")

    def test_mqtt_offline_buffering_and_drain(self):
        """Verifies MQTT buffer stores offline packets and drains in FIFO order upon reconnection."""
        mqtt_buffer.clear()
        
        # Buffer 3 messages
        id1 = mqtt_buffer.enqueue("devices/esp32/relay1", {"state": True}, idempotency_key="key_1")
        id2 = mqtt_buffer.enqueue("devices/esp32/relay2", {"state": False}, idempotency_key="key_2")
        id3 = mqtt_buffer.enqueue("devices/esp32/relay3", {"state": True}, idempotency_key="key_3")

        self.assertEqual(mqtt_buffer.get_buffered_count(), 3)

        # Mock reconnect send function
        dispatched_topics = []
        def mock_sender(topic: str, payload: dict) -> bool:
            dispatched_topics.append(topic)
            return True

        drain_result = mqtt_buffer.drain(mock_sender)
        self.assertEqual(drain_result["sent_count"], 3)
        self.assertEqual(drain_result["remaining_count"], 0)
        self.assertEqual(dispatched_topics, [
            "devices/esp32/relay1",
            "devices/esp32/relay2",
            "devices/esp32/relay3"
        ])


if __name__ == "__main__":
    unittest.main()
