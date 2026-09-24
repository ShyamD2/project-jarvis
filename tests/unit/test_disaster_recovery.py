"""
Unit Test: Disaster Recovery, Database Migrations & Backup Verification (Item 8).
Verifies:
  1. MigrationRunner executes migrations idempotently.
  2. DisasterRecoveryManager creates archives with SHA-256 manifest.
  3. Verify validates file checksums against manifest.
  4. Restore unpacks files safely.
"""

import unittest
import os
import shutil
import tempfile
from migrations.migrate import MigrationRunner
from scripts.backup import DisasterRecoveryManager


class TestDisasterRecovery(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_jarvis.db")
        self.backup_dir = os.path.join(self.temp_dir, "backups")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_migration_runner_idempotency(self):
        """Invariant: Running migrations twice produces zero extra executions."""
        runner = MigrationRunner(db_path=self.db_path)
        first_run = runner.run_all()
        self.assertGreater(first_run, 0)

        # Second run must apply 0
        second_run = runner.run_all()
        self.assertEqual(second_run, 0)

        applied = runner.get_applied_migrations()
        self.assertIn("v001_initial_schema.sql", applied)
        self.assertIn("v002_memory_provenance.sql", applied)
        self.assertIn("v003_audit_ledger.sql", applied)

    def test_backup_create_verify_and_restore(self):
        """Invariant: Backup archive contains valid SHA-256 manifest and verifies 100%."""
        # Create a sample file to backup
        data_dir = os.path.join(self.temp_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        sample_file = os.path.join(data_dir, "jarvis_main.db")
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write("sqlite format 3 header test data")

        mgr = DisasterRecoveryManager(root_dir=self.temp_dir, backup_dir=self.backup_dir)
        res = mgr.create_backup(label="unit_test")
        self.assertTrue(res["success"])
        archive_path = res["archive_path"]
        self.assertTrue(os.path.exists(archive_path))

        # Verify archive
        verification = mgr.verify_backup(archive_path)
        self.assertTrue(verification["valid"], f"Verification failed: {verification.get('error')}")
        self.assertGreater(verification["total_files_verified"], 0)

        # Restore archive into a clean destination
        restore_dir = os.path.join(self.temp_dir, "restored")
        restore_res = mgr.restore_backup(archive_path, target_dir=restore_dir)
        self.assertTrue(restore_res["success"])
        restored_file = os.path.join(restore_dir, "data", "jarvis_main.db")
        self.assertTrue(os.path.exists(restored_file))
        with open(restored_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "sqlite format 3 header test data")


if __name__ == "__main__":
    unittest.main()
