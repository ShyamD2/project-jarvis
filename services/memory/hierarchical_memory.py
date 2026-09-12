"""
Hierarchical Memory Architecture for Project J.A.R.V.I.S.
Coordinates all 7 cognitive memory tiers:
1. Working Memory (in-flight context & active subtask variables)
2. Conversation Memory (recent dialogue turns)
3. Episodic Memory (mission logs, milestones, historical incidents)
4. Semantic Memory (concepts, infrastructure topologies, relationships)
5. Procedural Memory (playbooks, action sequences, how tasks were solved)
6. Preferences & Feedback (user habits, corrections, learned aliases)
7. Knowledge & RAG (indexed manuals, documentation, vector embeddings)
"""

from __future__ import annotations
import os
import json
import time
from typing import Dict, Any, List, Optional

try:
    from .short_term import short_term_memory
    from .feedback_learning import learner
    from .knowledge_rag import knowledge_rag
    from .long_term import long_term_memory
except ImportError:
    from short_term import short_term_memory
    from feedback_learning import learner
    from knowledge_rag import knowledge_rag
    from long_term import long_term_memory

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)
PROCEDURAL_FILE = os.path.join(STORAGE_DIR, "procedural_memory.json")
SEMANTIC_FILE = os.path.join(STORAGE_DIR, "semantic_memory.json")
EPISODIC_FILE = os.path.join(STORAGE_DIR, "episodic_memory.json")


class HierarchicalMemory:
    def __init__(self):
        self.procedural: Dict[str, Any] = self._load_json(PROCEDURAL_FILE, {
            "deploy_docker": {
                "steps": ["build_image", "run_container", "verify_healthcheck"],
                "last_success": time.time(),
                "success_count": 5
            },
            "prepare_workspace": {
                "steps": ["illuminate_desk_lamp", "launch_vscode", "launch_terminal"],
                "last_success": time.time(),
                "success_count": 12
            },
            "restart_web_service": {
                "steps": ["check_port_listening", "terminate_existing", "start_uvicorn", "poll_health_200"],
                "last_success": time.time(),
                "success_count": 8
            }
        })

        default_browser_path = os.getenv("DEFAULT_BROWSER_PATH") or (
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe")
            if os.name == "nt" else "/usr/bin/google-chrome"
        )
        self.semantic: Dict[str, Any] = self._load_json(SEMANTIC_FILE, {
            "entities": {
                "opera_gx": {"type": "browser", "path": default_browser_path},
                "esp32_lab_01": {"type": "iot_node", "ip": "192.168.1.105", "sensors": ["lux", "temp"]},
                "aws_core": {"region": "us-east-1", "primary_services": ["EC2", "S3", "Lambda", "EventBridge"]}
            }
        })

        self.episodic: List[Dict[str, Any]] = self._load_json(EPISODIC_FILE, [])

    def _load_json(self, path: str, default: Any) -> Any:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load memory file '{path}': {e}")
        return default

    def _save_json(self, path: str, data: Any):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save memory file '{path}': {e}")

    # Tier 1 & 2: Working & Conversation
    def add_conversation_turn(self, role: str, content: str, intent: Optional[str] = None):
        short_term_memory.add_turn(role, content, intent)

    def get_conversation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return short_term_memory.get_recent_history(limit)

    def set_working_context(self, key: str, value: Any):
        short_term_memory.context_scratchpad[key] = value

    def get_working_context(self, key: str) -> Any:
        return short_term_memory.context_scratchpad.get(key)

    # Tier 3: Episodic
    def remember_episode(self, event_name: str, outcome: str, details: Dict[str, Any]):
        episode = {
            "timestamp": time.time(),
            "event": event_name,
            "outcome": outcome,
            "details": details
        }
        self.episodic.append(episode)
        if len(self.episodic) > 500:
            self.episodic.pop(0)
        self._save_json(EPISODIC_FILE, self.episodic)

    # Tier 4: Semantic
    def get_entity(self, name: str) -> Optional[Dict[str, Any]]:
        return self.semantic.get("entities", {}).get(name.lower())

    def update_entity(self, name: str, data: Dict[str, Any]):
        if "entities" not in self.semantic:
            self.semantic["entities"] = {}
        self.semantic["entities"][name.lower()] = data
        self._save_json(SEMANTIC_FILE, self.semantic)

    # Tier 5: Procedural
    def remember_procedural(self, task_name: str, steps: List[str]):
        self.procedural[task_name] = {
            "steps": steps,
            "last_updated": time.time(),
            "success_count": self.procedural.get(task_name, {}).get("success_count", 0) + 1
        }
        self._save_json(PROCEDURAL_FILE, self.procedural)

    def get_procedure(self, task_name: str) -> Optional[List[str]]:
        proc = self.procedural.get(task_name)
        return proc["steps"] if proc else None

    # Tier 6: Preferences & Feedback
    def get_preferences(self) -> Dict[str, Any]:
        prefs = dict(long_term_memory.preferences)
        prefs.update(learner.memory.get("preferences", {}))
        return prefs

    def learn_preference(self, key: str, value: Any):
        learner.memory.setdefault("preferences", {})[key] = value
        learner._save_memory()
        long_term_memory.set_preference(key, value)

    def record_experience(self, incident_id: str, learnings: Dict[str, Any]):
        long_term_memory.record_experience(incident_id, learnings)

    def get_experiences(self) -> Dict[str, Any]:
        return long_term_memory.experiences

    # Tier 7: Knowledge & RAG
    def search_knowledge(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        return knowledge_rag.search(query, limit)

    # Unified Cognitive Recall across all 7 tiers
    def recall(self, query: str) -> Dict[str, Any]:
        q_lower = query.lower()
        matched_proc = None
        for k, v in self.procedural.items():
            if k in q_lower or any(word in q_lower for word in k.split("_")):
                matched_proc = {k: v}
                break

        return {
            "working_memory": short_term_memory.context_scratchpad,
            "recent_turns": short_term_memory.get_recent_history(limit=4),
            "procedural": matched_proc,
            "preferences": self.get_preferences(),
            "experiences": self.get_experiences(),
            "knowledge": self.search_knowledge(query, limit=2)
        }


hierarchical_memory = HierarchicalMemory()
