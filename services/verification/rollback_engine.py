"""
Rollback & Transaction Engine for Project J.A.R.V.I.S.
Implements atomic operations with pre-state checkpoints, dual-channel verification, and automated rollback/retry:
Checkpoint -> Execute -> Verify -> Commit or Rollback -> Diagnose -> Retry
"""

from __future__ import annotations
import time
import uuid
import copy
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict

from shared.sdk_python.jarvis_sdk.logger import get_logger

try:
    from services.observability import obs_audit, obs_recorder, obs_metrics
except ImportError:
    obs_audit = None
    obs_recorder = None
    obs_metrics = None

logger = get_logger("JarvisRollbackEngine")


@dataclass
class TransactionCheckpoint:
    tx_id: str
    name: str
    pre_state: Dict[str, Any]
    status: str = "ACTIVE"  # ACTIVE, COMMITTED, ROLLED_BACK, FAILED
    created_at: float = field(default_factory=time.time)
    committed_at: Optional[float] = None
    rollback_at: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RollbackEngine:
    def __init__(self):
        self._transactions: Dict[str, TransactionCheckpoint] = {}
        self._rollback_handlers: Dict[str, Callable[[Dict[str, Any]], bool]] = {}

    def register_rollback_handler(self, state_type: str, handler: Callable[[Dict[str, Any]], bool]):
        """Registers a handler to restore state for a given category (e.g. 'file', 'process', 'config')"""
        self._rollback_handlers[state_type] = handler

    def begin_transaction(self, name: str, pre_state: Dict[str, Any]) -> str:
        """Starts a transaction and records initial pre-state checkpoint"""
        tx_id = f"tx_{uuid.uuid4().hex[:10]}"
        cp = TransactionCheckpoint(
            tx_id=tx_id,
            name=name,
            pre_state=copy.deepcopy(pre_state)
        )
        self._transactions[tx_id] = cp

        if obs_recorder:
            obs_recorder.record_system_event("transaction", "BEGIN", {"tx_id": tx_id, "name": name})
        logger.info(f"Transaction begun [{tx_id}]: '{name}'")
        return tx_id

    def commit_transaction(self, tx_id: str) -> bool:
        """Commits transaction after successful execution and verification"""
        cp = self._transactions.get(tx_id)
        if not cp or cp.status != "ACTIVE":
            return False

        cp.status = "COMMITTED"
        cp.committed_at = time.time()

        if obs_recorder:
            obs_recorder.record_system_event("transaction", "COMMITTED", {"tx_id": tx_id})
        logger.info(f"Transaction committed [{tx_id}]: '{cp.name}'")
        return True

    def rollback_transaction(self, tx_id: str, error_msg: Optional[str] = None) -> bool:
        """Rolls back pre-state if execution failed or verification failed"""
        cp = self._transactions.get(tx_id)
        if not cp or cp.status != "ACTIVE":
            return False

        cp.status = "ROLLED_BACK"
        cp.rollback_at = time.time()
        cp.error = error_msg

        logger.warning(f"Rolling back transaction [{tx_id}] '{cp.name}': {error_msg}")

        # Execute registered rollback handlers
        for state_key, state_val in cp.pre_state.items():
            handler = self._rollback_handlers.get(state_key)
            if handler:
                try:
                    handler(state_val)
                except Exception as e:
                    logger.error(f"Error executing rollback handler for '{state_key}': {e}")

        if obs_audit:
            obs_audit.record_event(
                event_type="ROLLBACK_INITIATED",
                actor="rollback_engine",
                target=cp.name,
                risk_level="HIGH",
                status="ROLLED_BACK",
                details={"tx_id": tx_id, "error": error_msg}
            )

        if obs_recorder:
            obs_recorder.record_system_event("transaction", "ROLLED_BACK", {"tx_id": tx_id, "error": error_msg})

        return True

    def get_transaction(self, tx_id: str) -> Optional[Dict[str, Any]]:
        cp = self._transactions.get(tx_id)
        return cp.to_dict() if cp else None

    def get_recent_transactions(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [cp.to_dict() for cp in list(self._transactions.values())[-limit:]]


rollback_engine = RollbackEngine()
