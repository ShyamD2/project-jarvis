"""
Security Policies and Boundaries for J.A.R.V.I.S.
Restricts agent boundaries according to the principle of least privilege.
"""

from typing import Dict, Set
from shared.schemas.action_envelope import TargetWorld


class PolicyEngine:
    def __init__(self):
        # Permitted target worlds per agent
        self.agent_world_matrix: Dict[str, Set[TargetWorld]] = {
            "windows_agent": {TargetWorld.COMPUTER},
            "esp32_agent": {TargetWorld.PHYSICAL},
            "aws_agent": {TargetWorld.DIGITAL},
            "terraform_agent": {TargetWorld.DIGITAL},
            "core_agent": {TargetWorld.DIGITAL, TargetWorld.COMPUTER, TargetWorld.PHYSICAL},
            "jarvis_core_agent": {TargetWorld.DIGITAL, TargetWorld.COMPUTER, TargetWorld.PHYSICAL},
            "agent_runtime": {TargetWorld.DIGITAL, TargetWorld.COMPUTER, TargetWorld.PHYSICAL},
            "master_orchestrator": {TargetWorld.DIGITAL, TargetWorld.COMPUTER, TargetWorld.PHYSICAL}
        }

    def is_agent_authorized(self, agent_name: str, world: TargetWorld) -> bool:
        """Verifies whether an agent is allowed to act within the target world"""
        allowed_worlds = self.agent_world_matrix.get(agent_name)
        if not allowed_worlds:
            return False
        return world in allowed_worlds


policy = PolicyEngine()
