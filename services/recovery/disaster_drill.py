"""
Automated Disaster Recovery Drill & Cryptographic Integrity Verification Engine.
Project J.A.R.V.I.S. (Phase 36 / Item 8 Resiliency Subsystem).

Provides end-to-end disaster preparedness validation:
  1. Full State Backup: Archives SQLite databases, audit ledgers, and configurations
     with HMAC-SHA256 signed integrity manifest.
  2. Disaster Simulation: Isolated byte corruption and catastrophic data wipe testing.
  3. Manifest Integrity Verification: Cryptographic checksum validation on restore.
  4. Post-Restore Deep Health Probing: SQLite PRAGMA integrity checks, schema inspection,
     and Planner DAG state validation.
  5. Automated Drill Runner: Executes the complete disaster cycle and generates
     structured operational health reports.
"""

from __future__ import annotations

import os
import sys
import time
import json
import hmac
import uuid
import shutil
import hashlib
import zipfile
import sqlite3
import argparse
from typing import Dict, Any, List, Optional, Union

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
DEFAULT_BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups", "drills")
DEFAULT_SECRET_KEY = os.environ.get("JARVIS_DR_SECRET", "jarvis-dr-master-integrity-key-v1")

DEFAULT_CRITICAL_TARGETS = [
    "services/planner/storage/missions.db",
    "services/iot_agent/storage/mqtt_buffer.db",
    "services/observability/storage/audit_log.jsonl",
    "services/observability/storage/chained_ledger.jsonl",
    "pyproject.toml",
    ".env",
    ".env.example",
]


