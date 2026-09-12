"""
Verification Contract for J.A.R.V.I.S. Dual-Channel Corroboration Engine.
Validates whether an action actually altered reality (Physical, OS, or Cloud state).
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import uuid
from typing import Any, Dict, Optional


class VerificationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"
    ROLLED_BACK = "rolled_back"


@dataclass
class VerificationResult:
    action_id: str
    status: VerificationStatus
    logical_verified: bool               # Channel 1: State query / return code verified
    sensory_verified: Optional[bool]     # Channel 2: Real-world sensory corroboration (lux, camera, port ping)
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: str(uuid.uuid4()))
    failure_reason: Optional[str] = None
    retry_recommended: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
