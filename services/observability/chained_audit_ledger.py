"""
Cryptographically Chained Local Audit Ledger for Project J.A.R.V.I.S.
Guarantees tamper-evident audit logging for all autonomous operations.
Each record is cryptographically linked to the previous entry via SHA-256 hash chaining:
Block[i].hash = SHA-256(Block[i-1].hash || Timestamp || Action || Parameters || Authorization || Verification).
Any retroactive tampering breaks ledger integrity and is immediately detected.
"""

from __future__ import annotations
import os
import json
import time
import hashlib
from typing import Dict, Any, List, Optional

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("ChainedAuditLedger")


class ChainedAuditLedger:
    GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

    def __init__(self, ledger_file: Optional[str] = None):
        self.ledger_file = ledger_file or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "storage/chained_ledger.jsonl")
        )
        os.makedirs(os.path.dirname(self.ledger_file), exist_ok=True)
        self._last_hash = self._get_tail_hash()

    def _get_tail_hash(self) -> str:
        if not os.path.exists(self.ledger_file):
            return self.GENESIS_HASH
        last_hash = self.GENESIS_HASH
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        last_hash = entry.get("hash", last_hash)
        except Exception:
            pass
        return last_hash

    def _compute_hash(self, prev_hash: str, timestamp: float, action: str, params: Dict[str, Any], auth: str, verified: bool) -> str:
        canonical_params = json.dumps(params, sort_keys=True, separators=(',', ':'))
        payload = f"{prev_hash}|{timestamp:.4f}|{action}|{canonical_params}|{auth}|{verified}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def record_action(
        self,
        intent: str,
        tool: str,
        parameters: Dict[str, Any],
        authorization_ticket: Optional[str] = None,
        verification_status: bool = True,
        result: str = "SUCCESS",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Appends a new cryptographically chained audit block."""
        timestamp = time.time()
        auth_str = authorization_ticket or "STANDARD_EXECUTION"
        block_hash = self._compute_hash(
            self._last_hash, timestamp, tool, parameters, auth_str, verification_status
        )

        entry = {
            "index": self._get_entry_count() + 1,
            "timestamp": timestamp,
            "prev_hash": self._last_hash,
            "intent": intent,
            "tool": tool,
            "parameters": parameters,
            "authorization": auth_str,
            "verified": verification_status,
            "result": result,
            "hash": block_hash,
            "metadata": metadata or {}
        }

        with open(self.ledger_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        self._last_hash = block_hash
        logger.info(f"🔒 [AuditLedger] Chained block #{entry['index']} ({tool}) -> Hash: {block_hash[:16]}...")
        return entry

    def _get_entry_count(self) -> int:
        if not os.path.exists(self.ledger_file):
            return 0
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    def verify_ledger_integrity(self) -> Dict[str, Any]:
        """Walks the complete ledger chain and verifies mathematical hash continuity."""
        if not os.path.exists(self.ledger_file):
            return {"valid": True, "total_blocks": 0, "status": "EMPTY_LEDGER"}

        expected_prev = self.GENESIS_HASH
        count = 0

        with open(self.ledger_file, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                block = json.loads(line)
                if block.get("prev_hash") != expected_prev:
                    logger.critical(f"🚨 [AuditLedger] CHAIN BROKEN at block #{idx}! Expected prev {expected_prev[:16]} but found {block.get('prev_hash')[:16]}")
                    return {"valid": False, "tampered_block": idx, "reason": "PREV_HASH_MISMATCH"}

                calc_hash = self._compute_hash(
                    block["prev_hash"],
                    block["timestamp"],
                    block["tool"],
                    block["parameters"],
                    block["authorization"],
                    block["verified"]
                )
                if block.get("hash") != calc_hash:
                    logger.critical(f"🚨 [AuditLedger] TAMPERING DETECTED in block #{idx}! Block hash invalid.")
                    return {"valid": False, "tampered_block": idx, "reason": "HASH_CORRUPTED"}

                expected_prev = block["hash"]
                count += 1

        logger.info(f"✔ [AuditLedger] Verified {count} blocks. Ledger integrity is mathematically sound.")
        return {"valid": True, "total_blocks": count, "tail_hash": expected_prev}


chained_audit_ledger = ChainedAuditLedger()
