"""
Production SQLite Database Utility for Project J.A.R.V.I.S. (Phase 2 Reliability & Concurrency).
Enforces Write-Ahead Logging (WAL), high concurrency busy timeouts (30s),
and clean checkpointing across all service databases.
"""

from __future__ import annotations
import os
import sqlite3
from typing import Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisDatabase")


def get_sqlite_connection(
    db_path: str,
    timeout: float = 30.0,
    enable_wal: bool = True
) -> sqlite3.Connection:
    """
    Returns an ACID, high-concurrency SQLite connection configured with WAL mode
    and 30,000ms busy timeout to prevent 'database is locked' errors.
    """
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    
    conn = sqlite3.connect(
        db_path,
        timeout=timeout,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row

    if enable_wal:
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception as e:
            logger.debug(f"[Database] Notice setting SQLite pragmas on {db_path}: {e}")

    return conn


def checkpoint_sqlite_db(db_path: str) -> bool:
    """
    Executes a WAL checkpoint (TRUNCATE) on the database file to ensure
    all journal pages are flushed to disk cleanly during backup or shutdown.
    """
    if not os.path.exists(db_path):
        return True
    try:
        with get_sqlite_connection(db_path, enable_wal=False) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.commit()
        return True
    except Exception as e:
        logger.warning(f"[Database] WAL checkpoint failed for {db_path}: {e}")
        return False
