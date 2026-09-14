"""
J.A.R.V.I.S. Safety Guard & 4-Tier Blast Radius Gatekeeper.
Strictly regulates action permissions, eliminates destructive bypasses, and manages two-factor confirmations.
"""

from __future__ import annotations
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, Tuple, List

from shared.schemas.action_envelope import ActionTier, TargetWorld
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisSafetyGuard")


class StrictTier(str, Enum):
    TIER_0_READ_ONLY = "TIER_0_READ_ONLY"           # Idempotent queries, CPU, IP, AWS list. Zero confirmation.
    TIER_1_REVERSIBLE = "TIER_1_REVERSIBLE"         # Volume, brightness, open app, pause music, folder create. Soft ack.
    TIER_2_DISRUPTIVE = "TIER_2_DISRUPTIVE"         # Kill app, stop container, stop EC2, change network, move files. Interactive approval.
    TIER_3_DESTRUCTIVE = "TIER_3_DESTRUCTIVE"       # Shutdown, restart, permanent delete, terraform destroy, drop DB. ALWAYS requires confirmation.


@dataclass
class ApprovalTicket:
    approval_id: str
    action_name: str
    tier: StrictTier
    parameters: Dict[str, Any]
    rationale: str
    tool_name: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 120.0) # 2 minutes
    status: str = "PENDING"                         # PENDING, APPROVED, REJECTED, EXPIRED
    approver: Optional[str] = None
    confirmation_method: Optional[str] = None       # "voice", "hud_button", "cli"


