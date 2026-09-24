"""
Memory Lifecycle & Privacy Deletion Engine for Project J.A.R.V.I.S.
Implements the 7-Stage Deterministic Memory Lifecycle:
  CAPTURE -> CLASSIFY -> STORE -> CONFIDENCE -> DECAY -> REVIEW -> DELETE

Enforces Memory Provenance, Decaying Confidence, Expiration TTL, and GDPR-Grade User Deletion APIs.
"""

from __future__ import annotations
import os
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisMemoryLifecycle")

MEMORY_STORE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "storage_lifecycle_memories.json"))


@dataclass
class MemoryProvenance:
    source: str  # e.g., "voice", "telegram", "cli", "agent_observation", "api"
    device_id: str  # e.g., "win_workstation", "android_node", "web_hud"
    user_id: str  # e.g., "operator", "shyam"
    channel: str = "direct"
    session_id: Optional[str] = None


@dataclass
class MemoryItem:
    id: str
    content: str
    category: str  # "user_preference", "system_state", "fact", "conversation", "transient"
    provenance: MemoryProvenance
    confidence: float = 1.0  # 0.0 to 1.0
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None  # None = permanent fact until deleted
    decay_rate: float = 0.01  # Decay per day (0.0 for permanent preferences)
    last_accessed_at: float = field(default_factory=time.time)
    last_reviewed_at: Optional[float] = None
    status: str = "ACTIVE"  # "ACTIVE", "DECAYED", "ARCHIVED", "DELETED"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryItem:
        prov_data = data.get("provenance", {})
        prov = MemoryProvenance(**prov_data)
        data_copy = dict(data)
        data_copy["provenance"] = prov
        return cls(**data_copy)


