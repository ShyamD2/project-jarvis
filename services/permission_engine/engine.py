"""
Master Permission Engine for J.A.R.V.I.S. (Phase 36).
Implements Policy-as-Code, RBAC, Multi-Factor Decision Evaluation,
Single-Use Capability Leases, Replay Protection, and Policy Simulation.
"""

from __future__ import annotations
import os
import time
import uuid
import yaml
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple

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

POLICY_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../policies/security_policies.yaml"))


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
    single_use_lease_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authorized": self.authorized,
            "tier": self.tier.value if hasattr(self.tier, "value") else str(self.tier),
            "risk_level": self.risk_level,
            "rationale": self.rationale,
            "requires_explicit_approval": self.requires_explicit_approval,
            "requires_mfa": self.requires_mfa,
            "approval_id": self.approval_id,
            "audit_id": self.audit_id,
            "timestamp": self.timestamp,
            "single_use_lease_id": self.single_use_lease_id
        }


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
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED, CONSUMED, EXPIRED
    created_at: float = field(default_factory=time.time)
    approved_by: Optional[str] = None
    approved_at: Optional[float] = None
    nonce: str = field(default_factory=lambda: uuid.uuid4().hex)
    lease_ttl_seconds: float = 300.0  # 5 minutes validity


class PermissionEngine:
    def __init__(self):
        self.audit_log: List[Dict[str, Any]] = []
        self._pending_approvals: Dict[str, PendingApproval] = {}
        # Single-use active capability leases: action_id -> PendingApproval
        self._active_leases: Dict[str, PendingApproval] = {}
        self._consumed_nonces: set[str] = set()
        self.policies = self._load_policies()

    def _load_policies(self) -> Dict[str, Any]:
        """Loads declarative policies from policies/security_policies.yaml."""
        if os.path.exists(POLICY_FILE_PATH):
            try:
                with open(POLICY_FILE_PATH, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"[PermissionEngine] Could not parse policies YAML: {e}")
        return {}

    def reload_policies(self):
        """Hot-reloads declarative policies."""
        self.policies = self._load_policies()
        logger.info("[PermissionEngine] Declarative security policies reloaded.")

    def evaluate(
        self,
        action: ActionEnvelope,
        approval_token: Optional[str] = None,
        confidence: float = 1.0,
        user_role: str = "OPERATOR",
        environment: Optional[str] = None
    ) -> PermissionDecision:
        """
        Multi-Factor Decision Function (Phase 36 Item 4 & Invariant):
        Decision = f(confidence, risk_tier, blast_radius, freshness, authorization, environment, reversibility)
        """
        if obs_metrics:
            obs_metrics.increment("policy.evaluations_total")

        target_env = (environment or os.getenv("JARVIS_ENV", "development")).lower().strip()

        # 1. Emergency Stand-Down & Safe Mode check (Zero-Tolerance Invariant)
        if config.emergency_stand_down or os.getenv("JARVIS_SAFE_MODE", "false").lower() == "true":
            # In safe mode, only reflex read queries are permitted
            if action.tier in [ActionTier.TIER_2_MUTATING, ActionTier.TIER_3_DESTRUCTIVE]:
                decision = PermissionDecision(
                    authorized=False,
                    tier=action.tier,
                    risk_level="CRITICAL",
                    rationale="BLOCKED: Emergency Stand-Down or Safe Mode active (mutations frozen)."
                )
                self._record_audit(action, decision)
                return decision

        # 2. Agent World Boundary check
        if not policy.is_agent_authorized(action.target_agent, action.target_world):
            decision = PermissionDecision(
                authorized=False,
                tier=action.tier,
                risk_level="HIGH",
                rationale=f"BLOCKED: Agent '{action.target_agent}' is not authorized in world '{action.target_world.value}'."
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

        # 4. RBAC Role Verification
        role_allowed = self._check_rbac_role(user_role, effective_tier, action.name)
        if not role_allowed:
            decision = PermissionDecision(
                authorized=False,
                tier=effective_tier,
                risk_level=risk_level,
                rationale=f"BLOCKED_RBAC: Role '{user_role}' is not authorized to execute tier '{effective_tier.value}' for tool '{action.name}'."
            )
            self._record_audit(action, decision)
            return decision

        # 5. Single-Use Capability Lease Check (Item 10 & 112)
        if action.action_id in self._active_leases:
            lease = self._active_leases[action.action_id]
            now = time.time()
            # Check expiration
            if now > lease.approved_at + lease.lease_ttl_seconds:
                del self._active_leases[action.action_id]
                decision = PermissionDecision(
                    authorized=False,
                    tier=effective_tier,
                    risk_level=risk_level,
                    rationale="BLOCKED_EXPIRED: Approval capability lease has expired."
                )
                self._record_audit(action, decision)
                return decision

            # Check replay prevention on nonce
            if lease.nonce in self._consumed_nonces:
                del self._active_leases[action.action_id]
                decision = PermissionDecision(
                    authorized=False,
                    tier=effective_tier,
                    risk_level=risk_level,
                    rationale="BLOCKED_REPLAY: Approval nonce was already consumed (replay detected)."
                )
                self._record_audit(action, decision)
                return decision

            # Consume the lease immediately (Single-Use Authority)
            self._consumed_nonces.add(lease.nonce)
            del self._active_leases[action.action_id]
            lease.status = "CONSUMED"
            logger.info(f"✔ [PermissionEngine] Consumed single-use capability lease for action '{action.name}' (Nonce: {lease.nonce[:8]})")

            decision = PermissionDecision(
                authorized=True,
                tier=effective_tier,
                risk_level=risk_level,
                rationale=f"AUTHORIZED_BY_LEASE: Approved by '{lease.approved_by}'",
                single_use_lease_id=lease.approval_id
            )
            self._record_audit(action, decision)
            return decision

        # 6. Multi-Factor Decision: High Confidence with Tier 3 Destructive STILL mandates human approval
        if effective_tier == ActionTier.TIER_3_DESTRUCTIVE:
            app_req = self._create_approval_request(action, effective_tier, risk_level, rationale)
            decision = PermissionDecision(
                authorized=False,
                tier=effective_tier,
                risk_level=risk_level,
                rationale=f"CRITICAL: Destructive action requires explicit single-use approval ticket. {rationale}",
                requires_explicit_approval=True,
                requires_mfa=True,
                approval_id=app_req.approval_id
            )
            self._record_audit(action, decision)
            return decision

        # 7. Tier 2 Mutating in PRODUCTION or with Low Confidence requires approval
        if effective_tier == ActionTier.TIER_2_MUTATING:
            if target_env == "production" or confidence < 0.85:
                app_req = self._create_approval_request(action, effective_tier, risk_level, rationale)
                decision = PermissionDecision(
                    authorized=False,
                    tier=effective_tier,
                    risk_level=risk_level,
                    rationale=f"APPROVAL_REQUIRED: Tier 2 Mutating Action in {target_env.upper()} (Confidence: {confidence:.2f}) requires operator lease.",
                    requires_explicit_approval=True,
                    requires_mfa=False,
                    approval_id=app_req.approval_id
                )
                self._record_audit(action, decision)
                return decision

        # 8. Tier 0 Reflex & Tier 1 Soft: Policy & Capability Verified -> Immediate Approval
        decision = PermissionDecision(
            authorized=True,
            tier=effective_tier,
            risk_level=risk_level,
            rationale=f"AUTHORIZED: [{risk_level}] {rationale}"
        )
        self._record_audit(action, decision)
        return decision

    def _check_rbac_role(self, role: str, tier: ActionTier, tool_name: str) -> bool:
        """Evaluates whether role has permission for tier and specific tool policy."""
        rbac_cfg = self.policies.get("rbac", {}).get("roles", {})
        role_def = rbac_cfg.get(role.upper())
        if not role_def:
            # Default fallback: OPERATOR allows tier 0 and 1
            if role.upper() == "OWNER":
                return True
            elif role.upper() == "ADMIN":
                return tier in [ActionTier.TIER_0_REFLEX, ActionTier.TIER_1_SOFT, ActionTier.TIER_2_MUTATING]
            elif role.upper() == "OPERATOR":
                return tier in [ActionTier.TIER_0_REFLEX, ActionTier.TIER_1_SOFT]
            elif role.upper() == "VIEWER":
                return tier == ActionTier.TIER_0_REFLEX
            return False

        allowed_tiers = role_def.get("allowed_tiers", [])
        return tier.value in allowed_tiers

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
        return req

    def approve_request(self, approval_id: str, approver: str = "operator", token: Optional[str] = None) -> bool:
        """Approves a pending ticket and creates an active single-use capability lease."""
        req = self._pending_approvals.get(approval_id)
        if not req or req.status != "PENDING":
            return False

        # If critical tier, enforce token / master secret check
        if req.risk_level == "CRITICAL" and token != config.master_secret:
            logger.warning(f"❌ [PermissionEngine] Approval {approval_id} rejected: Invalid token for critical action.")
            return False

        req.status = "APPROVED"
        req.approved_by = approver
        req.approved_at = time.time()
        # Add single-use lease
        self._active_leases[req.action_id] = req
        logger.info(f"✔ [PermissionEngine] Capability lease granted for {req.action_name} (ActionID: {req.action_id})")
        return True

    def reject_request(self, approval_id: str, reason: str = "Denied by operator") -> bool:
        req = self._pending_approvals.get(approval_id)
        if not req:
            return False
        req.status = "REJECTED"
        return True

    def simulate_policy(
        self,
        user_role: str,
        tool_name: str,
        parameters: Optional[Dict[str, Any]] = None,
        environment: str = "development"
    ) -> Dict[str, Any]:
        """Dry-run policy evaluation (Phase 36 Item 45)."""
        params = parameters or {}
        tool_cfg = self.policies.get("tools", {}).get(tool_name, {})
        tier_str = tool_cfg.get("tier", ActionTier.TIER_2_MUTATING.value)
        try:
            tier_enum = ActionTier(tier_str)
        except Exception:
            tier_enum = ActionTier.TIER_2_MUTATING

        env_action = ActionEnvelope(
            name=tool_name,
            target_world=TargetWorld.COMPUTER,
            target_agent="simulation_agent",
            tier=tier_enum,
            parameters=params
        )
        decision = self.evaluate(
            action=env_action,
            user_role=user_role,
            environment=environment
        )
        return {
            "tool": tool_name,
            "role": user_role,
            "environment": environment,
            "authorized": decision.authorized,
            "tier": decision.tier.value,
            "risk_level": decision.risk_level,
            "requires_approval": decision.requires_explicit_approval,
            "rationale": decision.rationale
        }

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
        if len(self.audit_log) > 1000:
            self.audit_log.pop(0)


permission_engine = PermissionEngine()
