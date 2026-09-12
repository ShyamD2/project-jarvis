"""
Long-Term Memory and Preference Store for J.A.R.V.I.S.
Stores persistent user preferences, identity attributes, and past operational learnings.
"""

from __future__ import annotations
import json
import os
from typing import Dict, Any, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisLongTermMemory")


class LongTermMemory:
    def __init__(self, persistence_path: Optional[str] = None):
        self.persistence_path = persistence_path or os.path.join(
            os.path.dirname(__file__), "storage_long_term.json"
        )
        self.preferences: Dict[str, Any] = {
            "user_title": "sir",
            "preferred_voice": "en-GB-RyanNeural",
            "theme": "arc_reactor_cyan",
            "default_editor": "code",
            "default_terminal": "powershell",
            "auto_confirm_tier1": True,
            "max_autonomous_budget_usd": 5.0
        }
        self.experiences: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.persistence_path):
            try:
                with open(self.persistence_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.preferences.update(data.get("preferences", {}))
                    self.experiences.update(data.get("experiences", {}))
            except Exception as e:
                logger.warning(f"Could not load long-term memory file: {e}")

    def save(self):
        try:
            with open(self.persistence_path, "w", encoding="utf-8") as f:
                json.dump({
                    "preferences": self.preferences,
                    "experiences": self.experiences
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving long-term memory: {e}")

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self.preferences.get(key, default)

    def set_preference(self, key: str, value: Any):
        self.preferences[key] = value
        self.save()

    def record_experience(self, incident_id: str, learnings: Dict[str, Any]):
        """Store self-healing experience or remediation playbook"""
        self.experiences[incident_id] = learnings
        self.save()


long_term_memory = LongTermMemory()
