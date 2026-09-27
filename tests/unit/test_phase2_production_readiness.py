"""
Phase 2 Unit Test Suite: Production Readiness & Reliability Hardening.
Verifies:
  1. SQLite WAL mode, 30s busy timeout, and clean TRUNCATE checkpoints.
  2. Concurrent multi-threaded reads/writes without lock contention.
  3. ACID MissionControl persistence across simulated engine restarts.
  4. Granular Liveness & Readiness probes (/health/live, /health/ready).
  5. Emergency stand-down reflection in readiness probes.
  6. ServiceManager PID tracking and lifecycle utilities.
  7. Public exemption for health probes through SecurityGuardMiddleware.
"""

import os
import sys
import time
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.database import get_sqlite_connection, checkpoint_sqlite_db
from services.planner.mission_persistence import MissionPersistenceManager
from services.planner.mission_control import MissionControl, MissionPhase
from services.jarvis_core.health import check_liveness, check_readiness
from agents.intelligence.emergency_stop import emergency_stop
from scripts.service_manager import is_pid_alive, get_stored_pid


class TestPhase2ProductionReadiness(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_db = os.path.join(self.temp_dir, "test_wal.db")

    def tearDown(self):
        # Ensure emergency stop is restored to nominal state
        if emergency_stop.is_stopped:
            master_key = os.getenv("JARVIS_MASTER_SECRET", "default_master_secret")
            emergency_stop.resume(auth_token=master_key)

        try:
            if os.path.exists(self.test_db):
                os.remove(self.test_db)
            wal_file = f"{self.test_db}-wal"
            if os.path.exists(wal_file):
                os.remove(wal_file)
            shm_file = f"{self.test_db}-shm"
            if os.path.exists(shm_file):
                os.remove(shm_file)
            os.rmdir(self.temp_dir)
        except Exception:
            pass

    def test_sqlite_wal_and_pragmas(self):
        """Verifies that get_sqlite_connection enables WAL mode and busy timeout."""
        with get_sqlite_connection(self.test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE test_items (id INTEGER PRIMARY KEY, name TEXT);")
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0].lower()
            self.assertEqual(journal_mode, "wal", f"Expected WAL journal mode, got {journal_mode}")

            cursor.execute("PRAGMA busy_timeout;")
            busy_timeout = cursor.fetchone()[0]
            self.assertGreaterEqual(busy_timeout, 30000, f"Expected >=30000ms busy timeout, got {busy_timeout}")

        # Test WAL checkpoint TRUNCATE
        ok = checkpoint_sqlite_db(self.test_db)
        self.assertTrue(ok, "Checkpoint should succeed without error")

    def test_concurrent_sqlite_wal_read_write(self):
        """Verifies concurrent multi-threaded writes and reads without database lock exceptions."""
        with get_sqlite_connection(self.test_db) as conn:
            conn.execute("CREATE TABLE counter (id INTEGER PRIMARY KEY, count INTEGER);")
            conn.execute("INSERT INTO counter (id, count) VALUES (1, 0);")
            conn.commit()

        errors = []

        def worker_writer(thread_id: int):
            try:
                for i in range(15):
                    with get_sqlite_connection(self.test_db) as conn:
                        conn.execute("UPDATE counter SET count = count + 1 WHERE id = 1;")
                        conn.commit()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"Writer-{thread_id}: {e}")

        def worker_reader(thread_id: int):
            try:
                for i in range(15):
                    with get_sqlite_connection(self.test_db) as conn:
                        row = conn.execute("SELECT count FROM counter WHERE id = 1;").fetchone()
                        self.assertIsNotNone(row)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"Reader-{thread_id}: {e}")

        threads = []
        for i in range(3):
            t_w = threading.Thread(target=worker_writer, args=(i,))
            t_r = threading.Thread(target=worker_reader, args=(i,))
            threads.extend([t_w, t_r])
            t_w.start()
            t_r.start()

        for t in threads:
            t.join(timeout=5.0)

        self.assertEqual(len(errors), 0, f"Concurrent WAL operations encountered errors: {errors}")

    def test_mission_control_acid_persistence_and_restart(self):
        """Verifies that missions created in MissionControl survive a restart through persistence."""
        mission_db = os.path.join(self.temp_dir, "missions_restart_test.db")
        persistence = MissionPersistenceManager(db_path=mission_db)

        # 1. Boot Engine A and create mission
        engine_a = MissionControl(persistence=persistence)
        m_data = {
            "id": "mission_reboot_test_101",
            "name": "Cluster Disaster Recovery Test",
            "objective": "Verify cross-process state recovery",
            "current_phase": "execute",
            "progress_percent": 65,
            "risk_level": "TIER_2_MUTATING",
            "live_actions": [{"action": "snapshot_ebs", "status": "VERIFIED"}]
        }
        persistence.save_mission(m_data)
        persistence.save_checkpoint("mission_reboot_test_101", 1, {"step": "snapshot_ebs"})

        # 2. Boot Engine B simulating process reboot with same persistence DB
        engine_b = MissionControl(persistence=persistence)
        recovered_mission = engine_b.get_mission("mission_reboot_test_101")

        self.assertIsNotNone(recovered_mission, "Mission should be loaded from persistence on reboot")
        self.assertEqual(recovered_mission["name"], "Cluster Disaster Recovery Test")
        self.assertEqual(recovered_mission["current_phase"], "execute")
        self.assertEqual(recovered_mission["progress_percent"], 65)

        # 3. Active mission recovery
        active_m = engine_b.get_active_mission()
        self.assertIsNotNone(active_m)
        self.assertEqual(active_m["id"], "mission_reboot_test_101")

    def test_liveness_and_readiness_probes(self):
        """Verifies deep health probes return structured metrics and detect emergency stand-down."""
        live_res = check_liveness()
        self.assertEqual(live_res["status"], "alive")
        self.assertIn("uptime_seconds", live_res)
        self.assertIn("pid", live_res)
        self.assertEqual(live_res["pid"], os.getpid())

        # Readiness under normal operation
        is_ready, ready_res = check_readiness()
        self.assertTrue(is_ready)
        self.assertEqual(ready_res["status"], "ready")
        self.assertIn("sqlite_storage", ready_res["checks"])
        self.assertEqual(ready_res["checks"]["sqlite_storage"]["status"], "HEALTHY")
        self.assertIn("latency_ms", ready_res["checks"]["sqlite_storage"])

        # Trigger emergency stand-down -> readiness must transition to False (503)
        emergency_stop.trigger_emergency_stop(reason="Test Emergency Probe")
        try:
            is_ready_stopped, ready_stopped_res = check_readiness()
            self.assertFalse(is_ready_stopped)
            self.assertEqual(ready_stopped_res["status"], "not_ready")
            self.assertEqual(ready_stopped_res["checks"]["emergency_circuit"]["status"], "STAND_DOWN")
        finally:
            master_key = os.getenv("JARVIS_MASTER_SECRET", "default_master_secret")
            emergency_stop.resume(auth_token=master_key)

        # After resume, readiness returns to True
        is_ready_resumed, ready_resumed = check_readiness()
        self.assertTrue(is_ready_resumed)
        self.assertEqual(ready_resumed["status"], "ready")

    def test_service_manager_process_utilities(self):
        """Verifies service_manager process detection and alive checks."""
        current_pid = os.getpid()
        self.assertTrue(is_pid_alive(current_pid), "Current test process PID should be reported alive")

        # Non-existent PID
        fake_pid = 99999999
        self.assertFalse(is_pid_alive(fake_pid), "Unused PID should not be reported alive")

    def test_security_middleware_health_probe_exemption(self):
        """Verifies that all health probes bypass token auth through SecurityGuardMiddleware."""
        from fastapi.testclient import TestClient
        from services.jarvis_core.main import app

        client = TestClient(app)

        # Root liveness & readiness probes
        resp_live = client.get("/health/live")
        self.assertEqual(resp_live.status_code, 200)
        self.assertEqual(resp_live.json().get("status"), "alive")

        resp_ready = client.get("/health/ready")
        self.assertIn(resp_ready.status_code, (200, 503))

        resp_root_health = client.get("/health")
        self.assertIn(resp_root_health.status_code, (200, 503))

        # Versioned api_v1 probes
        resp_v1_live = client.get("/api/v1/health/live")
        self.assertEqual(resp_v1_live.status_code, 200)

        resp_v1_ready = client.get("/api/v1/health/ready")
        self.assertIn(resp_v1_ready.status_code, (200, 503))

        # Mutating route without auth must still be rejected with 401
        resp_mutating = client.post("/api/v1/actions", json={"tool": "test", "parameters": {}})
        self.assertEqual(resp_mutating.status_code, 401, "Mutating endpoint without token must be blocked with 401")


if __name__ == "__main__":
    unittest.main()
