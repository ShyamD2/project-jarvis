"""
Feedback & Continuous Adaptive Learning Memory for J.A.R.V.I.S.
Records corrections, learns user preferences, and prevents repeating previous mistakes.
"""

import os
import json
import re
from typing import Dict, Any, Optional, List
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisFeedbackLearning")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
STORAGE_DIR = os.path.join(PROJECT_ROOT, "services/memory/storage")
MEMORY_FILE = os.path.join(STORAGE_DIR, "learned_memory.json")


class FeedbackLearner:
    def __init__(self, memory_file: str = MEMORY_FILE):
        self.memory_file = memory_file
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
        self.memory: Dict[str, Any] = self._load_memory()

    def _load_memory(self) -> Dict[str, Any]:
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading learned memory, initializing new: {e}")
        return {
            "preferences": {
                "browser": "opera",
                "workspace_profile": "developer",
                "default_volume": 60
            },
            "corrections": {},
            "aliases": {},
            "history": []
        }

    def _save_memory(self):
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save learned memory: {e}")

    def inspect_and_learn(self, query: str, last_response: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Inspects user input for corrections or preferences.
        Examples:
        - "No, open in Opera instead"
        - "I said Discord not Spotify"
        - "Remember that my default browser is Chrome"
        - "Don't open notepad, open terminal"
        """
        q_lower = query.strip().lower()

        # 1. Direct browser preference learning
        if any(w in q_lower for w in ["preferred browser", "default browser", "favorite browser", "use opera", "use chrome", "use edge"]):
            for b in ["opera", "chrome", "edge", "firefox", "brave"]:
                if b in q_lower:
                    self.memory["preferences"]["browser"] = b
                    self._save_memory()
                    logger.info(f"🧠 [Learning] Committed default browser preference: {b}")
                    return {
                        "type": "preference_learned",
                        "key": "browser",
                        "value": b,
                        "acknowledgement": f"Understood, sir. I have set your preferred browser to {b.capitalize()} and will not repeat that mistake."
                    }

        # 2. Correction pattern: "No, [X] instead" or "Not [X], [Y]"
        correction_match = re.search(r"\b(no|not that|wrong|mistake|instead)\b.*?\b(use|open|launch|do)\s+([a-zA-Z0-9_\-\s]+)", q_lower)
        if correction_match:
            desired_action = correction_match.group(3).strip()
            self.memory["history"].append({
                "query": query,
                "corrected_to": desired_action
            })
            self._save_memory()
            logger.info(f"🧠 [Learning] Recorded correction: {desired_action}")
            return {
                "type": "correction_learned",
                "desired_action": desired_action,
                "acknowledgement": f"My apologies, sir. I have updated my neural memory model: executing '{desired_action}' now."
            }

        # 3. Custom Alias: "When I say X, do Y"
        alias_match = re.search(r"when i say ['\"]?([^'\"]+)['\"]?,?\s+(?:do|run|open)\s+['\"]?([^'\"]+)['\"]?", q_lower)
        if alias_match:
            trigger = alias_match.group(1).strip()
            action = alias_match.group(2).strip()
            self.memory["aliases"][trigger] = action
            self._save_memory()
            logger.info(f"🧠 [Learning] Learned alias: '{trigger}' -> '{action}'")
            return {
                "type": "alias_learned",
                "trigger": trigger,
                "action": action,
                "acknowledgement": f"Understood, sir. Whenever you say '{trigger}', I will execute '{action}'."
            }

        return None

    def apply_learned_adaptations(self, query: str) -> str:
        """
        Rewrites or enhances the query using learned preferences and aliases.
        """
        q_lower = query.strip().lower()

        # Check aliases
        for trigger, action in self.memory.get("aliases", {}).items():
            if trigger in q_lower:
                logger.info(f"🧠 [Learning] Applying learned alias: '{trigger}' -> '{action}'")
                return action

        # Apply preferred browser if query mentions "browser" or "tab" without specifying one
        pref_browser = self.memory.get("preferences", {}).get("browser", "opera")
        if any(w in q_lower for w in ["open tab", "new tab", "browse"]) and not any(b in q_lower for b in ["opera", "chrome", "edge"]):
            return f"{query} on {pref_browser}"

        return query


learner = FeedbackLearner()
