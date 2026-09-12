"""
Intent Router for J.A.R.V.I.S. Brain.
Routes user inputs to the appropriate tier (Fast-Path Reflex vs Deep Reasoning Planner).
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional
import re


class IntentType(str, Enum):
    EMERGENCY = "emergency"
    DIRECT_ACTION = "direct_action"
    COMPLEX_PLAN = "complex_plan"
    CONVERSATION = "conversation"


@dataclass
class RoutedIntent:
    intent_type: IntentType
    confidence: float
    recommended_model_tier: str       # "tier_1_fast" or "tier_2_deep"
    target_tool: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    raw_query: str = ""


class IntentRouter:
    def __init__(self):
        # High-priority regex patterns for ultra-fast zero-latency classification (<1ms)
        self.emergency_patterns = [
            r"\b(stand\s*down|abort|kill\s*all|freeze|emergency\s*stop)\b"
        ]
        self.direct_action_patterns = [
            (r"\b(turn\s+on|turn\s+off|switch\s+on|switch\s+off|toggle)\b.*\b(light|lamp|fan|relay)\b", "control_physical_device"),
            (r"\b(volume\s+(up|down|mute|unmute))\b", "control_system_audio"),
            (r"\b(lock\s+(the\s+)?(pc|screen|computer))\b", "lock_screen"),
            (r"\b(open|launch|start|run)\b.*\b(opera|browser|chrome|edge|notepad|calculator|calc|vs\s*code|code|terminal|wt|spotify|discord)\b", "launch_app"),
            (r"\b(new\s+tab|open\s+tab|browse|google|search\s+for|open\s+website)\b", "browse_web"),
            (r"\b(close|kill|terminate|shut\s+down)\b.*\b(opera|browser|chrome|edge|notepad|calculator|calc|code|terminal)\b", "close_app"),
            (r"\b(prepare\s+(my\s+)?workspace)\b", "prepare_workspace")
        ]
        self.complex_plan_patterns = [
            r"\b(deploy|provision|terraform|kubernetes|docker\s+compose|debug|investigate|remediate|workflow)\b"
        ]

    def route(self, text: str) -> RoutedIntent:
        """Classifies text and determines optimal execution tier"""
        t = text.strip().lower()

        # 1. Emergency Circuit Breaker check
        for pat in self.emergency_patterns:
            if re.search(pat, t):
                return RoutedIntent(
                    intent_type=IntentType.EMERGENCY,
                    confidence=1.0,
                    recommended_model_tier="tier_1_fast",
                    raw_query=text
                )

        # 2. Fast-Path Direct Action check
        for pat, tool_name in self.direct_action_patterns:
            match = re.search(pat, t)
            if match:
                return RoutedIntent(
                    intent_type=IntentType.DIRECT_ACTION,
                    confidence=0.95,
                    recommended_model_tier="tier_1_fast",
                    target_tool=tool_name,
                    raw_query=text
                )

        # 3. Complex Multi-Step Planner check
        for pat in self.complex_plan_patterns:
            if re.search(pat, t):
                return RoutedIntent(
                    intent_type=IntentType.COMPLEX_PLAN,
                    confidence=0.90,
                    recommended_model_tier="tier_2_deep",
                    raw_query=text
                )

        # 4. Default: Conversational Reflex
        return RoutedIntent(
            intent_type=IntentType.CONVERSATION,
            confidence=0.85,
            recommended_model_tier="tier_1_fast",
            raw_query=text
        )


router = IntentRouter()
