"""
ACID SQLite Mission & State Persistence Manager (Phase 36 Stage 36.8).
Ensures missions, tasks, and state checkpoints survive process crashes,
system reboots, and network disconnects.
"""

from __future__ import annotations
import os
import sqlite3
import json
import time
import uuid
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisMissionPersistence")


class MissionPersistenceManager:
    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            storage_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "storage"))
            os.makedirs(storage_dir, exist_ok=True)
            db_path = os.path.join(storage_dir, "missions.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS missions (
                        mission_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        objective TEXT NOT NULL,
                        current_phase TEXT NOT NULL,
                        progress_percent INTEGER DEFAULT 0,
                        risk_level TEXT DEFAULT 'LOW',
                        cost_usd REAL DEFAULT 0.0,
                        final_result TEXT,
                        dag_json TEXT,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoints (
                        checkpoint_id TEXT PRIMARY KEY,
                        mission_id TEXT NOT NULL,
                        step_index INTEGER NOT NULL,
                        state_hash TEXT,
                        snapshot_json TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        FOREIGN KEY(mission_id) REFERENCES missions(mission_id)
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"[MissionPersistence] SQLite init failed: {e}")

    def save_mission(self, mission_data: Dict[str, Any]) -> str:
        """Upserts a mission record into SQLite."""
        m_id = mission_data.get("mission_id") or mission_data.get("id")
        if not m_id:
            raise ValueError("Mission data missing mandatory mission_id / id.")
        now = time.time()
        dag_json = json.dumps(mission_data.get("live_actions", []))

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO missions (
                    mission_id, name, objective, current_phase, progress_percent,
                    risk_level, cost_usd, final_result, dag_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(mission_id) DO UPDATE SET
                    current_phase = excluded.current_phase,
                    progress_percent = excluded.progress_percent,
                    cost_usd = excluded.cost_usd,
                    final_result = excluded.final_result,
                    dag_json = excluded.dag_json,
                    updated_at = excluded.updated_at
            """, (
                m_id,
                mission_data.get("name", "Unnamed Mission"),
                mission_data.get("objective", ""),
                mission_data.get("current_phase", "analyze"),
                mission_data.get("progress_percent", 0),
                mission_data.get("risk_level", "LOW"),
                mission_data.get("cost_usd", 0.0),
                mission_data.get("final_result"),
                dag_json,
                mission_data.get("created_at", now),
                now
            ))
            conn.commit()
        return m_id

    def get_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM missions WHERE mission_id = ?", (mission_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["live_actions"] = json.loads(d.get("dag_json") or "[]")
            return d

    def list_missions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM missions ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
            missions = []
            for r in rows:
                d = dict(r)
                d["live_actions"] = json.loads(d.get("dag_json") or "[]")
                missions.append(d)
            return missions

    def save_checkpoint(self, mission_id: str, step_index: int, snapshot: Dict[str, Any]) -> str:
        """Saves an execution checkpoint snapshot for crash recovery."""
        cp_id = f"cp_{uuid.uuid4().hex[:8]}"
        now = time.time()
        snap_json = json.dumps(snapshot)
        state_hash = snapshot.get("state_hash", "")

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO checkpoints (checkpoint_id, mission_id, step_index, state_hash, snapshot_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (cp_id, mission_id, step_index, state_hash, snap_json, now))
            conn.commit()
        return cp_id

    def get_latest_checkpoint(self, mission_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM checkpoints WHERE mission_id = ? ORDER BY step_index DESC LIMIT 1",
                (mission_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["snapshot"] = json.loads(d.get("snapshot_json") or "{}")
            return d

    def get_interrupted_missions(self) -> List[Dict[str, Any]]:
        """Returns all missions in non-terminal active phases that survived a crash."""
        terminal_phases = ("complete", "aborted", "failed")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM missions WHERE current_phase NOT IN ({','.join(['?']*len(terminal_phases))})",
                terminal_phases
            ).fetchall()
            return [dict(r) for r in rows]


mission_persistence = MissionPersistenceManager()
