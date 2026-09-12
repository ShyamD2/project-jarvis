"""
Integration tests for J.A.R.V.I.S. Memory, World Model, and RAG Knowledge.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from services.memory.world_model import WorldModel
from services.memory.short_term import ShortTermMemory
from services.memory.long_term import LongTermMemory
from services.memory.knowledge_rag import KnowledgeRAG


class TestJarvisMemory(unittest.TestCase):
    def test_world_model_digital_twin(self):
        wm = WorldModel()
        wm.update_device("esp32_lab_01", relays={"desk_lamp": True}, sensors={"lux": 650.0})
        wm.update_pc(active_window="Visual Studio Code", cpu_percent=15.2)

        snapshot = wm.get_snapshot()
        self.assertIn("esp32_lab_01", snapshot["devices"])
        self.assertTrue(snapshot["devices"]["esp32_lab_01"]["relays"]["desk_lamp"])
        self.assertEqual(snapshot["devices"]["esp32_lab_01"]["sensors"]["lux"], 650.0)
        self.assertEqual(snapshot["pc"]["active_window"], "Visual Studio Code")

    def test_short_term_dialogue_memory(self):
        stm = ShortTermMemory()
        stm.add_turn("user", "Jarvis, what is the server status?")
        stm.add_turn("jarvis", "All systems are nominal, sir.")

        history = stm.get_recent_history()
        self.assertEqual(len(history), 2)
        formatted = stm.format_for_prompt()
        self.assertIn("User: Jarvis, what is the server status?", formatted)
        self.assertIn("J.A.R.V.I.S.: All systems are nominal, sir.", formatted)

    def test_long_term_preferences(self):
        ltm = LongTermMemory(persistence_path=os.path.join(os.path.dirname(__file__), "test_ltm.json"))
        ltm.set_preference("user_title", "sir")
        self.assertEqual(ltm.get_preference("user_title"), "sir")

        # Cleanup test file
        if os.path.exists(ltm.persistence_path):
            os.remove(ltm.persistence_path)

    def test_knowledge_rag_search(self):
        rag = KnowledgeRAG()
        results = rag.search("ESP32 MQTT light protocol")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["doc_id"], "rb_02")
        self.assertIn("ESP32", results[0]["title"])


if __name__ == "__main__":
    unittest.main()
