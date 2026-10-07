"""
Cryptographic Proof of Execution Engine for Project J.A.R.V.I.S.
Generates immutable, tamper-evident cryptographic execution receipts for every action dispatched across
Computer, Physical, and Digital worlds. Provides SHA-256 canonical digest calculation, HMAC-SHA256 signing,
dual-channel verification audit recording, and append-only SQLite/JSONL ledger storage.
"""

from __future__ import annotations
import os
import json
import time
import uuid
import hmac
import hashlib
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisProofOfExecution")

CORE_RECEIPT_FIELDS = (
    "action_id",
    "request",
    "planned_action",
    "risk_tier",
    "authorization",
    "execution",
    "before_state",
    "after_state",
    "state_delta",
    "verification",
    "rollback",
    "final_status",
)


@dataclass(frozen=True)
class ExecutionReceipt:
    """
    Immutable Cryptographic Execution Receipt.
    Guarantees non-repudiation and tamper detection for all executed or blocked actions.
    """
    action_id: str
    request: str
    planned_action: str
    risk_tier: str
    authorization: Dict[str, Any]
    execution: Dict[str, Any]
    before_state: Dict[str, Any]
    after_state: Dict[str, Any]
    state_delta: Dict[str, Any]
    verification: Dict[str, Any]
    rollback: Dict[str, Any]
    final_status: str
    receipt_hash: str
    signature: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "request": self.request,
            "planned_action": self.planned_action,
            "risk_tier": self.risk_tier,
            "authorization": dict(self.authorization),
            "execution": dict(self.execution),
            "before_state": dict(self.before_state),
            "after_state": dict(self.after_state),
            "state_delta": dict(self.state_delta),
            "verification": dict(self.verification),
            "rollback": dict(self.rollback),
            "final_status": self.final_status,
            "receipt_hash": self.receipt_hash,
            "signature": self.signature,
        }

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()


