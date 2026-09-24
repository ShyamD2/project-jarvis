"""
Unit Tests: Node Mesh Protocol & Geolocation Privacy Controls (Phase 36 / Cross-Device Pillar).
Verifies:
  1. Node registration, heartbeat recording, and liveness detection.
  2. Capability discovery across device types.
  3. Action dispatch with receipt generation.
  4. Geolocation privacy defaults (location_enabled = False, LocationPrecision.NEVER).
  5. Location tracking blocking when disabled (LOCATION_PRIVACY_BLOCKED).
  6. Approximate vs Precise coordinate sanitization.
"""

import unittest
import asyncio
from devices.node_mesh import (
    node_mesh,
    JarvisNode,
    DeviceType,
    NodeState,
    LocationPrecision
)


class TestNodeMeshProtocol(unittest.TestCase):
    def setUp(self):
        # Register a test mobile node
        self.node = node_mesh.register_node(
            node_id="test_pixel_phone",
            device_id="dev_pixel_99",
            name="Test Pixel Companion",
            device_type=DeviceType.ANDROID,
            capabilities=["notification", "vibrate", "gps_location", "camera"],
            auth_token="secure_test_token_2026"
        )

    def test_node_registration_and_heartbeat(self):
        """Invariant: Node is registered with correct capabilities and records heartbeats."""
        self.assertEqual(self.node.name, "Test Pixel Companion")
        self.assertTrue(self.node.is_alive())
        self.assertTrue(self.node.has_capability("notification"))
        self.assertTrue(self.node.has_capability("gps_location"))

        # Heartbeat update
        ok = node_mesh.record_heartbeat("test_pixel_phone", telemetry={"battery": 92})
        self.assertTrue(ok)
        self.assertEqual(self.node.telemetry.get("battery"), 92)

    def test_capability_discovery(self):
        """Invariant: Coordinator discovers active nodes by required capability."""
        camera_nodes = node_mesh.discover_nodes_by_capability("camera")
        self.assertGreater(len(camera_nodes), 0)
        self.assertTrue(any(n.node_id == "test_pixel_phone" for n in camera_nodes))

        phone_nodes = node_mesh.discover_nodes_by_type(DeviceType.ANDROID)
        self.assertGreater(len(phone_nodes), 0)

    def test_action_dispatch_and_receipt(self):
        """Invariant: Dispatched action produces verified receipt."""
        res = asyncio.run(
            node_mesh.dispatch_device_action(
                target_node_id="test_pixel_phone",
                action="notification",
                parameters={"title": "Alert", "body": "Test alert message"}
            )
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "DISPATCHED_AND_VERIFIED")
        self.assertIn("receipt_id", res)

    def test_default_location_privacy_is_disabled(self):
        """Invariant: Location is NEVER enabled by default and defaults to NEVER precision."""
        self.assertFalse(self.node.location_enabled)
        self.assertEqual(self.node.location_precision, LocationPrecision.NEVER)

        # Dispatching location query while disabled must be strictly blocked
        res = asyncio.run(
            node_mesh.dispatch_device_action(
                target_node_id="test_pixel_phone",
                action="gps_location",
                parameters={"latitude": 37.774929, "longitude": -122.419416}
            )
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "LOCATION_PRIVACY_BLOCKED")

    def test_approximate_location_sanitization(self):
        """Invariant: APPROXIMATE precision rounds lat/lon to 2 decimals (~1.1 km)."""
        node_mesh.set_node_location_privacy(
            node_id="test_pixel_phone",
            enabled=True,
            precision=LocationPrecision.APPROXIMATE
        )
        res = asyncio.run(
            node_mesh.dispatch_device_action(
                target_node_id="test_pixel_phone",
                action="gps_location",
                parameters={"latitude": 37.774929, "longitude": -122.419416}
            )
        )
        self.assertTrue(res["success"])
        loc = res["parameters"]["sanitized_location"]
        self.assertEqual(loc["latitude"], 37.77)
        self.assertEqual(loc["longitude"], -122.42)
        self.assertEqual(loc["precision"], "approximate")

    def test_precise_location_preservation(self):
        """Invariant: PRECISE precision preserves full decimal resolution."""
        node_mesh.set_node_location_privacy(
            node_id="test_pixel_phone",
            enabled=True,
            precision=LocationPrecision.PRECISE
        )
        res = asyncio.run(
            node_mesh.dispatch_device_action(
                target_node_id="test_pixel_phone",
                action="gps_location",
                parameters={"latitude": 37.774929, "longitude": -122.419416}
            )
        )
        self.assertTrue(res["success"])
        loc = res["parameters"]["sanitized_location"]
        self.assertEqual(loc["latitude"], 37.774929)
        self.assertEqual(loc["longitude"], -122.419416)
        self.assertEqual(loc["precision"], "precise")


if __name__ == "__main__":
    unittest.main()
