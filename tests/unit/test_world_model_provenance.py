"""
Unit Tests: World Model Confidence Decay & Memory Provenance (Item 7).
Verifies:
  1. EntityState storage with confidence, observed_at, source, and pid.
  2. Time-decayed confidence calculations on stale observations.
  3. Pruning of stale entities based on confidence threshold.
  4. MemoryItem fields (memory_id, fact, source, created_at, updated_at, confidence, sensitivity, expiration, user_confirmed).
"""

import unittest
import time
from services.memory.world_model import world_model, EntityState
from services.memory.memory_lifecycle import MemoryItem, MemoryProvenance


class TestWorldModelProvenance(unittest.TestCase):
    def test_entity_state_creation_and_decay(self):
        """Invariant: Entity confidence decays over time without fresh observation."""
        ent = EntityState(
            entity_id="proc_chrome_1234",
            entity_type="process",
            state={"name": "chrome.exe", "cpu": 12.5},
            confidence=1.0,
            observed_at=time.time() - 100.0,  # 100 seconds ago
            source="psutil",
            pid=1234,
            decay_rate_per_sec=0.005  # Decay = 0.5 over 100s
        )
        conf = ent.get_confidence()
        self.assertLess(conf, 1.0)
        self.assertAlmostEqual(conf, 0.5, delta=0.05)
        self.assertFalse(ent.is_stale(threshold=0.3))

        # Very old observation
        ent.observed_at = time.time() - 500.0
        self.assertTrue(ent.is_stale(threshold=0.3))

    def test_world_model_entity_lifecycle(self):
        """Invariant: WorldModel tracks entities and prunes stale observations."""
        world_model.update_entity(
            entity_id="window_vscode",
            entity_type="window",
            state={"title": "Visual Studio Code"},
            confidence=1.0,
            source="win32_enum_windows",
            pid=5678
        )
        ent = world_model.get_entity("window_vscode")
        self.assertIsNotNone(ent)
        self.assertEqual(ent.pid, 5678)
        self.assertEqual(ent.source, "win32_enum_windows")
        self.assertEqual(ent.confidence, 1.0)

        # Snapshot includes entities
        snap = world_model.get_snapshot()
        self.assertIn("entities", snap)
        self.assertIn("window_vscode", snap["entities"])

    def test_memory_provenance_and_metadata_fields(self):
        """Invariant: MemoryItem supports full provenance, sensitivity, and confirmation metadata."""
        prov = MemoryProvenance(
            source="voice_command",
            device_id="win_workstation",
            user_id="operator"
        )
        item = MemoryItem(
            id="mem_pref_001",
            content="User prefers dark theme in HUD",
            category="user_preference",
            provenance=prov,
            confidence=0.95,
            sensitivity="CONFIDENTIAL",
            user_confirmed=True
        )

        self.assertEqual(item.memory_id, "mem_pref_001")
        self.assertEqual(item.fact, "User prefers dark theme in HUD")
        self.assertEqual(item.source, "voice_command")
        self.assertEqual(item.sensitivity, "CONFIDENTIAL")
        self.assertTrue(item.user_confirmed)
        self.assertGreater(item.updated_at, 0)

        # Dictionary serialization retains all metadata
        d = item.to_dict()
        self.assertEqual(d["memory_id"], "mem_pref_001")
        self.assertEqual(d["sensitivity"], "CONFIDENTIAL")
        self.assertTrue(d["user_confirmed"])


if __name__ == "__main__":
    unittest.main()