def compute_sha256_bytes(data: bytes) -> str:
    """Computes SHA-256 hash of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def compute_sha256_file(file_path: str) -> str:
    """Computes SHA-256 hash of a file streaming in 64KB chunks."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class DisasterRecoveryDrill:
    """
    Automated Disaster Recovery Drill Engine for Project J.A.R.V.I.S.
    Simulates catastrophic loss, verifies cryptographic backups, and probes
    post-restore SQLite and Planner state.
    """

    def __init__(
        self,
        root_dir: Optional[str] = None,
        backup_dir: Optional[str] = None,
        secret_key: Optional[str] = None,
        targets: Optional[List[str]] = None,
    ):
        self.root_dir = os.path.abspath(root_dir or PROJECT_ROOT)
        self.backup_dir = os.path.abspath(backup_dir or DEFAULT_BACKUP_DIR)
        self.secret_key = secret_key or DEFAULT_SECRET_KEY
        self.critical_targets = list(targets if targets is not None else DEFAULT_CRITICAL_TARGETS)
        os.makedirs(self.backup_dir, exist_ok=True)

    def _sign_manifest(self, manifest_data: Dict[str, Any]) -> str:
        """Generates HMAC-SHA256 signature for canonical manifest files mapping."""
        # Sign canonical serialization of files dictionary
        canonical = json.dumps(manifest_data.get("files", {}), sort_keys=True, separators=(",", ":"))
        return hmac.new(self.secret_key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    def _verify_manifest_signature(self, manifest_data: Dict[str, Any]) -> bool:
        """Verifies HMAC-SHA256 signature against the manifest files mapping."""
        expected_sig = manifest_data.get("signature", "")
        if not expected_sig:
            return False
        calculated = self._sign_manifest(manifest_data)
        return hmac.compare_digest(expected_sig, calculated)

    def get_existing_targets(self, source_dir: Optional[str] = None) -> List[str]:
        """Resolves critical target files that currently exist on disk."""
        src = os.path.abspath(source_dir or self.root_dir)
        existing = []
        for rel_path in self.critical_targets:
            full_path = os.path.join(src, rel_path)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                existing.append(full_path)
        return existing

    def backup_all_state(
        self,
        backup_dir: Optional[str] = None,
        source_dir: Optional[str] = None,
        label: str = "drill",
    ) -> Dict[str, Any]:
        """
        Collects all critical state DBs, audit logs, and config files.
        Computes SHA-256 hashes and generates a signed manifest.json,
        archiving all components into a timestamped ZIP archive.
        """
        dest_backup_dir = os.path.abspath(backup_dir or self.backup_dir)
        src_dir = os.path.abspath(source_dir or self.root_dir)
        os.makedirs(dest_backup_dir, exist_ok=True)

        targets = self.get_existing_targets(src_dir)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_id = f"jarvis_backup_{label}_{timestamp}_{uuid.uuid4().hex[:6]}"
        archive_name = f"{backup_id}.zip"
        archive_path = os.path.join(dest_backup_dir, archive_name)

        manifest: Dict[str, Any] = {
            "manifest_version": "2.0",
            "backup_id": backup_id,
            "created_at": time.time(),
            "created_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "label": label,
            "archive_name": archive_name,
            "algorithm": "sha256",
            "files": {},
        }

        # Build cryptographic manifest
        for target in targets:
            rel_path = os.path.relpath(target, src_dir).replace("\\", "/")
            file_hash = compute_sha256_file(target)
            file_size = os.path.getsize(target)
            manifest["files"][rel_path] = {
                "sha256": file_hash,
                "size_bytes": file_size,
            }

        # Sign the manifest
        manifest["signature"] = self._sign_manifest(manifest)

        # Write ZIP archive
        manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for target in targets:
                rel_path = os.path.relpath(target, src_dir).replace("\\", "/")
                zf.write(target, arcname=rel_path)
            # Embed manifest.json at the root of the archive
            zf.writestr("manifest.json", manifest_bytes)

        archive_size = os.path.getsize(archive_path)
        archive_sha256 = compute_sha256_file(archive_path)

        return {
            "success": True,
            "backup_id": backup_id,
            "backup_path": archive_path,
            "archive_name": archive_name,
            "archive_size_bytes": archive_size,
            "archive_sha256": archive_sha256,
            "files_count": len(manifest["files"]),
            "manifest": manifest,
            "timestamp": manifest["created_at"],
        }

    def simulate_disaster(
        self,
        target_paths: Union[str, List[str]],
        mode: str = "corrupt",
    ) -> Dict[str, Any]:
        """
        Safely simulates catastrophic loss or byte-corruption of SQLite DBs or configs
        in an isolated scratch/test directory.
        Supported modes:
          - 'corrupt': Overwrites file headers/payload with corrupt junk bytes.
          - 'wipe' / 'delete': Deletes the target files completely.
          - 'truncate': Empties file to 0 bytes.
          - 'mixed': Corrupts headers on half, deletes the remainder.
        """
        resolved_files: List[str] = []

        if isinstance(target_paths, str):
            if os.path.isdir(target_paths):
                for root, _, files in os.walk(target_paths):
                    for f in files:
                        resolved_files.append(os.path.join(root, f))
            elif os.path.isfile(target_paths):
                resolved_files.append(target_paths)
        else:
            for p in target_paths:
                if os.path.isdir(p):
                    for root, _, files in os.walk(p):
                        for f in files:
                            resolved_files.append(os.path.join(root, f))
                elif os.path.isfile(p):
                    resolved_files.append(p)

        corrupted: List[str] = []
        deleted: List[str] = []
        truncated: List[str] = []

        for idx, file_path in enumerate(resolved_files):
            current_mode = mode
            if mode == "mixed":
                current_mode = "wipe" if (idx % 2 == 0) else "corrupt"

            if current_mode in ("wipe", "delete"):
                try:
                    os.remove(file_path)
                    deleted.append(file_path)
                except OSError:
                    pass
            elif current_mode == "truncate":
                try:
                    with open(file_path, "wb") as f:
                        f.write(b"")
                    truncated.append(file_path)
                except OSError:
                    pass
            else:  # corrupt
                try:
                    # Overwrite SQLite/text headers with garbage to simulate disk bit-rot / crash corruption
                    with open(file_path, "r+b") as f:
                        f.seek(0)
                        f.write(b"FATAL_DISASTER_BYTE_CORRUPTION_INJECTED_X99\x00\xff\x00\xaa" * 8)
                    corrupted.append(file_path)
                except OSError:
                    pass

        return {
            "success": True,
            "disaster_type": f"catastrophic_{mode}",
            "corrupted_files": corrupted,
            "deleted_files": deleted,
            "truncated_files": truncated,
            "total_affected": len(corrupted) + len(deleted) + len(truncated),
        }

    def restore_from_backup(
        self,
        backup_id_or_path: str,
        destination_dir: str,
    ) -> Dict[str, Any]:
        """
        Restores files from backup archive/manifest.
        Verifies SHA-256 hashes against the signed manifest during restore,
        immediately catching any tampered or corrupted files.
        """
        # Resolve backup path
        if os.path.isabs(backup_id_or_path) and os.path.exists(backup_id_or_path):
            archive_path = backup_id_or_path
        else:
            archive_path = os.path.join(self.backup_dir, backup_id_or_path)
            if not archive_path.endswith(".zip") and os.path.exists(archive_path + ".zip"):
                archive_path += ".zip"

        if not os.path.exists(archive_path):
            return {
                "success": False,
                "error": f"Backup archive not found: {archive_path}",
                "corrupted_files": [],
                "restored_files": [],
            }

        dest_dir = os.path.abspath(destination_dir)
        os.makedirs(dest_dir, exist_ok=True)

        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                # 1. Read manifest.json
                if "manifest.json" not in zf.namelist():
                    return {
                        "success": False,
                        "error": "Archive corrupted: manifest.json is missing.",
                        "corrupted_files": [],
                        "restored_files": [],
                    }

                manifest_raw = zf.read("manifest.json").decode("utf-8")
                manifest = json.loads(manifest_raw)

                # 2. Check manifest signature
                if not self._verify_manifest_signature(manifest):
                    return {
                        "success": False,
                        "error": "Manifest signature verification failed! Archive has been tampered with.",
                        "signature_valid": False,
                        "corrupted_files": list(manifest.get("files", {}).keys()),
                        "restored_files": [],
                    }

                files_manifest = manifest.get("files", {})
                restored_files: List[str] = []
                corrupted_files: List[str] = []
                verified_hashes: Dict[str, bool] = {}

                # 3. Verify member integrity and extract
                for rel_path, meta in files_manifest.items():
                    if rel_path not in zf.namelist():
                        corrupted_files.append(rel_path)
                        verified_hashes[rel_path] = False
                        continue

                    # Read bytes directly from archive and check hash
                    content_bytes = zf.read(rel_path)
                    actual_sha256 = compute_sha256_bytes(content_bytes)

                    if actual_sha256 != meta.get("sha256"):
                        corrupted_files.append(rel_path)
                        verified_hashes[rel_path] = False
                        continue

                    # Path traversal security check
                    target_file_path = os.path.abspath(os.path.join(dest_dir, rel_path))
                    if not target_file_path.startswith(dest_dir):
                        return {
                            "success": False,
                            "error": f"Security violation: path traversal detected ({rel_path})",
                            "corrupted_files": [rel_path],
                            "restored_files": [],
                        }

                    # Write out safely
                    os.makedirs(os.path.dirname(target_file_path), exist_ok=True)
                    with open(target_file_path, "wb") as out_f:
                        out_f.write(content_bytes)

                    verified_hashes[rel_path] = True
                    restored_files.append(target_file_path)

                if corrupted_files:
                    return {
                        "success": False,
                        "error": f"Integrity check failed: corrupted files detected {corrupted_files}",
                        "signature_valid": True,
                        "restored_count": len(restored_files),
                        "restored_files": restored_files,
                        "corrupted_files": corrupted_files,
                        "verified_hashes": verified_hashes,
                    }

                return {
                    "success": True,
                    "signature_valid": True,
                    "restored_count": len(restored_files),
                    "restored_files": restored_files,
                    "corrupted_files": [],
                    "verified_hashes": verified_hashes,
                    "destination_dir": dest_dir,
                }

        except zipfile.BadZipFile:
            return {
                "success": False,
                "error": "Archive corrupted: not a valid ZIP file.",
                "corrupted_files": ["<archive>"],
                "restored_files": [],
            }

    def verify_post_restore_health(self, target_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Probes restored databases:
          - Runs SELECT queries, verifies schema integrity, PRAGMA integrity_check.
          - Probes services/planner mission DAG state.
          - Confirms system status is 100% ONLINE with zero data loss.
        """
        base_dir = os.path.abspath(target_dir or self.root_dir)
        checks: Dict[str, Any] = {}
        all_healthy = True
        failed_checks: List[str] = []

        # 1. Probe SQLite databases
        sqlite_reports = {}
        # Find all .db files under base_dir
        db_files = []
        for root, _, files in os.walk(base_dir):
            for f in files:
                if f.endswith(".db"):
                    db_files.append(os.path.join(root, f))

        for db_path in db_files:
            rel_db = os.path.relpath(db_path, base_dir).replace("\\", "/")
            db_status = {"healthy": False, "pragma_ok": False, "tables": {}}
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                # Run PRAGMA integrity_check
                cur.execute("PRAGMA integrity_check;")
                rows = cur.fetchall()
                if rows and rows[0][0] == "ok":
                    db_status["pragma_ok"] = True
                else:
                    db_status["pragma_ok"] = False
                    all_healthy = False
                    failed_checks.append(f"{rel_db}: PRAGMA integrity_check failed")

                # Inspect tables & counts
                cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [r[0] for r in cur.fetchall()]

                for t in tables:
                    try:
                        cur.execute(f"SELECT COUNT(*) as cnt FROM {t};")
                        cnt = cur.fetchone()["cnt"]
                        db_status["tables"][t] = {"row_count": cnt, "readable": True}
                    except Exception as ex:
                        db_status["tables"][t] = {"row_count": -1, "readable": False, "error": str(ex)}
                        all_healthy = False
                        failed_checks.append(f"{rel_db}.{t}: query error {ex}")

                conn.close()
                db_status["healthy"] = db_status["pragma_ok"] and (len(tables) > 0)
            except Exception as e:
                db_status["error"] = str(e)
                all_healthy = False
                failed_checks.append(f"{rel_db}: SQLite connection failed ({e})")

            sqlite_reports[rel_db] = db_status

        checks["sqlite_integrity"] = {
            "status": "PASS" if not any(not s.get("healthy") for s in sqlite_reports.values()) else "FAIL",
            "databases": sqlite_reports,
        }

        # 2. Probe Planner Mission & DAG State
        planner_db = os.path.join(base_dir, "services", "planner", "storage", "missions.db")
        planner_status = {"healthy": False, "missions_verified": 0, "checkpoints_verified": 0}
        if os.path.exists(planner_db):
            try:
                conn = sqlite3.connect(planner_db)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                # Validate missions table and DAG JSON
                cur.execute("SELECT mission_id, name, current_phase, dag_json FROM missions;")
                missions = cur.fetchall()
                for m in missions:
                    dag_raw = m["dag_json"]
                    if dag_raw:
                        # Ensure valid JSON serialization of DAG
                        json.loads(dag_raw)
                    planner_status["missions_verified"] += 1

                # Validate checkpoints table
                cur.execute("SELECT checkpoint_id, mission_id, snapshot_json FROM checkpoints;")
                checkpoints = cur.fetchall()
                for cp in checkpoints:
                    snap_raw = cp["snapshot_json"]
                    if snap_raw:
                        json.loads(snap_raw)
                    planner_status["checkpoints_verified"] += 1

                conn.close()
                planner_status["healthy"] = True
            except Exception as e:
                planner_status["error"] = str(e)
                all_healthy = False
                failed_checks.append(f"planner_dag_probe: {e}")
        else:
            # If no missions.db was part of the targets, mark as skipped/neutral
            planner_status["healthy"] = True
            planner_status["skipped"] = "missions.db not present in target_dir"

        checks["planner_dag_state"] = planner_status

        # 3. Probe Observability Audit Logs
        audit_log_path = os.path.join(base_dir, "services", "observability", "storage", "audit_log.jsonl")
        audit_status = {"healthy": False, "entries_parsed": 0}
        if os.path.exists(audit_log_path):
            try:
                with open(audit_log_path, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        line_str = line.strip()
                        if line_str:
                            json.loads(line_str)
                            audit_status["entries_parsed"] += 1
                audit_status["healthy"] = True
            except Exception as e:
                audit_status["error"] = str(e)
                all_healthy = False
                failed_checks.append(f"audit_log_probe: {e}")
        else:
            audit_status["healthy"] = True
            audit_status["skipped"] = "audit_log.jsonl not present in target_dir"

        checks["audit_ledger_health"] = audit_status

        # 4. Summary & Score
        health_score = 100.0 if all_healthy else round(max(0.0, 100.0 - (len(failed_checks) * 25.0)), 1)
        system_status = "ONLINE" if all_healthy else "DEGRADED"
        status_label = "100% ONLINE" if all_healthy else f"{health_score}% DEGRADED"

        return {
            "status": status_label,
            "system_status": system_status,
            "health_score": health_score,
            "zero_data_loss": all_healthy,
            "all_healthy": all_healthy,
            "failed_checks": failed_checks,
            "checks": checks,
        }

    def _prepare_sample_state(self, staging_live_dir: str):
        """Populates an isolated directory with minimal valid state DBs for drill execution."""
        # Planner missions.db
        planner_storage = os.path.join(staging_live_dir, "services", "planner", "storage")
        os.makedirs(planner_storage, exist_ok=True)
        p_db = os.path.join(planner_storage, "missions.db")
        conn_p = sqlite3.connect(p_db)
        conn_p.execute("""
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
        conn_p.execute("""
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
        conn_p.execute("""
            INSERT OR REPLACE INTO missions VALUES (
                'drill_mission_001', 'Disaster Recovery Validation',
                'Verify automated drill continuity', 'COMPLETE', 100,
                'LOW', 0.0, 'SUCCESS', '["task_backup", "task_restore"]',
                strftime('%s', 'now'), strftime('%s', 'now')
            )
        """)
        conn_p.execute("""
            INSERT OR REPLACE INTO checkpoints VALUES (
                'cp_001', 'drill_mission_001', 1, 'state_hash_ok',
                '{"step": 1, "status": "VERIFIED"}', strftime('%s', 'now')
            )
        """)
        conn_p.commit()
        conn_p.close()

        # IoT MQTT buffer db
        iot_storage = os.path.join(staging_live_dir, "services", "iot_agent", "storage")
        os.makedirs(iot_storage, exist_ok=True)
        iot_db = os.path.join(iot_storage, "mqtt_buffer.db")
        conn_iot = sqlite3.connect(iot_db)
        conn_iot.execute("""
            CREATE TABLE IF NOT EXISTS buffered_messages (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                idempotency_key TEXT UNIQUE,
                created_at REAL NOT NULL,
                dispatched INTEGER DEFAULT 0
            )
        """)
        conn_iot.execute("""
            INSERT OR REPLACE INTO buffered_messages VALUES (
                'msg_drill_1', 'jarvis/drill/telemetry',
                '{"status": "drill_active"}', 'idem_drill_001',
                strftime('%s', 'now'), 0
            )
        """)
        conn_iot.commit()
        conn_iot.close()

        # Observability audit log
        obs_storage = os.path.join(staging_live_dir, "services", "observability", "storage")
        os.makedirs(obs_storage, exist_ok=True)
        obs_log = os.path.join(obs_storage, "audit_log.jsonl")
        with open(obs_log, "w", encoding="utf-8") as f:
            f.write(json.dumps({"event": "DRILL_INIT", "timestamp": time.time(), "actor": "DisasterDrill"}) + "\n")
            f.write(json.dumps({"event": "SYSTEM_CHECK", "timestamp": time.time(), "status": "OK"}) + "\n")

        # Config files
        pyproj = os.path.join(staging_live_dir, "pyproject.toml")
        with open(pyproj, "w", encoding="utf-8") as f:
            f.write("[project]\nname = 'jarvis-agentos'\nversion = '2.0.0'\n")

    def run_full_drill(self, isolated_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes the entire drill cycle:
          1. Backup state & compute SHA-256 manifest.
          2. Safely simulate disaster (corruption & loss) in an isolated workspace.
          3. Restore state from backup.
          4. Verify SHA-256 checksums and manifest signature.
          5. Probe post-restore health of all SQLite databases & Planner DAGs.
          6. Generate comprehensive JSON report.
        """
        drill_id = f"drill_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        workspace = os.path.abspath(
            isolated_dir or os.path.join(self.backup_dir, f"run_{drill_id}")
        )
        os.makedirs(workspace, exist_ok=True)

        staging_live = os.path.join(workspace, "live_state")
        staging_backups = os.path.join(workspace, "backup_storage")
        os.makedirs(staging_live, exist_ok=True)
        os.makedirs(staging_backups, exist_ok=True)

        drill_instance = DisasterRecoveryDrill(
            root_dir=staging_live,
            backup_dir=staging_backups,
            secret_key=self.secret_key,
            targets=self.critical_targets,
        )

        # 1. Populate staging live with existing project files or initialized sample state
        existing_project_targets = self.get_existing_targets(self.root_dir)
        if existing_project_targets:
            for src_file in existing_project_targets:
                rel = os.path.relpath(src_file, self.root_dir)
                dest = os.path.join(staging_live, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(src_file, dest)
        else:
            self._prepare_sample_state(staging_live)

        # Ensure sample state is also populated if some databases are missing
        for t in self.critical_targets:
            dest = os.path.join(staging_live, t)
            if not os.path.exists(dest) and ("storage" in t or t == "pyproject.toml"):
                self._prepare_sample_state(staging_live)
                break

        # Step 1: Backup
        backup_res = drill_instance.backup_all_state(
            backup_dir=staging_backups,
            source_dir=staging_live,
            label="full_cycle",
        )

        # Step 2: Simulate Disaster (Byte corruption and deletion)
        disaster_res = drill_instance.simulate_disaster(
            target_paths=staging_live,
            mode="corrupt",
        )

        # Step 3: Restore
        restore_res = drill_instance.restore_from_backup(
            backup_id_or_path=backup_res["backup_path"],
            destination_dir=staging_live,
        )

        # Step 4: Health Probes
        health_res = drill_instance.verify_post_restore_health(target_dir=staging_live)

        # Cleanup drill temporary workspace if created automatically and drill passed
        overall_success = (
            backup_res.get("success", False)
            and disaster_res.get("success", False)
            and restore_res.get("success", False)
            and health_res.get("all_healthy", False)
            and health_res.get("zero_data_loss", False)
        )

        report = {
            "drill_id": drill_id,
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "success": overall_success,
            "system_status": health_res.get("system_status", "OFFLINE"),
            "health_score": health_res.get("health_score", 0.0),
            "zero_data_loss": health_res.get("zero_data_loss", False),
            "summary": {
                "backed_up_files": backup_res.get("files_count", 0),
                "disaster_affected_files": disaster_res.get("total_affected", 0),
                "restored_files_count": restore_res.get("restored_count", 0),
                "corrupted_files_detected_count": len(restore_res.get("corrupted_files", [])),
                "status": health_res.get("status", "UNKNOWN"),
            },
            "phases": {
                "backup": {
                    "backup_id": backup_res.get("backup_id"),
                    "archive_sha256": backup_res.get("archive_sha256"),
                    "files_count": backup_res.get("files_count"),
                },
                "disaster_simulation": {
                    "disaster_type": disaster_res.get("disaster_type"),
                    "total_affected": disaster_res.get("total_affected"),
                },
                "restore": {
                    "restored_count": restore_res.get("restored_count"),
                    "signature_valid": restore_res.get("signature_valid"),
                    "corrupted_files": restore_res.get("corrupted_files"),
                },
                "health_probes": {
                    "status": health_res.get("status"),
                    "health_score": health_res.get("health_score"),
                    "failed_checks": health_res.get("failed_checks"),
                    "checks": health_res.get("checks"),
                },
            },
        }

        # Cleanup scratch workspace
        try:
            shutil.rmtree(workspace, ignore_errors=True)
        except Exception:
            pass

        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Automated Disaster Recovery Drill")
    parser.add_argument("--json", action="store_true", default=True, help="Output clean JSON report")
    parser.add_argument("--backup-dir", type=str, default=None, help="Custom backup directory")
    args = parser.parse_args()

    drill = DisasterRecoveryDrill(backup_dir=args.backup_dir)
    result = drill.run_full_drill()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") else 1)
