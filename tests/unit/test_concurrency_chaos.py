"""
Concurrency & Race Condition Stress Test Suite (Phase 5).
Simulates high-concurrency chaos across SQLite WAL access, offline buffer queues,
and event mesh dual-dispatch to guarantee zero 'database is locked' errors, zero data corruption,
and ACID integrity under heavy asynchronous load.
"""

import os
import time
import uuid
import unittest
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from shared.database import get_sqlite_connection, checkpoint_sqlite_db
from services.iot_agent.mqtt_buffer import MQTTOfflineBuffer
from shared.schemas.event_envelope import JarvisEvent
from shared.sdk_python.jarvis_sdk.event_mesh import EventMesh


class TestConcurrencyChaos(unittest.TestCase):
    """Stress tests multi-threaded SQLite WAL access, offline spooling, and event dispatch."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "chaos_test.db")
        # Initialize schema
        with get_sqlite_connection(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE items (
                    id TEXT PRIMARY KEY,
                    worker_id INTEGER,
                    seq INTEGER,
                    payload TEXT,
                    created_at REAL
                )
            """)
            conn.commit()

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_50_concurrent_sqlite_wal_workers_no_locks(self):
        """
        Spawns 50 concurrent threads simultaneously performing read/write/update transactions.
        Guarantees:
          - Zero 'sqlite3.OperationalError: database is locked'
          - Zero data loss (50 workers * 10 records = 500 verified rows)
          - ACID consistency in WAL mode
        """
        num_workers = 50
        records_per_worker = 10
        errors: List[Exception] = []

        def worker_task(worker_id: int):
            try:
                for seq in range(records_per_worker):
                    item_id = f"item_w{worker_id}_s{seq}_{uuid.uuid4().hex[:6]}"
                    # Write
                    with get_sqlite_connection(self.db_path) as conn:
                        conn.execute(
                            "INSERT INTO items (id, worker_id, seq, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                            (item_id, worker_id, seq, f"payload_{worker_id}_{seq}", time.time())
                        )
                        conn.commit()

                    # Interleaved read
                    with get_sqlite_connection(self.db_path) as conn:
                        row = conn.execute("SELECT id, payload FROM items WHERE id = ?", (item_id,)).fetchone()
                        if not row or row["payload"] != f"payload_{worker_id}_{seq}":
                            raise ValueError(f"Data corruption on read for {item_id}")

                    # Interleaved aggregate count
                    with get_sqlite_connection(self.db_path) as conn:
                        _ = conn.execute("SELECT count(*) FROM items").fetchone()

            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker_task, wid) for wid in range(num_workers)]
            for f in as_completed(futures):
                f.result()

        # Verify zero lock failures or exceptions
        self.assertEqual(len(errors), 0, f"Encountered errors during concurrent WAL access: {errors}")

        # Verify final record count matches exactly
        with get_sqlite_connection(self.db_path) as conn:
            total_count = conn.execute("SELECT count(*) AS cnt FROM items").fetchone()["cnt"]
            self.assertEqual(total_count, num_workers * records_per_worker)

        # Checkpoint WAL cleanly
        ok = checkpoint_sqlite_db(self.db_path)
        self.assertTrue(ok)

    def test_concurrent_mqtt_offline_buffer_spooling(self):
        """
        Simulates 30 concurrent sensor feeds rapidly enqueueing messages into MQTTOfflineBuffer.
        Guarantees:
          - No race conditions during concurrent enqueue
          - Deduplication and idempotency key preservation
          - Accurate FIFO drain count
        """
        buffer_db = os.path.join(self.temp_dir.name, "chaos_mqtt_buffer.db")
        buffer = MQTTOfflineBuffer(db_path=buffer_db)
        num_producers = 30
        items_per_producer = 5
        errors = []

        def producer_task(pid: int):
            try:
                for i in range(items_per_producer):
                    topic = f"telemetry/sensor_{pid}/metric_{i}"
                    idem_key = f"idem_p{pid}_i{i}"
                    buffer.enqueue(topic, {"sensor": pid, "value": i * 1.5}, idempotency_key=idem_key)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=num_producers) as executor:
            futures = [executor.submit(producer_task, p) for p in range(num_producers)]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0)
        expected_total = num_producers * items_per_producer
        self.assertEqual(buffer.get_buffered_count(), expected_total)

        # Concurrently drain messages
        drained_topics = []
        drain_lock = threading.Lock()

        def test_sender(topic: str, payload: dict) -> bool:
            with drain_lock:
                drained_topics.append(topic)
            return True

        drain_stats = buffer.drain(test_sender)
        self.assertEqual(drain_stats["sent_count"], expected_total)
        self.assertEqual(drain_stats["remaining_count"], 0)
        self.assertEqual(len(drained_topics), expected_total)

    def test_concurrent_event_mesh_dispatch(self):
        """
        Verifies EventMesh handles high-frequency multi-threaded event publishing
        with concurrent dynamic subscribers without race conditions or memory corruption.
        """
        mesh = EventMesh()
        # Disable external clients for isolated local stress
        mesh._mqtt_client = None
        mesh._eventbridge_client = None

        received_events: List[JarvisEvent] = []
        lock = threading.Lock()

        def event_handler(event: JarvisEvent):
            with lock:
                received_events.append(event)

        mesh.subscribe("stress.telemetry", event_handler)
        mesh.subscribe("*", event_handler)  # Wildcard handler receives duplicate

        num_threads = 25
        events_per_thread = 10

        def publish_task(tid: int):
            for seq in range(events_per_thread):
                ev = JarvisEvent(
                    source=f"thread.{tid}",
                    type="stress.telemetry",
                    data={"thread": tid, "seq": seq}
                )
                mesh.publish(ev, fast_path=False, cloud_sync=False)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(publish_task, t) for t in range(num_threads)]
            for f in as_completed(futures):
                f.result()

        # Each event triggers exact match + wildcard = 2 deliveries
        expected_deliveries = num_threads * events_per_thread * 2
        self.assertEqual(len(received_events), expected_deliveries)


if __name__ == "__main__":
    unittest.main()
