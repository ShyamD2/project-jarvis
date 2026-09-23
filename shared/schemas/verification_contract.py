"""
Verification Contract for J.A.R.V.I.S. Dual-Channel Corroboration Engine.
Validates whether an action actually altered reality (Physical, OS, or Cloud state).
Phase 36: Adds UNKNOWN terminal state, observed_state, expected_state, match, confidence, and verifier.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import uuid
import time
from typing import Any, Dict, Optional


class VerificationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"       # Post-condition confirmed in real environment
    FAILED = "failed"           # Post-condition not achieved / contradicted
    UNKNOWN = "unknown"         # Execution occurred/pending, but post-condition cannot be confirmed
    AMBIGUOUS = "ambiguous"     # Backward-compatibility alias for UNKNOWN
    ROLLED_BACK = "rolled_back"


@dataclass
class VerificationResult:
    action_id: str
    status: VerificationStatus
    logical_verified: bool = True               # Channel 1: State query / return code verified
    sensory_verified: Optional[bool] = None     # Channel 2: Real-world sensory corroboration
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: str(time.time()))
    failure_reason: Optional[str] = None
    retry_recommended: bool = False
    observed_state: Dict[str, Any] = field(default_factory=dict)
    expected_state: Dict[str, Any] = field(default_factory=dict)
    match: bool = False
    confidence: float = 1.0
    evidence: Dict[str, Any] = field(default_factory=dict)
    observed_at: float = field(default_factory=time.time)
    verifier: str = "VerificationEngine"

    def __post_init__(self):
        if self.status == VerificationStatus.VERIFIED:
            self.match = True
            if self.sensory_verified is None:
                self.sensory_verified = True
        elif self.status == VerificationStatus.FAILED:
            self.match = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VerificationResult:
        raw_status = data.get("status", "pending")
        if raw_status == "ambiguous":
            st = VerificationStatus.UNKNOWN
        else:
            try:
                st = VerificationStatus(raw_status)
            except ValueError:
                st = VerificationStatus.UNKNOWN

        return cls(
            action_id=data.get("action_id", str(uuid.uuid4())),
            status=st,
            logical_verified=data.get("logical_verified", True),
            sensory_verified=data.get("sensory_verified"),
            details=data.get("details", {}),
            timestamp=data.get("timestamp", str(time.time())),
            failure_reason=data.get("failure_reason"),
            retry_recommended=data.get("retry_recommended", False),
            observed_state=data.get("observed_state", {}),
            expected_state=data.get("expected_state", {}),
            match=data.get("match", st == VerificationStatus.VERIFIED),
            confidence=data.get("confidence", 1.0),
            evidence=data.get("evidence", {}),
            observed_at=data.get("observed_at", time.time()),
            verifier=data.get("verifier", "VerificationEngine")
        )
