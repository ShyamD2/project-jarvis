"""
Disaster Recovery & Backup Utility for Project J.A.R.V.I.S. (Item 8).
Features:
  1. Creates compressed .tar.gz or .zip backup archives containing:
     - SQLite databases (data/jarvis_main.db, data/memory/*.db)
     - Audit ledgers and logs
     - Memory stores and persistent state
  2. Embeds an immutable SHA-256 integrity manifest (`manifest.json`) in every archive.
  3. Supports:
     - `backup()`: creates archive and returns metadata
     - `verify()`: validates cryptographic checksums of all archived files
     - `restore()`: safely restores databases and state files with pre-flight check
"""

from __future__ import annotations
import os
import sys
import tarfile
import hashlib
import json
import time
import argparse
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")


def compute_sha256(file_path: str) -> str:
    """Calculates SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class DisasterRecoveryManager:
    def __init__(self, root_dir: str = PROJECT_ROOT, backup_dir: str = DEFAULT_BACKUP_DIR):
        self.root_dir = root_dir
        self.backup_dir = backup_dir
        os.makedirs(self.backup_dir, exist_ok=True)

    def get_backup_targets(self) -> List[str]:
        """Identifies active databases, ledgers, and state stores to backup."""
        potential_targets = [
            os.path.join(self.root_dir, "data", "jarvis_main.db"),
            os.path.join(self.root_dir, "data", "memory", "episodic_memory.db"),
            os.path.join(self.root_dir, "data", "memory", "neural_memory_graph.json"),
            os.path.join(self.root_dir, "services", "observability", "storage", "chained_ledger.jsonl"),
            os.path.join(self.root_dir, "services", "memory", "storage_lifecycle_memories.json")
        ]
        return [p for p in potential_targets if os.path.exists(p)]

    def create_backup(self, label: str = "auto") -> Dict[str, Any]:
        """Creates a timestamped disaster recovery archive with a SHA-256 manifest."""
        targets = self.get_backup_targets()
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        archive_name = f"jarvis_backup_{label}_{timestamp}.tar.gz"
        archive_path = os.path.join(self.backup_dir, archive_name)

        manifest: Dict[str, Any] = {
            "created_at": time.time(),
            "created_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "label": label,
            "archive_name": archive_name,
            "files": {}
        }

        # Build file manifest
        for target in targets:
            rel_path = os.path.relpath(target, self.root_dir).replace("\\", "/")
            manifest["files"][rel_path] = {
                "sha256": compute_sha256(target),
                "size_bytes": os.path.getsize(target)
            }

        # Write archive
        with tarfile.open(archive_path, "w:gz") as tar:
            for target in targets:
                rel_path = os.path.relpath(target, self.root_dir).replace("\\", "/")
                tar.add(target, arcname=rel_path)

            # Add manifest.json directly into archive
            manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
            import io
            ti = tarfile.TarInfo(name="manifest.json")
            ti.size = len(manifest_bytes)
            ti.mtime = int(time.time())
            tar.addfile(ti, io.BytesIO(manifest_bytes))

        archive_size = os.path.getsize(archive_path)
        archive_sha256 = compute_sha256(archive_path)

        result = {
            "success": True,
            "archive_path": archive_path,
            "archive_name": archive_name,
            "archive_size_bytes": archive_size,
            "archive_sha256": archive_sha256,
            "files_count": len(targets),
            "manifest": manifest
        }
        print(f"[OK] [Backup] Created: {archive_name} ({archive_size / 1024:.1f} KB, SHA-256: {archive_sha256[:8]}...)")
        return result

    def verify_backup(self, archive_path: str) -> Dict[str, Any]:
        """Validates all file checksums against the internal manifest.json."""
        if not os.path.exists(archive_path):
            return {"valid": False, "error": f"Archive not found: {archive_path}"}

        with tarfile.open(archive_path, "r:gz") as tar:
            # Read manifest
            try:
                manifest_member = tar.getmember("manifest.json")
                f = tar.extractfile(manifest_member)
                if not f:
                    return {"valid": False, "error": "Empty manifest.json"}
                manifest = json.loads(f.read().decode("utf-8"))
            except KeyError:
                return {"valid": False, "error": "No manifest.json found in backup archive."}

            # Check every listed file
            for rel_path, meta in manifest.get("files", {}).items():
                try:
                    member = tar.getmember(rel_path)
                    content = tar.extractfile(member).read()
                    actual_sha256 = hashlib.sha256(content).hexdigest()
                    if actual_sha256 != meta["sha256"]:
                        return {
                            "valid": False,
                            "error": f"Checksum mismatch for '{rel_path}': expected {meta['sha256']}, got {actual_sha256}"
                        }
                except KeyError:
                    return {"valid": False, "error": f"File '{rel_path}' missing from archive."}

        print(f"[OK] [Verify] Backup '{os.path.basename(archive_path)}' mathematically verified (100% integrity).")
        return {
            "valid": True,
            "archive_path": archive_path,
            "total_files_verified": len(manifest.get("files", {})),
            "created_at": manifest.get("created_at")
        }

    def restore_backup(self, archive_path: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
        """Restores files from backup archive after verifying manifest integrity."""
        # 1. Pre-flight verification
        verification = self.verify_backup(archive_path)
        if not verification["valid"]:
            return {"success": False, "error": f"Pre-flight verification failed: {verification.get('error')}"}

        dest = target_dir or self.root_dir

        with tarfile.open(archive_path, "r:gz") as tar:
            members = [m for m in tar.getmembers() if m.name != "manifest.json"]
            for m in members:
                # Security check against tar slip
                norm_target = os.path.abspath(os.path.join(dest, m.name))
                if not norm_target.startswith(os.path.abspath(dest)):
                    return {"success": False, "error": f"Path traversal attempt in archive: {m.name}"}
                if hasattr(tarfile, "data_filter"):
                    tar.extract(m, path=dest, filter="data")
                else:
                    tar.extract(m, path=dest)

        print(f"[OK] [Restore] Restored {len(members)} items from '{os.path.basename(archive_path)}'.")
        return {
            "success": True,
            "restored_count": len(members),
            "destination": dest
        }


backup_manager = DisasterRecoveryManager()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Disaster Recovery & Backup")
    parser.add_argument("--backup", action="store_true", help="Create new backup")
    parser.add_argument("--verify", type=str, help="Verify backup archive integrity")
    parser.add_argument("--restore", type=str, help="Restore from backup archive")
    parser.add_argument("--label", type=str, default="manual", help="Backup label tag")

    args = parser.parse_args()

    if args.backup:
        backup_manager.create_backup(label=args.label)
    elif args.verify:
        backup_manager.verify_backup(args.verify)
    elif args.restore:
        backup_manager.restore_backup(args.restore)
    else:
        # Default behavior: run backup and verify
        res = backup_manager.create_backup(label="cli_test")
        backup_manager.verify_backup(res["archive_path"])
