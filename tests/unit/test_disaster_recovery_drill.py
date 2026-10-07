"""
Unit Tests for Automated Disaster Recovery Drill & Integrity Verification (Phase 36 / Item 8).
Validates:
  1. Backup creation generates valid SHA-256 manifests and HMAC signatures.
  2. Byte-corruption and tampered archives are detected cryptographically on restore.
  3. Wipe and restore workflow recovers full state and passes PRAGMA integrity check.
  4. End-to-end full drill execution returns 100% ONLINE health with zero data loss.
"""

from __future__ import annotations

import os
import sys
import json
import shutil
import sqlite3
import tempfile
import zipfile
import pytest

from services.recovery.disaster_drill import DisasterRecoveryDrill, compute_sha256_file


class TestDisasterRecoveryDrill:
    @pytest.fixture(autouse=True)
    def setup_test_env(self):
        self.temp_root = tempfile.mkdtemp(prefix="jarvis_dr_test_")
        self.backup_dir = os.path.join(self.temp_root, "backups")
        os.makedirs(self.backup_dir, exist_ok=True)

        # 1. Create simulated Planner missions.db
        planner_dir = os.path.join(self.temp_root, "services", "planner", "storage")
        os.makedirs(planner_dir, exist_ok=True)
        self.missions_db = os.path.join(planner_dir, "missions.db")
        conn = sqlite3.connect(self.missions_db)
        conn.execute("""
            CREATE TABLE missions (
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
            CREATE TABLE checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                state_hash TEXT,
                snapshot_json TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        conn.execute("""
            INSERT INTO missions VALUES (
                'm_test_01', 'Test Autonomous Mission', 'Verify resilience',
                'EXECUTE', 50, 'LOW', 0.01, NULL,
                '["node_init", "node_audit", "node_verify"]', 1700000000.0, 1700000010.0
            )
        """)
        conn.execute("""
            INSERT INTO checkpoints VALUES (
                'cp_test_01', 'm_test_01', 1, 'hash_abc123',
                '{"step": 1, "status": "CHECKPOINT_OK"}', 1700000005.0
            )
        """)
        conn.commit()
        conn.close()

        # 2. Create simulated IoT MQTT buffer db
        iot_dir = os.path.join(self.temp_root, "services", "iot_agent", "storage")
        os.makedirs(iot_dir, exist_ok=True)
        self.mqtt_db = os.path.join(iot_dir, "mqtt_buffer.db")
        conn_iot = sqlite3.connect(self.mqtt_db)
        conn_iot.execute("""
            CREATE TABLE buffered_messages (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                idempotency_key TEXT UNIQUE,
                created_at REAL NOT NULL,
                dispatched INTEGER DEFAULT 0
            )
        """)
        conn_iot.execute("""
            INSERT INTO buffered_messages VALUES (
                'msg_001', 'devices/light/state', '{"state": "ON"}',
                'idem_key_001', 1700000000.0, 0
            )
        """)
        conn_iot.commit()
        conn_iot.close()

        # 3. Create simulated Observability audit log
        obs_dir = os.path.join(self.temp_root, "services", "observability", "storage")
        os.makedirs(obs_dir, exist_ok=True)
        self.audit_log = os.path.join(obs_dir, "audit_log.jsonl")
        with open(self.audit_log, "w", encoding="utf-8") as f:
            f.write(json.dumps({"event": "SYSTEM_START", "timestamp": 1700000000.0, "actor": "JARVIS"}) + "\n")
            f.write(json.dumps({"event": "POLICY_CHECK", "timestamp": 1700000001.0, "actor": "AUTH_ENGINE"}) + "\n")

        # 4. Create config file
        self.config_file = os.path.join(self.temp_root, "pyproject.toml")
        with open(self.config_file, "w", encoding="utf-8") as f:
            f.write("[project]\nname = 'jarvis-agentos'\nversion = '2.0.0'\n")

        self.drill = DisasterRecoveryDrill(
            root_dir=self.temp_root,
            backup_dir=self.backup_dir,
            secret_key="test-secret-key-123",
            targets=[
                "services/planner/storage/missions.db",
                "services/iot_agent/storage/mqtt_buffer.db",
                "services/observability/storage/audit_log.jsonl",
                "pyproject.toml",
            ],
        )

        yield

        shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_disaster_drill_backup_generates_valid_checksums(self):
        """Invariant: Backup must generate valid SHA-256 hashes and a valid HMAC signature."""
        backup_res = self.drill.backup_all_state(label="test_checksum")
        assert backup_res["success"] is True
        assert os.path.exists(backup_res["backup_path"])

        manifest = backup_res["manifest"]
        assert manifest["manifest_version"] == "2.0"
        assert manifest["algorithm"] == "sha256"
        assert len(manifest["files"]) == 4

        # Validate HMAC signature
        assert self.drill._verify_manifest_signature(manifest) is True

        # Verify SHA-256 for each archived target against actual file on disk
        for rel_path, file_meta in manifest["files"].items():
            full_path = os.path.join(self.temp_root, rel_path)
            assert os.path.exists(full_path)

            expected_sha256 = compute_sha256_file(full_path)
            assert file_meta["sha256"] == expected_sha256
            assert len(file_meta["sha256"]) == 64
            assert file_meta["size_bytes"] == os.path.getsize(full_path)

    def test_disaster_drill_corruption_detected(self):
        """Invariant: Restoring a tampered or bit-rotted archive must be rejected."""
        backup_res = self.drill.backup_all_state(label="tamper_test")
        original_zip = backup_res["backup_path"]

        # Read zip contents
        tampered_zip = os.path.join(self.backup_dir, "tampered_archive.zip")
        with zipfile.ZipFile(original_zip, "r") as z_in:
            with zipfile.ZipFile(tampered_zip, "w") as z_out:
                for item in z_in.infolist():
                    data = z_in.read(item.filename)
                    if item.filename == "services/planner/storage/missions.db":
                        # Corrupt bytes inside the archived database
                        data = b"TAMPERED_MALICIOUS_BYTE_PAYLOAD_XX" + data[34:]
                    z_out.writestr(item, data)

        restore_dest = os.path.join(self.temp_root, "restore_tampered")
        restore_res = self.drill.restore_from_backup(tampered_zip, destination_dir=restore_dest)

        assert restore_res["success"] is False
        assert "services/planner/storage/missions.db" in restore_res["corrupted_files"]
        assert "Integrity check failed" in restore_res["error"]

        # Test manifest signature tampering detection
        tampered_manifest_zip = os.path.join(self.backup_dir, "tampered_manifest.zip")
        with zipfile.ZipFile(original_zip, "r") as z_in:
            manifest_data = json.loads(z_in.read("manifest.json").decode("utf-8"))
            # Alter signature
            manifest_data["signature"] = "deadbeef" * 8
            with zipfile.ZipFile(tampered_manifest_zip, "w") as z_out:
                for item in z_in.infolist():
                    if item.filename == "manifest.json":
                        z_out.writestr("manifest.json", json.dumps(manifest_data).encode("utf-8"))
                    else:
                        z_out.writestr(item, z_in.read(item.filename))

        restore_sig_res = self.drill.restore_from_backup(tampered_manifest_zip, destination_dir=restore_dest)
        assert restore_sig_res["success"] is False
        assert restore_sig_res["signature_valid"] is False
        assert "Manifest signature verification failed" in restore_sig_res["error"]

    def test_disaster_drill_restore_recovers_state(self):
        """Invariant: Backup -> Wipe -> Restore successfully restores 100% data and health."""
        # Step 1: Backup
        backup_res = self.drill.backup_all_state(label="restore_test")
        assert backup_res["success"] is True

        # Step 2: Wipe all target files
        disaster_res = self.drill.simulate_disaster(
            target_paths=[self.missions_db, self.mqtt_db, self.audit_log, self.config_file],
            mode="wipe",
        )
        assert disaster_res["success"] is True
        assert not os.path.exists(self.missions_db)
        assert not os.path.exists(self.mqtt_db)
        assert not os.path.exists(self.audit_log)
        assert not os.path.exists(self.config_file)

        # Step 3: Restore
        restore_res = self.drill.restore_from_backup(backup_res["backup_path"], destination_dir=self.temp_root)
        assert restore_res["success"] is True
        assert restore_res["restored_count"] == 4
        assert len(restore_res["corrupted_files"]) == 0

        # Step 4: Health Probes
        health = self.drill.verify_post_restore_health(target_dir=self.temp_root)
        assert health["all_healthy"] is True
        assert health["status"] == "100% ONLINE"
        assert health["system_status"] == "ONLINE"
        assert health["health_score"] == 100.0
        assert health["zero_data_loss"] is True

        # Verify SQLite contents
        with sqlite3.connect(self.missions_db) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            assert cur.fetchone()[0] == "ok"
            cur.execute("SELECT COUNT(*) FROM missions;")
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT COUNT(*) FROM checkpoints;")
            assert cur.fetchone()[0] == 1

        with sqlite3.connect(self.mqtt_db) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            assert cur.fetchone()[0] == "ok"
            cur.execute("SELECT COUNT(*) FROM buffered_messages;")
            assert cur.fetchone()[0] == 1

    def test_disaster_drill_full_cycle_pass(self):
        """Invariant: run_full_drill() executes full drill cycle and returns 100% ONLINE."""
        drill_workspace = os.path.join(self.temp_root, "drill_cycle_run")
        report = self.drill.run_full_drill(isolated_dir=drill_workspace)

        assert report["success"] is True
        assert report["system_status"] == "ONLINE"
        assert report["health_score"] == 100.0
        assert report["zero_data_loss"] is True
        assert report["summary"]["status"] == "100% ONLINE"
        assert report["summary"]["corrupted_files_detected_count"] == 0
        assert report["phases"]["backup"]["files_count"] >= 4
        assert report["phases"]["restore"]["signature_valid"] is True
        assert report["phases"]["health_probes"]["checks"]["sqlite_integrity"]["status"] == "PASS"

    def test_disaster_drill_simulate_corruption_detection(self):
        """Invariant: Post-restore health probe detects SQLite byte corruption."""
        # Simulate corrupting missions.db
        with open(self.missions_db, "r+b") as f:
            f.seek(0)
            f.write(b"CORRUPTED_DISASTER_INJECTION_" + b"\x00\xff" * 16)

        health = self.drill.verify_post_restore_health(target_dir=self.temp_root)
        assert health["all_healthy"] is False
        assert health["zero_data_loss"] is False
        assert health["system_status"] == "DEGRADED"
        assert health["health_score"] < 100.0
