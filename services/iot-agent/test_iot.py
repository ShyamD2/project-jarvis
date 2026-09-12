"""
Integration tests for J.A.R.V.I.S. IoT & Physical Mesh.
Tests Device Shadow synchronization, delta calculation, and Raspberry Pi offline reflex logic.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from shadow_sync import DeviceShadowSync
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../devices/raspberry-pi")))
from gateway import PiGateway


class TestJarvisIoT(unittest.TestCase):
    def test_shadow_delta_detection(self):
        sync = DeviceShadowSync()
        sync.update_reported("esp32_01", {"desk_lamp": False})

        # Set desired to True -> delta should be {"desk_lamp": True}
        shadow = sync.set_desired("esp32_01", {"desk_lamp": True})
        self.assertEqual(shadow["desired"]["desk_lamp"], True)
        self.assertEqual(shadow["reported"]["desk_lamp"], False)

        # Device reports True -> now in sync
        sync.update_reported("esp32_01", {"desk_lamp": True})
        delta = sync._compute_delta(shadow["desired"], shadow["reported"])
        self.assertEqual(len(delta), 0)

    def test_pi_gateway_offline_reflex(self):
        gw = PiGateway()
        # Simulate double clap in offline condition
        reflex = gw.evaluate_offline_reflex("sensory.clap", {"count": 2})
        self.assertIsNotNone(reflex)
        self.assertEqual(reflex["action"], "set_relay")
        self.assertEqual(reflex["target"], "desk_lamp")
        self.assertTrue(reflex["state"])


if __name__ == "__main__":
    unittest.main()
