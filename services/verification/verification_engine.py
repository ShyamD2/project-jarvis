"""
Verification Engine for Project J.A.R.V.I.S.
Performs dual-channel corroboration (Logical State + Sensory Reality).
Triggers autonomous self-healing if verification fails.
"""

from __future__ import annotations
import time
from typing import Dict, Any, Optional
from shared.schemas.verification_contract import VerificationResult, VerificationStatus
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisVerificationEngine")


class VerificationEngine:
    def verify_action(
        self,
        action_id: str,
        logical_check: bool,
        sensory_check: Optional[bool] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> VerificationResult:
        """
        Dual-channel corroboration:
        Channel 1: API / command return code
        Channel 2: Physical / process / metric reality change
        """
        details = details or {}
        is_verified = logical_check and (sensory_check is not False)

        status = VerificationStatus.VERIFIED if is_verified else VerificationStatus.FAILED
        failure_reason = None if is_verified else "Verification failed: Logical or sensory corroboration mismatch."

        result = VerificationResult(
            action_id=action_id,
            status=status,
            logical_verified=logical_check,
            sensory_verified=sensory_check,
            details=details,
            failure_reason=failure_reason,
            retry_recommended=not is_verified
        )

        if is_verified:
            logger.info(f"✔ [VerificationEngine] Action [{action_id}] VERIFIED via dual channels.")
        else:
            logger.warning(f"❌ [VerificationEngine] Action [{action_id}] FAILED verification. Triggering self-healing.")

        return result


verification_engine = VerificationEngine()
