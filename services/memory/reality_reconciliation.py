"""
Reality Reconciliation Engine for Project J.A.R.V.I.S. (Phase 36 Stage 36.5).
Implements the Observation != Correction Principle (Item 116 & Item 121):
  - Detects drift between Expected State (Intent/Model) and Observed Ground-Truth.
  - Updates the World Model's belief state to match reality.
  - Strictly prohibits autonomous production mutations without explicit operator approval.
"""

from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger
from services.memory.world_model import world_model

logger = get_logger("JarvisRealityReconciliation")


@dataclass
class DriftEvent:
    drift_id: str = field(default_factory=lambda: f"drift_{uuid.uuid4().hex[:8]}")
    entity_id: str = ""
    attribute: str = ""
    expected_value: Any = None
    observed_value: Any = None
    severity: str = "WARNING"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RealityReconciliationEngine:
    def __init__(self, max_ledger_size: int = 1000):
        self.drift_ledger: List[DriftEvent] = []
        self._max_ledger_size = max_ledger_size

    def detect_drift(
        self,
        entity_id: str,
        expected: Dict[str, Any],
        observed: Dict[str, Any]
    ) -> List[DriftEvent]:
        """
        Compares expected state attributes against observed state attributes.
        Returns a list of detected DriftEvents.
        """
        events = []
        for key, exp_val in expected.items():
            if key in observed:
                obs_val = observed[key]
                if exp_val != obs_val:
                    # Severity determination
                    sev = "WARNING"
                    if key in ["status", "running", "online", "healthy"]:
                        sev = "CRITICAL"
                    elif key in ["level", "volume", "temperature", "cpu"]:
                        sev = "INFO"

                    event = DriftEvent(
                        entity_id=entity_id,
                        attribute=key,
                        expected_value=exp_val,
                        observed_value=obs_val,
                        severity=sev
                    )
                    events.append(event)
                    self._record_drift(event)
            else:
                # Attribute missing in observed state
                event = DriftEvent(
                    entity_id=entity_id,
                    attribute=key,
                    expected_value=exp_val,
                    observed_value=None,
                    severity="WARNING"
                )
                events.append(event)
                self._record_drift(event)
        return events

    def _record_drift(self, event: DriftEvent):
        self.drift_ledger.append(event)
        if len(self.drift_ledger) > self._max_ledger_size:
            self.drift_ledger.pop(0)
        logger.warning(
            f"⚠️ [DriftDetected] Entity '{event.entity_id}' attribute '{event.attribute}': "
            f"Expected [{event.expected_value}] != Observed [{event.observed_value}] ({event.severity})"
        )

    def reconcile_world_model(self, entity_id: str, observed: Dict[str, Any]):
        """
        Updates World Model belief state to reflect true observed reality.
        Does NOT alter external production systems.
        """
        if "device" in entity_id or "relay" in entity_id:
            world_model.update_device(entity_id, relays=observed.get("relays"), sensors=observed.get("sensors"))
        elif "pc" in entity_id or "host" in entity_id:
            world_model.update_pc(**observed)
        elif "cloud" in entity_id or "aws" in entity_id:
            world_model.update_cloud(**observed)

    def reconcile(
        self,
        entity_id: str,
        expected: Dict[str, Any],
        observed: Dict[str, Any],
        autonomous_correct: bool = False,
        operator_approval_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Reconciles ground truth with world model.
        CARDINAL INVARIANT: Observation != Correction.
        Attempting autonomous production mutation without explicit operator approval will be rejected.
        """
        drifts = self.detect_drift(entity_id, expected, observed)
        drift_detected = len(drifts) > 0

        # Always update internal World Model so Jarvis is grounded in truth
        self.reconcile_world_model(entity_id, observed)

        # Enforce Observation != Correction invariant
        autonomous_mutation_executed = False
        if autonomous_correct and drift_detected:
            if not operator_approval_token:
                logger.error(
                    f"🛑 [RealityReconciliation] Autonomous mutation rejected for '{entity_id}'. "
                    f"Policy Invariant: Observation != Correction requires explicit operator approval."
                )
                raise PermissionError(
                    "Autonomous production mutation prohibited: Observation != Correction principle "
                    "mandates operator ticket for production state alterations."
                )
            else:
                # Operator authorized mutation
                autonomous_mutation_executed = True
                logger.info(f"✔ [RealityReconciliation] Operator authorized correction for '{entity_id}'.")

        return {
            "entity_id": entity_id,
            "drift_detected": drift_detected,
            "drift_count": len(drifts),
            "drifts": [d.to_dict() for d in drifts],
            "world_model_reconciled": True,
            "autonomous_mutation_executed": autonomous_mutation_executed
        }


reality_reconciliation = RealityReconciliationEngine()