class ProofOfExecutionEngine:
    """
    Cryptographic Proof-of-Execution Engine.
    Produces, signs, validates, and stores tamper-evident execution receipts.
    """

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        master_secret: Optional[str] = None
    ):
        if storage_dir:
            self.storage_dir = os.path.abspath(storage_dir)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.storage_dir = os.path.join(base_dir, "storage")

        os.makedirs(self.storage_dir, exist_ok=True)
        self.jsonl_path = os.path.join(self.storage_dir, "execution_receipts.jsonl")
        self.db_path = os.path.join(self.storage_dir, "execution_receipts.db")

        self._master_secret_override = master_secret
        self._lock = threading.Lock()
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initializes SQLite ledger database."""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS execution_receipts (
                            action_id TEXT PRIMARY KEY,
                            created_at REAL,
                            risk_tier TEXT,
                            final_status TEXT,
                            receipt_hash TEXT,
                            signature TEXT,
                            receipt_json TEXT
                        )
                    """)
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_receipts_created ON execution_receipts(created_at)"
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_receipts_status ON execution_receipts(final_status)"
                    )
                    conn.commit()
        except Exception as e:
            logger.warning(f"Failed to initialize SQLite ledger at {self.db_path}: {e}")

    def get_master_secret(self) -> str:
        """Retrieves JARVIS_MASTER_SECRET with fail-safe fallbacks."""
        if self._master_secret_override:
            return self._master_secret_override

        secret = os.getenv("JARVIS_MASTER_SECRET", "").strip()
        if not secret:
            try:
                from shared.sdk_python.jarvis_sdk.config import config
                secret = getattr(config, "master_secret", "").strip()
            except Exception:
                secret = ""

        if not secret:
            secret = "jarvis_default_master_secret_proof_of_execution_2026"
        return secret

    @staticmethod
    def compute_state_delta(
        before: Dict[str, Any],
        after: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculates differences between pre-execution and post-execution state snapshots."""
        b_dict = before if isinstance(before, dict) else {}
        a_dict = after if isinstance(after, dict) else {}
        delta: Dict[str, Any] = {}
        all_keys = set(b_dict.keys()) | set(a_dict.keys())
        for k in sorted(all_keys):
            b_val = b_dict.get(k)
            a_val = a_dict.get(k)
            if b_val != a_val:
                delta[k] = {"before": b_val, "after": a_val}
        return delta

    @staticmethod
    def compute_canonical_json(data: Dict[str, Any]) -> str:
        """Generates deterministic canonical JSON representation of core receipt fields."""
        core = {
            field: data.get(field)
            for field in CORE_RECEIPT_FIELDS
        }
        return json.dumps(core, sort_keys=True, separators=(',', ':'), default=str)

    @staticmethod
    def compute_receipt_hash(canonical_str: str) -> str:
        """Computes SHA-256 digest of canonical receipt string."""
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def compute_signature(self, canonical_str: str, secret: Optional[str] = None) -> str:
        """Computes HMAC-SHA256 signature over canonical receipt string."""
        sec = secret or self.get_master_secret()
        return hmac.new(
            sec.encode("utf-8"),
            canonical_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def compute_signature_over_hash(self, receipt_hash: str, secret: Optional[str] = None) -> str:
        """Computes HMAC-SHA256 signature over SHA-256 receipt hash."""
        sec = secret or self.get_master_secret()
        return hmac.new(
            sec.encode("utf-8"),
            receipt_hash.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def generate_receipt(
        self,
        action_id: str,
        request: str,
        planned_action: str,
        risk_tier: str,
        authorization: Optional[Dict[str, Any]] = None,
        execution: Optional[Dict[str, Any]] = None,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        state_delta: Optional[Dict[str, Any]] = None,
        verification: Optional[Dict[str, Any]] = None,
        rollback: Optional[Dict[str, Any]] = None,
        final_status: str = "VERIFIED",
        store: bool = True,
    ) -> ExecutionReceipt:
        """
        Generates an immutable cryptographic ExecutionReceipt for an action.
        Persists to disk if store=True.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # Format authorization dict
        auth_dict = {
            "lease_id": (authorization or {}).get("lease_id"),
            "nonce": (authorization or {}).get("nonce") or uuid.uuid4().hex,
            "authorized_by": (authorization or {}).get("authorized_by") or "OPERATOR",
            "parameter_hash": (authorization or {}).get("parameter_hash") or "",
        }

        # Format execution dict
        exec_dict = {
            "started_at": (execution or {}).get("started_at") or now_iso,
            "finished_at": (execution or {}).get("finished_at") or now_iso,
            "duration_ms": float((execution or {}).get("duration_ms", 0.0)),
            "exit_code": int((execution or {}).get("exit_code", 0)),
        }

        b_state = dict(before_state or {})
        a_state = dict(after_state or {})
        s_delta = (
            dict(state_delta)
            if state_delta is not None
            else self.compute_state_delta(b_state, a_state)
        )

        # Format verification dict
        verif_dict = {
            "logical": bool((verification or {}).get("logical", False)),
            "sensory": bool((verification or {}).get("sensory", False)),
            "state_match": bool((verification or {}).get("state_match", False)),
            "contract_mode": str((verification or {}).get("contract_mode", "logical_only")),
        }

        # Format rollback dict
        rb_dict = {
            "available": bool((rollback or {}).get("available", False)),
            "executed": bool((rollback or {}).get("executed", False)),
        }

        # Normalize final status
        status_norm = final_status.upper() if isinstance(final_status, str) else "FAILED"
        if status_norm in ("VERIFIED", "SUCCESS", "DISPATCHED"):
            final_status_val = "VERIFIED"
        elif status_norm in ("BLOCKED", "DENIED", "REJECTED"):
            final_status_val = "BLOCKED"
        else:
            final_status_val = "FAILED"

        core_payload = {
            "action_id": action_id,
            "request": request,
            "planned_action": planned_action,
            "risk_tier": risk_tier,
            "authorization": auth_dict,
            "execution": exec_dict,
            "before_state": b_state,
            "after_state": a_state,
            "state_delta": s_delta,
            "verification": verif_dict,
            "rollback": rb_dict,
            "final_status": final_status_val,
        }

        canonical_str = self.compute_canonical_json(core_payload)
        receipt_hash = self.compute_receipt_hash(canonical_str)
        signature = self.compute_signature(canonical_str)

        receipt = ExecutionReceipt(
            action_id=action_id,
            request=request,
            planned_action=planned_action,
            risk_tier=risk_tier,
            authorization=auth_dict,
            execution=exec_dict,
            before_state=b_state,
            after_state=a_state,
            state_delta=s_delta,
            verification=verif_dict,
            rollback=rb_dict,
            final_status=final_status_val,
            receipt_hash=receipt_hash,
            signature=signature,
        )

        if store:
            self.store_receipt(receipt)

        return receipt

    def store_receipt(
        self,
        receipt: Union[ExecutionReceipt, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Persists receipt to SQLite/JSON ledger in services/verification/storage/execution_receipts.jsonl
        and execution_receipts.db.
        """
        receipt_dict = receipt.to_dict() if hasattr(receipt, "to_dict") else dict(receipt)

        with self._lock:
            # 1. Append to JSONL file
            try:
                with open(self.jsonl_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(receipt_dict, default=str) + "\n")
            except Exception as e:
                logger.error(f"Failed to append receipt to JSONL at {self.jsonl_path}: {e}")

            # 2. Insert into SQLite table
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO execution_receipts
                        (action_id, created_at, risk_tier, final_status, receipt_hash, signature, receipt_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            receipt_dict.get("action_id"),
                            time.time(),
                            receipt_dict.get("risk_tier"),
                            receipt_dict.get("final_status"),
                            receipt_dict.get("receipt_hash"),
                            receipt_dict.get("signature"),
                            json.dumps(receipt_dict, default=str)
                        )
                    )
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to persist receipt to SQLite at {self.db_path}: {e}")

        return receipt_dict

    def get_receipt(self, action_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a specific execution receipt by action_id from ledger."""
        with self._lock:
            # Check SQLite first
            if os.path.exists(self.db_path):
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT receipt_json FROM execution_receipts WHERE action_id = ?",
                            (action_id,)
                        )
                        row = cursor.fetchone()
                        if row and row[0]:
                            return json.loads(row[0])
                except Exception as e:
                    logger.warning(f"Error querying SQLite for receipt {action_id}: {e}")

            # Fallback to JSONL
            if os.path.exists(self.jsonl_path):
                try:
                    with open(self.jsonl_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            item = json.loads(line)
                            if item.get("action_id") == action_id:
                                return item
                except Exception as e:
                    logger.warning(f"Error reading JSONL for receipt {action_id}: {e}")

        return None

    def list_receipts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists recent execution receipts ordered from most recent to oldest."""
        with self._lock:
            # Query SQLite
            if os.path.exists(self.db_path):
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT receipt_json FROM execution_receipts ORDER BY rowid DESC LIMIT ?",
                            (limit,)
                        )
                        rows = cursor.fetchall()
                        if rows:
                            return [json.loads(r[0]) for r in rows if r and r[0]]
                except Exception as e:
                    logger.warning(f"Error listing receipts from SQLite: {e}")

            # Fallback to JSONL
            if os.path.exists(self.jsonl_path):
                try:
                    receipts = []
                    with open(self.jsonl_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                receipts.append(json.loads(line))
                    return receipts[-limit:][::-1]
                except Exception as e:
                    logger.warning(f"Error reading JSONL for receipts: {e}")

        return []

    def verify_receipt_integrity(
        self,
        receipt: Union[ExecutionReceipt, Dict[str, Any]]
    ) -> bool:
        """
        Verifies the cryptographic integrity of an execution receipt.
        Recalculates canonical SHA-256 digest and HMAC-SHA256 signature to guarantee
        that neither payload fields nor hashes have been tampered with.
        """
        if receipt is None:
            return False

        if hasattr(receipt, "to_dict"):
            data = receipt.to_dict()
        elif isinstance(receipt, dict):
            data = receipt
        else:
            return False

        stored_hash = data.get("receipt_hash")
        stored_signature = data.get("signature")
        if not stored_hash or not stored_signature:
            return False

        canonical_str = self.compute_canonical_json(data)
        expected_hash = self.compute_receipt_hash(canonical_str)

        # 1. Verify SHA-256 hash match
        if not hmac.compare_digest(stored_hash, expected_hash):
            return False

        # 2. Verify HMAC-SHA256 signature match
        secret = self.get_master_secret()
        expected_sig_canonical = self.compute_signature(canonical_str, secret)
        expected_sig_hash = self.compute_signature_over_hash(expected_hash, secret)

        sig_matches = (
            hmac.compare_digest(stored_signature, expected_sig_canonical)
            or hmac.compare_digest(stored_signature, expected_sig_hash)
        )

        return sig_matches


# Global singleton instance
proof_engine = ProofOfExecutionEngine()