class SafetyGuard:
    def __init__(self):
        self._pending_tickets: Dict[str, ApprovalTicket] = {}
        self._approved_action_keys: set[str] = set()

        # Regex patterns for strict risk tier mapping
        self.tier3_patterns = [
            r"\b(shutdown|shut\s+down|power\s+off|turn\s+off\s+pc|reboot|pc\s+restart|restart)\b",
            r"\b(terraform\s+destroy|destroy\s+infrastructure|destroy\s+all)\b",
            r"\b(permanent\s+delete|force\s+delete|rm\s+-rf|wipe\s+disk|format\s+[c-z]:|drop\s+database|truncate\s+table)\b",
            r"\b(delete\s+s3\s+bucket|delete\s+bucket|terminate\s+instance|delete\s+database|delete\s+table)\b",
            r"\b(execute_powershell|powershell|cmd\.exe|run_script|raw_command|eval|exec)\b",
            r"\b(sign\s*out|log\s*off)\b"
        ]

        self.tier2_patterns = [
            r"\b(kill\s+app|close\s+app|kill\s+process|force\s+kill|terminate\s+process|close\s+all\s+apps)\b",
            r"\b(docker\s+stop|stop\s+container|docker\s+restart|container\s+restart)\b",
            r"\b(stop\s+ec2|stop\s+instance|restart\s+ec2)\b",
            r"\b(disconnect\s+wifi|change\s+network|switch\s+wifi|modify\s+ip|reset\s+adapter)\b",
            r"\b(move\s+file|rename\s+file|move\s+folder|rename\s+folder)\b",
            r"\b(delete\s+file|remove\s+file|recycle_file)\b"
        ]

        self.tier1_patterns = [
            r"\b(volume|set\s+volume|mute|unmute|brightness|set\s+brightness|media\s+play|media\s+pause|next\s+track|previous\s+track)\b",
            r"\b(open\s+app|launch\s+app|open\s+browser|browse\s+web|open\s+tab|new\s+tab|open\s+bookmarks|close\s+tab|close\s+window)\b",
            r"\b(create\s+file|create\s+folder|make\s+dir|zip\s+folder|unzip\s+file|clipboard\s+copy|clipboard\s+paste)\b",
            r"\b(mouse\s+click|type\s+text|press\s+key|press\s+shortcut|screenshot|send\s+message|take\s+note|add\s+task)\b"
        ]

        self.tier0_patterns = [
            r"\b(cpu|ram|memory|disk|battery|temperature|hardware|status|vitals|telemetry|ip\s+address|network\s+status)\b",
            r"\b(list\s+s3|list\s+ec2|aws\s+health|cloud\s+health|git\s+status|git\s+log|docker\s+ps|list\s+containers)\b",
            r"\b(time|date|weather|check\s+messages|read\s+notes|list\s+tasks|screen\s+vision|analyze\s+screen)\b"
        ]

    def classify_action(self, action_name: str, parameters: Optional[Dict[str, Any]] = None) -> Tuple[StrictTier, str]:
        """
        Classifies an action strictly into Tier 0, 1, 2, or 3.
        """
        target_str = f"{action_name} {str(parameters or {})}".lower().replace("_", " ")

        # Check Tier 3 (Destructive)
        for pat in self.tier3_patterns:
            if re.search(pat, target_str):
                return StrictTier.TIER_3_DESTRUCTIVE, f"Destructive command matches '{pat}'. Mandatory confirmation required."

        # Check Tier 2 (Potentially Disruptive)
        for pat in self.tier2_patterns:
            if re.search(pat, target_str):
                return StrictTier.TIER_2_DISRUPTIVE, f"Disruptive command matches '{pat}'. Interactive approval required."

        # Check Tier 0 (Read-Only)
        for pat in self.tier0_patterns:
            if re.search(pat, target_str):
                return StrictTier.TIER_0_READ_ONLY, f"Read-only command matches '{pat}'. 0 confirmation required."

        # Default to Tier 1 (Reversible)
        return StrictTier.TIER_1_REVERSIBLE, "Standard reversible operation. Soft confirmation applied."

    def evaluate_request(
        self,
        action_name: str,
        parameters: Optional[Dict[str, Any]] = None,
        approval_id: Optional[str] = None,
        tool_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluates permission to execute.
        STRICT POLICY:
        - Tier 0: Authorized immediately.
        - Tier 1: Authorized immediately (with soft ack).
        - Tier 2: Authorized if pre-approved or interactive approval ticket provided.
        - Tier 3: ALWAYS BLOCKED unless a valid, unexpired, confirmed approval ticket is presented.
                  NO OVERRIDE FLAG ALLOWED.
        """
        params = parameters or {}
        tier, rationale = self.classify_action(action_name, params)

        # Check if already approved via ticket
        if approval_id and approval_id in self._pending_tickets:
            ticket = self._pending_tickets[approval_id]
            if ticket.status == "APPROVED":
                if time.time() > ticket.expires_at:
                    ticket.status = "EXPIRED"
                    return {
                        "authorized": False,
                        "tier": tier.value,
                        "rationale": "Confirmation ticket has expired. Please re-issue the command.",
                        "requires_confirmation": True,
                        "ticket_id": None
                    }
                return {
                    "authorized": True,
                    "tier": tier.value,
                    "rationale": f"Action authorized via confirmed ticket {approval_id}.",
                    "requires_confirmation": False,
                    "ticket_id": approval_id
                }

        # Check Tier 3 Destructive
        if tier == StrictTier.TIER_3_DESTRUCTIVE:
            # Generate ticket
            ticket = self._create_ticket(action_name, tier, params, rationale, tool_name=tool_name)
            friendly_name = action_name.replace("pc_", "").replace("_", " ")
            logger.warning(f"[SafetyGuard] Tier 3 Destructive action '{action_name}' blocked pending mandatory confirmation. Ticket: {ticket.approval_id}")
            return {
                "authorized": False,
                "tier": tier.value,
                "rationale": f"MANDATORY CONFIRMATION: {rationale}",
                "requires_confirmation": True,
                "confirmation_level": "TIER_3_DESTRUCTIVE",
                "ticket_id": ticket.approval_id,
                "prompt_user": f"Sir, you have requested a sensitive system action ({friendly_name}). Should I proceed? Please say 'yes' or 'proceed' to confirm."
            }

        # Check Tier 2 Disruptive
        if tier == StrictTier.TIER_2_DISRUPTIVE:
            ticket = self._create_ticket(action_name, tier, params, rationale, tool_name=tool_name)
            logger.info(f"[SafetyGuard] Tier 2 Disruptive action '{action_name}' held for approval. Ticket: {ticket.approval_id}")
            return {
                "authorized": False,
                "tier": tier.value,
                "rationale": f"APPROVAL REQUIRED: {rationale}",
                "requires_confirmation": True,
                "confirmation_level": "TIER_2_DISRUPTIVE",
                "ticket_id": ticket.approval_id,
                "prompt_user": f"Sir, please approve the disruptive action: {action_name.replace('_', ' ')}."
            }

        # Tier 0 and Tier 1 are authorized
        return {
            "authorized": True,
            "tier": tier.value,
            "rationale": rationale,
            "requires_confirmation": False,
            "ticket_id": None
        }

    def _create_ticket(self, action_name: str, tier: StrictTier, parameters: Dict[str, Any], rationale: str, tool_name: Optional[str] = None) -> ApprovalTicket:
        app_id = f"sec_{uuid.uuid4().hex[:8]}"
        ticket = ApprovalTicket(
            approval_id=app_id,
            action_name=action_name,
            tier=tier,
            parameters=parameters,
            rationale=rationale,
            tool_name=tool_name
        )
        self._pending_tickets[app_id] = ticket
        return ticket

    def confirm_ticket(self, approval_id: str, approver: str = "operator", method: str = "voice") -> bool:
        """Confirms a pending approval ticket"""
        ticket = self._pending_tickets.get(approval_id)
        if not ticket:
            logger.warning(f"[SafetyGuard] Attempted to confirm unknown ticket {approval_id}")
            return False
        if time.time() > ticket.expires_at:
            ticket.status = "EXPIRED"
            logger.warning(f"[SafetyGuard] Ticket {approval_id} expired")
            return False

        ticket.status = "APPROVED"
        ticket.approver = approver
        ticket.confirmation_method = method
        logger.info(f"[SafetyGuard] Ticket {approval_id} ({ticket.action_name}) APPROVED by {approver} via {method}")
        return True

    def reject_ticket(self, approval_id: str, reason: str = "Denied by operator") -> bool:
        """Rejects a pending approval ticket"""
        ticket = self._pending_tickets.get(approval_id)
        if not ticket:
            return False
        ticket.status = "REJECTED"
        logger.info(f"[SafetyGuard] Ticket {approval_id} ({ticket.action_name}) REJECTED: {reason}")
        return True

    def get_latest_pending_ticket(self) -> Optional[ApprovalTicket]:
        """Retrieves the most recent active pending approval ticket"""
        now = time.time()
        for t in reversed(list(self._pending_tickets.values())):
            if t.status == "PENDING" and now <= t.expires_at:
                return t
        return None

    def get_ticket(self, approval_id: str) -> Optional[ApprovalTicket]:
        return self._pending_tickets.get(approval_id)


safety_guard = SafetyGuard()
