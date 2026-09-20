"""
J.A.R.V.I.S. Episodic Task Memory Continuum (Pillar 11).
Maintains structured execution history, action trajectories, verification outcomes,
and user feedback across all sessions. Uses SQLite FTS5 for rapid (<5ms)
task similarity retrieval and few-shot trajectory recall.
"""

from __future__ import annotations
import os
import sys
import time
import json
import uuid
import sqlite3
import threading
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisEpisodicMemory")

DB_DIR = os.path.join(PROJECT_ROOT, "data", "memory")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "episodic_memory.db")


class EpisodicMemory:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes relational and FTS5 tables."""
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    task_id TEXT PRIMARY KEY,
                    timestamp REAL,
                    user_query TEXT,
                    intent TEXT,
                    plan_json TEXT,
                    actions_json TEXT,
                    status TEXT,
                    error_message TEXT,
                    duration_ms REAL,
                    verified INTEGER,
                    user_feedback TEXT,
                    correction TEXT
                )
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
                    task_id UNINDEXED,
                    user_query,
                    actions_summary,
                    tokenize='porter unicode61'
                )
            """)
            conn.commit()

    def record_episode(
        self,
        user_query: str,
        intent: str,
        actions_executed: List[Dict[str, Any]],
        status: str = "SUCCESS",
        plan: Optional[List[str]] = None,
        error_message: Optional[str] = None,
        duration_ms: float = 0.0,
        verified: bool = True,
        task_id: Optional[str] = None
    ) -> str:
        """
        Records a completed execution episode into episodic memory.
        """
        tid = task_id or f"ep_{uuid.uuid4().hex[:8]}"
        t_now = time.time()
        plan_str = json.dumps(plan or [])
        actions_str = json.dumps(actions_executed or [])

        # Build search summary of actions
        tool_names = [a.get("tool", "") for a in actions_executed]
        actions_summary = f"{intent} {' '.join(tool_names)}"

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO episodes 
                (task_id, timestamp, user_query, intent, plan_json, actions_json, status, error_message, duration_ms, verified, user_feedback, correction)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tid,
                    t_now,
                    user_query,
                    intent,
                    plan_str,
                    actions_str,
                    status,
                    error_message or "",
                    duration_ms,
                    1 if verified else 0,
                    None,
                    None
                )
            )
            # Update FTS index
            conn.execute(
                "INSERT INTO episodes_fts (task_id, user_query, actions_summary) VALUES (?, ?, ?)",
                (tid, user_query, actions_summary)
            )
            conn.commit()

        logger.info(f"💾 [EpisodicMemory] Recorded episode [{tid}]: \"{user_query[:50]}\" (status={status})")
        return tid

    def record_feedback(self, task_id: str, feedback: str, correction: Optional[str] = None) -> bool:
        """Records user feedback or verbal correction for a specific task episode."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE episodes SET user_feedback = ?, correction = ? WHERE task_id = ?",
                (feedback, correction, task_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def recall_similar_episodes(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieves similar past task executions using SQLite FTS5 search.
        """
        clean_q = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
        if not clean_q:
            return []

        # Split into terms for FTS OR query
        terms = [f'"{term}"' for term in clean_q.split() if len(term) > 2]
        if not terms:
            return []

        fts_query = " OR ".join(terms)

        results = []
        with self._lock, self._get_connection() as conn:
            try:
                cursor = conn.execute(
                    """
                    SELECT e.*, bm25(episodes_fts) AS rank
                    FROM episodes_fts f
                    JOIN episodes e ON f.task_id = e.task_id
                    WHERE episodes_fts MATCH ? AND e.status = 'SUCCESS'
                    ORDER BY rank ASC, e.timestamp DESC
                    LIMIT ?
                    """,
                    (fts_query, limit)
                )
                for row in cursor.fetchall():
                    results.append({
                        "task_id": row["task_id"],
                        "timestamp": row["timestamp"],
                        "user_query": row["user_query"],
                        "intent": row["intent"],
                        "plan": json.loads(row["plan_json"]) if row["plan_json"] else [],
                        "actions": json.loads(row["actions_json"]) if row["actions_json"] else [],
                        "status": row["status"],
                        "duration_ms": row["duration_ms"],
                        "verified": bool(row["verified"]),
                        "user_feedback": row["user_feedback"]
                    })
            except Exception as e:
                logger.warning(f"[EpisodicMemory] FTS query warning: {e}")

        return results

    def get_recent_episodes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns the most recent episodes."""
        results = []
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM episodes ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            for row in cursor.fetchall():
                results.append({
                    "task_id": row["task_id"],
                    "timestamp": row["timestamp"],
                    "user_query": row["user_query"],
                    "intent": row["intent"],
                    "actions": json.loads(row["actions_json"]) if row["actions_json"] else [],
                    "status": row["status"],
                    "verified": bool(row["verified"]),
                    "duration_ms": row["duration_ms"]
                })
        return results

    def format_episodic_context(self, query: str) -> str:
        """
        Formats relevant previous task solutions as few-shot demonstrations for the LLM.
        """
        similar = self.recall_similar_episodes(query, limit=2)
        if not similar:
            return ""

        lines = ["\n[Past Successful Episodes & Workflows for Reference]:"]
        for ep in similar:
            tool_seq = " -> ".join(a.get("tool", "") for a in ep.get("actions", []))
            lines.append(f"• Query: \"{ep['user_query']}\" | Solution: {tool_seq} (Verified)")
        lines.append("")
        return "\n".join(lines)


episodic_memory = EpisodicMemory()
