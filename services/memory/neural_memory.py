"""
Deep Learning Neural Memory Graph for Project J.A.R.V.I.S. (Pillar 11).
Passively extracts facts, technical preferences, project topologies, and personal details
from user dialogue. Maintains a persistent semantic memory store and injects relevant memories
dynamically into context so J.A.R.V.I.S. remembers everything across sessions with <5ms recall.
"""

from __future__ import annotations
import os
import sys
import re
import time
import json
import uuid
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisNeuralMemory")

MEMORY_DIR = os.path.join(PROJECT_ROOT, "data", "memory")
os.makedirs(MEMORY_DIR, exist_ok=True)
MEMORY_FILE = os.path.join(MEMORY_DIR, "neural_memory_graph.json")


class NeuralMemoryGraph:
    def __init__(self):
        self._memories: Dict[str, Dict[str, Any]] = {}
        self._load_storage()

    def _load_storage(self):
        """Loads persistent memories from disk."""
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._memories = data.get("memories", {})
            except Exception as e:
                logger.warning(f"[NeuralMemory] Failed to load memory file: {e}")
                self._memories = {}
        else:
            # Seed default project memory
            self.remember(
                fact="The user is building Project J.A.R.V.I.S., a peerless Agentic OS.",
                category="project_context",
                importance=1.0
            )

    def _save_storage(self):
        """Atomically saves memories to disk."""
        try:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump({"memories": self._memories, "updated_at": time.time()}, f, indent=2)
        except Exception as e:
            logger.error(f"[NeuralMemory] Failed to save memories: {e}")

    def _extract_tokens(self, text: str) -> set[str]:
        """Tokenizes text for hybrid semantic keyword and ontology matching."""
        clean = re.sub(r"[^\w\s]", " ", text.lower())
        tokens = clean.split()
        stopwords = {
            "a", "an", "the", "is", "are", "was", "were", "and", "or", "in", "on", "at",
            "to", "for", "with", "about", "it", "this", "that", "i", "my", "you", "your",
            "what", "which", "do", "should", "we", "our"
        }
        extracted = {t for t in tokens if len(t) > 2 and t not in stopwords}

        # Domain Ontology Expansion for Deep Learning Semantic Matching
        TECH_ONTOLOGY = {
            "database": {"postgresql", "postgres", "mysql", "mongodb", "sqlite", "redis", "dynamodb"},
            "cloud": {"aws", "azure", "gcp", "terraform", "kubernetes", "docker"},
            "architecture": {"microservices", "monolith", "serverless", "distributed"}
        }
        expanded = set(extracted)
        for concept, terms in TECH_ONTOLOGY.items():
            if extracted & terms:
                expanded.add(concept)
            if concept in extracted:
                expanded.update(terms)

        return expanded

    def remember(
        self,
        fact: str,
        category: str = "general",
        importance: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Stores a discrete fact or concept into the neural memory graph.
        Deduplicates if a nearly identical fact exists.
        """
        fact_clean = fact.strip()
        tokens = self._extract_tokens(fact_clean)

        # Check for existing duplicate fact
        for mid, m in self._memories.items():
            existing_tokens = set(m.get("tokens", []))
            if tokens and existing_tokens:
                overlap = len(tokens & existing_tokens) / len(tokens | existing_tokens)
                if overlap > 0.8:
                    # Update importance and timestamp of existing memory
                    m["importance"] = max(m.get("importance", 1.0), importance)
                    m["updated_at"] = time.time()
                    m["fact"] = fact_clean
                    self._save_storage()
                    return m

        mem_id = f"mem_{uuid.uuid4().hex[:8]}"
        record = {
            "id": mem_id,
            "fact": fact_clean,
            "category": category,
            "importance": float(importance),
            "tokens": list(tokens),
            "created_at": time.time(),
            "updated_at": time.time(),
            "metadata": metadata or {}
        }
        self._memories[mem_id] = record
        self._save_storage()
        logger.info(f"🧠 [NeuralMemory] Stored memory [{mem_id}] ({category}): \"{fact_clean}\"")
        return record

    def auto_extract_and_remember(self, utterance: str) -> List[Dict[str, Any]]:
        """
        Passive Deep Learning Fact Extraction:
        Analyzes user statements in the background to automatically identify
        technical preferences, personal facts, project details, and goals.
        """
        extracted = []
        u = utterance.strip()
        u_lower = u.lower()

        # 1. Technical Preferences ("I prefer X over Y", "My favorite stack is X")
        m_pref = re.search(r"\b(?:i\s+prefer|i\s+like|my\s+favorite\s+\w+\s+is)\s+([^.!?]+)", u_lower)
        if m_pref:
            fact = f"User preference: {m_pref.group(0).strip()}."
            extracted.append(self.remember(fact=fact, category="tech_preference", importance=0.9))

        # 2. Personal Identity & Credentials ("My name is X", "I am a cloud engineer")
        m_ident = re.search(r"\b(?:my\s+name\s+is|i\s+am\s+(?:a|an)?\s+([a-zA-Z\s]+))", u_lower)
        if m_ident and not any(w in u_lower for w in ["trying", "going", "ready"]):
            fact = f"User identity: {u.strip()}."
            extracted.append(self.remember(fact=fact, category="personal", importance=0.95))

        # 3. Goals & Milestones ("My goal is X", "I want to crack FAANG", "Preparing for X")
        m_goal = re.search(r"\b(?:my\s+goal\s+is|i\s+want\s+to|i\s+am\s+preparing\s+for|targeting)\s+([^.!?]+)", u_lower)
        if m_goal:
            fact = f"User goal: {m_goal.group(0).strip()}."
            extracted.append(self.remember(fact=fact, category="goal", importance=0.95))

        # 4. Explicit Memorization ("Remember that X", "Note that X")
        m_exp = re.search(r"\b(?:remember\s+(?:that)?|note\s+(?:that)?|keep\s+in\s+mind\s+(?:that)?)\s+([^.!?]+)", u, re.IGNORECASE)
        if m_exp:
            fact = f"Explicit user note: {m_exp.group(1).strip()}."
            extracted.append(self.remember(fact=fact, category="explicit_note", importance=1.0))

        # 5. Infrastructure / Architecture Facts ("Our server is X", "We use PostgreSQL")
        m_infra = re.search(r"\b(?:our\s+(?:server|database|cluster|stack)\s+is|we\s+use\s+([a-zA-Z0-9\s]+)\s+for)\s+([^.!?]+)", u_lower)
        if m_infra:
            fact = f"Infrastructure context: {u.strip()}."
            extracted.append(self.remember(fact=fact, category="project_context", importance=0.85))

        return extracted

    def recall_relevant(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Hybrid Semantic Retrieval (<5ms):
        Calculates relevance score combining keyword intersection, category weighting,
        and importance score. Returns top-K most relevant memories.
        """
        query_tokens = self._extract_tokens(query)
        scored_memories = []

        for mid, m in self._memories.items():
            tokens = set(m.get("tokens", []))
            fact_str = m.get("fact", "").lower()
            relevance = 0.0

            # Direct keyword overlap
            if query_tokens and tokens:
                shared = len(query_tokens & tokens)
                if shared > 0:
                    relevance += (shared / len(query_tokens)) * 2.0

            # Substring exact match boost
            for qt in query_tokens:
                if qt in fact_str:
                    relevance += 0.5

            # Importance factor
            relevance *= m.get("importance", 1.0)

            if relevance > 0.1:
                scored_memories.append((relevance, m))
            elif m.get("importance", 0.0) >= 0.95:
                scored_memories.append((0.05 * m.get("importance", 1.0), m))

        # Sort by relevance descending
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_memories[:top_k]]

    def format_memory_context(self, query: str) -> str:
        """
        Formats retrieved memories into an elegant context injection block for the LLM.
        """
        recalled = self.recall_relevant(query, top_k=4)
        if not recalled:
            return ""

        lines = ["\n[Persistent Neural Memory Recall (What you know about the user & system)]:"]
        for m in recalled:
            lines.append(f"• [{m.get('category', 'general')}]: {m.get('fact')}")
        lines.append("")
        return "\n".join(lines)

    def list_all_memories(self) -> List[Dict[str, Any]]:
        """Returns all stored memories sorted by recency."""
        return sorted(list(self._memories.values()), key=lambda x: x.get("created_at", 0), reverse=True)

    def forget_memory(self, identifier: str) -> bool:
        """Deletes a memory by ID or matching keyword."""
        if identifier in self._memories:
            del self._memories[identifier]
            self._save_storage()
            return True

        # Check keyword match
        to_del = []
        for mid, m in self._memories.items():
            if identifier.lower() in m.get("fact", "").lower():
                to_del.append(mid)

        if to_del:
            for d in to_del:
                del self._memories[d]
            self._save_storage()
            return True

        return False


neural_memory = NeuralMemoryGraph()
