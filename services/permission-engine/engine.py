"""
Master Permission Engine for J.A.R.V.I.S.
Coordinates risk classification, boundary policies, approval tokens, and audit trails.
"""

from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld
try:
    from .risk_classifier import classifier
    from .policy import policy
except ImportError:
    from risk_classifier import classifier
    from policy import policy
from shared.sdk_python.jarvis_sdk.config import config
from shared.sdk_python.jarvis_sdk.logger import get_logger

try:
    from services.observability import obs_audit, obs_metrics
except ImportError:
    obs_audit = None
    obs_metrics = None

logger = get_logger("JarvisPermissionEngine")


@dataclass
class PermissionDecision:
    authorized: bool
    tier: ActionTier
    risk_level: str
    rationale: str
    requires_explicit_approval: bool = False
    requires_mfa: bool = False
    approval_id: Optional[str] = None
    audit_id: str = field(default_factory=lambda: f"audit_{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)


@dataclass
class PendingApproval:
    approval_id: str
    action_id: str
    action_name: str
    actor: str
    target_world: str
    risk_level: str
    tier: str
    rationale: str
    parameters: Dict[str, Any]
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED
    created_at: float = field(default_factory=time.time)
    approved_by: Optional[str] = None
    approved_at: Optional[float] = None


class PermissionEngine:
    def __init__(self):
        self.audit_log: List[Dict[str, Any]] = []
        self._pending_approvals: Dict[str, PendingApproval] = {}
        self._approved_actions: set[str] = set()

    def evaluate(self, action: ActionEnvelope, approval_token: Optional[str] = None) -> PermissionDecision:
        """
        Evaluates whether an action is permitted to execute.
        Enforces Circuit Breaker, Least-Privilege boundaries, and strict Risk Tiers:
        LOW: Immediate execution
        MEDIUM: Soft log and execute
        HIGH: Requires interactive user approval
        CRITICAL: Requires explicit approval token + MFA verification
        """
        if obs_metrics:
            obs_metrics.increment("policy.evaluations_total")

        # 1. Emergency Stand-Down check
        if config.emergency_stand_down:
            decision = PermissionDecision(
                authorized=False,
                tier=action.tier,
                risk_level="CRITICAL",
                rationale="BLOCKED: Emergency Stand-Down is currently active."
            )
            self._record_audit(action, decision)
            return decision

        # 2. Agent World Boundary check
        if not policy.is_agent_authorized(action.target_agent, action.target_world):
            decision = PermissionDecision(
                authorized=False,
                tier=action.tier,
                risk_level="HIGH",
                rationale=f"BLOCKED: Agent '{action.target_agent}' is not authorized to operate in world '{action.target_world.value}'."
            )
            self._record_audit(action, decision)
            return decision

        # 3. Dynamic Blast-Radius Classification
        classified_tier, rationale = classifier.classify(
            name=action.name,
            command=action.name,
            target_world=action.target_world,
            parameters=action.parameters
        )

        effective_tier = max(action.tier, classified_tier, key=lambda t: list(ActionTier).index(t))
        risk_level = classifier.tier_to_risk(effective_tier)

        # Check if already approved via approval queue
        if action.action_id in self._approved_actions:
            decision = PermissionDecision(
                authorized=True,
                tier=effective_tier,
                risk_level=risk_level,
                rationale=f"AUTHORIZED_BY_USER: Previously approved action '{action.name}'"
            )
            self._record_audit(action, decision)
            return decision

        # 4. Tier 3 Destructive / CRITICAL Action Safeguard (Requires Token + MFA)
        if effective_tier == ActionTier.TIER_3_DESTRUCTIVE:
            if not approval_token or approval_token != config.master_secret:
                app_req = self._create_approval_request(action, effective_tier, risk_level, rationale)
                decision = PermissionDecision(
                    authorized=False,
                    tier=effective_tier,
                    risk_level=risk_level,
                    rationale=f"BLOCKED: CRITICAL Destructive Action requires explicit MFA / Master Secret approval. {rationale}",
                    requires_explicit_approval=True,
                    requires_mfa=True,
                    approval_id=app_req.approval_id
                )
                self._record_audit(action, decision)
                return decision

        # 5. Tier 2 Mutating / HIGH Action Safeguard (Requires interactive UI approval unless pre-approved)
        if effective_tier == ActionTier.TIER_2_MUTATING and action.requires_approval:
            if not approval_token:
                app_req = self._create_approval_request(action, effective_tier, risk_level, rationale)
                decision = PermissionDecision(
                    authorized=False,
                    tier=effective_tier,
                    risk_level=risk_level,
                    rationale=f"APPROVAL_REQUIRED: HIGH Risk Mutating Action requires interactive confirmation. {rationale}",
                    requires_explicit_approval=True,
                    requires_mfa=False,
                    approval_id=app_req.approval_id
                )
                self._record_audit(action, decision)
                return decision

        # Authorized (LOW or MEDIUM or validly approved HIGH/CRITICAL)
        decision = PermissionDecision(
            authorized=True,
            tier=effective_tier,
            risk_level=risk_level,
            rationale=f"AUTHORIZED: [{risk_level}] {rationale}"
        )
        self._record_audit(action, decision)
        return decision

    def _create_approval_request(self, action: ActionEnvelope, tier: ActionTier, risk_level: str, rationale: str) -> PendingApproval:
        app_id = f"appr_{uuid.uuid4().hex[:8]}"
        req = PendingApproval(
            approval_id=app_id,
            action_id=action.action_id,
            action_name=action.name,
            actor=action.target_agent,
            target_world=action.target_world.value,
            risk_level=risk_level,
            tier=tier.value,
            rationale=rationale,
            parameters=action.parameters
        )
        self._pending_approvals[app_id] = req
        if obs_audit:
            obs_audit.record_event(
                event_type="APPROVAL_REQUEST",
                actor=action.target_agent,
                target=action.name,
                risk_level=risk_level,
                status="PENDING",
                details={"approval_id": app_id, "rationale": rationale}
            )
        return req

    def approve_request(self, approval_id: str, approver: str = "user", token: Optional[str] = None) -> bool:
        req = self._pending_approvals.get(approval_id)
        if not req:
            return False
        if req.risk_level == "CRITICAL" and (not token or token != config.master_secret):
            logger.warning(f"Failed MFA/Token check for critical approval {approval_id}")
            return False

        req.status = "APPROVED"
        req.approved_by = approver
        req.approved_at = time.time()
        self._approved_actions.add(req.action_id)

        if obs_audit:
            obs_audit.record_event(
                event_type="APPROVAL_GRANTED",
                actor=approver,
                target=req.action_name,
                risk_level=req.risk_level,
                status="APPROVED",
                details={"approval_id": approval_id}
            )
        return True

    def reject_request(self, approval_id: str, reason: str = "Denied by user") -> bool:
        req = self._pending_approvals.get(approval_id)
        if not req:
            return False
        req.status = "REJECTED"
        if obs_audit:
            obs_audit.record_event(
                event_type="APPROVAL_DENIED",
                actor="user",
                target=req.action_name,
                risk_level=req.risk_level,
                status="REJECTED",
                details={"approval_id": approval_id, "reason": reason}
            )
        return True

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        return [
            {
                "approval_id": a.approval_id,
                "action_id": a.action_id,
                "action_name": a.action_name,
                "actor": a.actor,
                "target_world": a.target_world,
                "risk_level": a.risk_level,
                "tier": a.tier,
                "rationale": a.rationale,
                "parameters": a.parameters,
                "created_at": a.created_at
            }
            for a in self._pending_approvals.values() if a.status == "PENDING"
        ]

    def _record_audit(self, action: ActionEnvelope, decision: PermissionDecision):
        entry = {
            "audit_id": decision.audit_id,
            "action_id": action.action_id,
            "action_name": action.name,
            "agent": action.target_agent,
            "world": action.target_world.value,
            "tier": decision.tier.value,
            "risk_level": decision.risk_level,
            "authorized": decision.authorized,
            "rationale": decision.rationale,
            "timestamp": decision.timestamp
        }
        self.audit_log.append(entry)
        if obs_audit:
            obs_audit.record_event(
                event_type="POLICY_DECISION",
                actor=action.target_agent,
                target=action.name,
                risk_level=decision.risk_level,
                status="AUTHORIZED" if decision.authorized else "BLOCKED",
                details={"rationale": decision.rationale, "tier": decision.tier.value}
            )
        if decision.authorized:
            logger.info(f"Permission Granted: {action.name} [{decision.risk_level}]")
        else:
            logger.warning(f"Permission Denied: {action.name} - {decision.rationale}")


permission_engine = PermissionEngine()