class MemoryLifecycleManager:
    """Authoritative memory lifecycle and transparency manager."""

    def __init__(self, persistence_file: str = MEMORY_STORE_PATH):
        self.persistence_file = persistence_file
        self.memories: Dict[str, MemoryItem] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.persistence_file):
            try:
                with open(self.persistence_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for m_id, m_dict in data.items():
                        self.memories[m_id] = MemoryItem.from_dict(m_dict)
                logger.info(f"Loaded {len(self.memories)} memory items from lifecycle store.")
            except Exception as e:
                logger.warning(f"Could not load lifecycle memories: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.persistence_file), exist_ok=True)
            data = {m_id: m.to_dict() for m_id, m in self.memories.items() if m.status != "DELETED"}
            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist memory items: {e}")

    # STAGE 1: CAPTURE
    def capture(
        self,
        raw_text: str,
        source: str = "voice",
        device_id: str = "local_node",
        user_id: str = "operator",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Captures raw conversational or environmental observation with complete provenance."""
        return {
            "draft_id": f"draft_{uuid.uuid4().hex[:8]}",
            "content": raw_text.strip(),
            "provenance": MemoryProvenance(
                source=source,
                device_id=device_id,
                user_id=user_id,
                session_id=session_id
            ),
            "captured_at": time.time()
        }

    # STAGE 2: CLASSIFY
    def classify(self, draft: Dict[str, Any], explicit_category: Optional[str] = None) -> MemoryItem:
        """Categorizes memory draft, sets appropriate initial confidence and TTL expiration."""
        content = draft["content"]
        c_lower = content.lower()

        if explicit_category:
            category = explicit_category
        elif any(k in c_lower for k in ["i prefer", "always", "my name", "never", "i like"]):
            category = "user_preference"
        elif any(k in c_lower for k in ["ip is", "server is", "status", "version"]):
            category = "system_state"
        elif any(k in c_lower for k in ["weather", "tomorrow", "remind me in", "meeting at"]):
            category = "transient"
        else:
            category = "conversation"

        now = time.time()
        # Set category-specific TTL and decay
        if category == "user_preference":
            expires_at = None  # Permanent until deleted
            decay_rate = 0.00
            confidence = 1.0
        elif category == "system_state":
            expires_at = now + (86400 * 7)  # 7 days validity
            decay_rate = 0.05
            confidence = 0.95
        elif category == "transient":
            expires_at = now + 86400  # 24 hours
            decay_rate = 0.20
            confidence = 0.85
        else:
            expires_at = now + (86400 * 30)  # 30 days
            decay_rate = 0.02
            confidence = 0.90

        mem = MemoryItem(
            id=f"mem_{uuid.uuid4().hex[:10]}",
            content=content,
            category=category,
            provenance=draft["provenance"],
            confidence=confidence,
            created_at=now,
            expires_at=expires_at,
            decay_rate=decay_rate,
            last_accessed_at=now,
            status="ACTIVE"
        )
        return mem

    # STAGE 3: STORE
    def store(self, item: MemoryItem) -> MemoryItem:
        """Stores classified memory into authoritative persistent memory store."""
        self.memories[item.id] = item
        self._save()
        logger.info(f"Stored memory [{item.category}] {item.id}: '{item.content[:40]}...' (Confidence: {item.confidence:.2f})")
        return item

    # STAGE 4: CONFIDENCE REINFORCEMENT
    def update_confidence(self, memory_id: str, delta: float, reason: str = "") -> Optional[MemoryItem]:
        """Adjusts memory confidence based on verification corroboration or contradiction."""
        if memory_id not in self.memories:
            return None
        mem = self.memories[memory_id]
        mem.confidence = max(0.0, min(1.0, mem.confidence + delta))
        mem.last_accessed_at = time.time()
        if mem.confidence < 0.2:
            mem.status = "DECAYED"
        self._save()
        logger.info(f"Updated confidence for {memory_id} to {mem.confidence:.2f} ({reason})")
        return mem

    # STAGE 5: DECAY
    def apply_decay(self, elapsed_days: float = 1.0) -> List[str]:
        """Applies mathematical time decay to transient and conversational memories."""
        decayed_ids = []
        now = time.time()
        for m in self.memories.values():
            if m.status != "ACTIVE" or m.decay_rate == 0.0:
                continue
            # Decay based on time
            loss = m.decay_rate * elapsed_days
            m.confidence = max(0.0, m.confidence - loss)
            if m.confidence < 0.3:
                m.status = "DECAYED"
                decayed_ids.append(m.id)
            if m.expires_at and now > m.expires_at:
                m.status = "DECAYED"
                if m.id not in decayed_ids:
                    decayed_ids.append(m.id)
        if decayed_ids:
            self._save()
            logger.info(f"Applied memory decay: {len(decayed_ids)} items decayed.")
        return decayed_ids

    # STAGE 6: REVIEW
    def review(self, memory_id: str, action: str = "keep") -> Optional[MemoryItem]:
        """Operator review: 'keep', 'boost', 'archive', or 'delete'."""
        if memory_id not in self.memories:
            return None
        mem = self.memories[memory_id]
        mem.last_reviewed_at = time.time()
        if action == "keep":
            mem.status = "ACTIVE"
        elif action == "boost":
            mem.confidence = 1.0
            mem.status = "ACTIVE"
        elif action == "archive":
            mem.status = "ARCHIVED"
        elif action == "delete":
            return self.delete(memory_id)
        self._save()
        return mem

    # STAGE 7: DELETE (Full User & GDPR Control)
    def delete(self, memory_id: str) -> bool:
        """Deletes a single memory item with immediate effect."""
        if memory_id in self.memories:
            self.memories[memory_id].status = "DELETED"
            del self.memories[memory_id]
            self._save()
            logger.info(f"Deleted memory item: {memory_id}")
            return True
        return False

    def delete_by_category(self, category: str) -> int:
        """Deletes all memories matching category (e.g. 'conversation', 'transient')."""
        targets = [m_id for m_id, m in self.memories.items() if m.category == category]
        for m_id in targets:
            del self.memories[m_id]
        if targets:
            self._save()
            logger.info(f"Deleted {len(targets)} memories in category '{category}'")
        return len(targets)

    def delete_by_provenance(self, user_id: Optional[str] = None, device_id: Optional[str] = None) -> int:
        """Deletes memories originating from specific user or device."""
        targets = []
        for m_id, m in self.memories.items():
            match_user = (user_id is None) or (m.provenance.user_id == user_id)
            match_dev = (device_id is None) or (m.provenance.device_id == device_id)
            if match_user and match_dev:
                targets.append(m_id)
        for m_id in targets:
            del self.memories[m_id]
        if targets:
            self._save()
            logger.info(f"Deleted {len(targets)} memories for user '{user_id}' / device '{device_id}'")
        return len(targets)

    def purge_expired(self) -> int:
        """Purges memories whose TTL expiration timestamp has passed."""
        now = time.time()
        targets = [m_id for m_id, m in self.memories.items() if m.expires_at and now > m.expires_at]
        for m_id in targets:
            del self.memories[m_id]
        if targets:
            self._save()
            logger.info(f"Purged {len(targets)} expired memory items.")
        return len(targets)

    # TRANSPARENCY REPORT (Answers the 4 Core Questions)
    def get_transparency_report(self) -> Dict[str, Any]:
        """
        Answers the 4 critical memory questions:
        1. What does JARVIS remember?
        2. Why does it remember it?
        3. When does it forget?
        4. How does the user delete it?
        """
        active_items = [m for m in self.memories.values() if m.status == "ACTIVE"]
        categories = {}
        for m in active_items:
            categories[m.category] = categories.get(m.category, 0) + 1

        return {
            "total_active_memories": len(active_items),
            "breakdown_by_category": categories,
            "architecture": {
                "what_is_remembered": "Explicit user preferences, ground-truth system states, and structured task context.",
                "why_it_is_remembered": "To reduce redundant queries, adapt to user preferences, and reconcile real-world state.",
                "when_it_forgets": "Transient items expire in 24h, system states in 7 days, or when confidence decays below 0.3.",
                "how_to_delete": "Execute delete(memory_id), delete_by_category(category), or use POST /api/v1/memory/delete."
            },
            "recent_memories": [
                {
                    "id": m.id,
                    "content": m.content[:60] + "..." if len(m.content) > 60 else m.content,
                    "category": m.category,
                    "confidence": round(m.confidence, 2),
                    "source": m.provenance.source,
                    "device": m.provenance.device_id,
                    "expires_in_seconds": round(m.expires_at - time.time(), 1) if m.expires_at else None
                }
                for m in sorted(active_items, key=lambda x: x.last_accessed_at, reverse=True)[:10]
            ]
        }


memory_lifecycle = MemoryLifecycleManager()
