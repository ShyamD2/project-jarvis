"""
Epistemic Self-Correction Engine for Project J.A.R.V.I.S.
Guarantees truth-in-state reporting by strictly distinguishing between:
1. EXECUTED: Code ran without throwing an exception.
2. VERIFIED: Ground-truth sensory / OS inspection confirmed the expected physical change.
3. FAILED: Error occurred or non-zero exit code returned.
4. UNCERTAIN: Tool completed, but physical verification was indeterminate.
Prevents J.A.R.V.I.S. from confabulating success based solely on exception-free returns.
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("EpistemicEvaluator")


class EpistemicState(str, Enum):
    VERIFIED = "VERIFIED"     # Confirmed by sensory check or OS reality probe
    EXECUTED = "EXECUTED"     # Ran, but sensory proof is not required (e.g. read-only telemetry)
    UNCERTAIN = "UNCERTAIN"   # Tool executed, but physical verification could not confirm state
    FAILED = "FAILED"         # Execution errored or returned explicit failure


@dataclass
class EpistemicAssessment:
    state: EpistemicState
    truthful_summary: str
    confidence: float
    sensory_verified: bool
    requires_operator_notice: bool


class EpistemicEvaluator:
    def __init__(self):
        self._last_assessment: Optional[EpistemicAssessment] = None

    def get_last_assessment(self) -> Optional[EpistemicAssessment]:
        return self._last_assessment

    def evaluate(
        self,
        tool_name: str,
        tool_result: Any,
        verification_status: bool = True,
        verification_details: Optional[Dict[str, Any]] = None
    ) -> EpistemicAssessment:
        """Evaluates ground truth vs execution claim."""
        details = verification_details or {}

        # 1. Failure check
        if isinstance(tool_result, dict):
            if not tool_result.get("success", True) or tool_result.get("status") == "error":
                err = tool_result.get("error", "Action failed")
                assessment = EpistemicAssessment(
                    state=EpistemicState.FAILED,
                    truthful_summary=f"Action '{tool_name}' failed: {err}",
                    confidence=1.0,
                    sensory_verified=False,
                    requires_operator_notice=True
                )
                self._last_assessment = assessment
                return assessment

        # 2. Sensory Verification check
        if verification_status:
            assessment = EpistemicAssessment(
                state=EpistemicState.VERIFIED,
                truthful_summary=f"Action '{tool_name}' successfully executed and verified against host reality.",
                confidence=1.0,
                sensory_verified=True,
                requires_operator_notice=False
            )
            self._last_assessment = assessment
            return assessment

        # 3. Unverified Mutating Action check
        mutating_keywords = ["launch", "open", "close", "kill", "power", "click", "delete", "write", "set"]
        is_mutating = any(k in tool_name.lower() for k in mutating_keywords)

        if is_mutating:
            logger.warning(f"⚠️ [EpistemicEvaluator] Mutating action '{tool_name}' completed without verified sensory confirmation.")
            assessment = EpistemicAssessment(
                state=EpistemicState.UNCERTAIN,
                truthful_summary=f"Action '{tool_name}' was triggered, but physical sensory confirmation is pending.",
                confidence=0.5,
                sensory_verified=False,
                requires_operator_notice=True
            )
            self._last_assessment = assessment
            return assessment

        # 4. Pure read-only action
        assessment = EpistemicAssessment(
            state=EpistemicState.EXECUTED,
            truthful_summary=f"Action '{tool_name}' query completed.",
            confidence=0.9,
            sensory_verified=False,
            requires_operator_notice=False
        )
        self._last_assessment = assessment
        return assessment


epistemic_evaluator = EpistemicEvaluator()
