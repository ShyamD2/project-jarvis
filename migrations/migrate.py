"""
Database Migration Runner for Project J.A.R.V.I.S.
Applies versioned schema migrations (.sql) idempotently in strict alphabetical order.
Tracks applied versions in the `schema_migrations` table with SHA-256 integrity checksums.
"""

from __future__ import annotations
import os
import sys
import sqlite3
import hashlib
import time
from typing import List, Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "jarvis_main.db")


class MigrationRunner:
    def __init__(self, db_path: Optional[str] = None, migrations_dir: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.migrations_dir = migrations_dir or os.path.dirname(__file__)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_migrations_table()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_migrations_table(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    checksum TEXT NOT NULL
                )
            """)
            conn.commit()

    def get_applied_migrations(self) -> Dict[str, str]:
        """Returns dict of {version: checksum} for all applied migrations."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT version, checksum FROM schema_migrations ORDER BY version ASC")
            return {row["version"]: row["checksum"] for row in cursor.fetchall()}

    def get_pending_migrations(self) -> List[str]:
        """Returns list of migration filenames that have not yet been applied."""
        applied = self.get_applied_migrations()
        all_files = sorted([
            f for f in os.listdir(self.migrations_dir)
            if f.endswith(".sql") and f.startswith("v")
        ])
        return [f for f in all_files if f not in applied]

    def apply_migration(self, filename: str) -> bool:
        """Executes a single migration script and records it."""
        path = os.path.join(self.migrations_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Adapt Postgres types to SQLite if running embedded
        sql_content = content.replace("DOUBLE PRECISION", "REAL")
        sql_content = sql_content.replace("VARCHAR(", "TEXT(").replace("BOOLEAN", "INTEGER")

        with self._get_connection() as conn:
            conn.executescript(sql_content)
            conn.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
                (filename, checksum)
            )
            conn.commit()

        print(f"[OK] [Migration] Applied: {filename} (Checksum: {checksum[:8]}...)")
        return True

    def run_all(self) -> int:
        """Applies all pending migrations in order."""
        pending = self.get_pending_migrations()
        if not pending:
            print("Everything up to date. Zero pending migrations.")
            return 0

        print(f"Applying {len(pending)} pending migrations...")
        for filename in pending:
            self.apply_migration(filename)
        return len(pending)


if __name__ == "__main__":
    runner = MigrationRunner()
    count = runner.run_all()
    print(f"Migrations completed successfully. Applied: {count}")
