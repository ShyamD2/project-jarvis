"""
Intent Router for J.A.R.V.I.S. Brain.
Routes user inputs to the appropriate tier (Fast-Path Reflex, Emergency Intercept, Confirmation Gate, or Deep Reasoning Planner).
Includes native Tanglish and multilingual semantic normalization.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
import re


class IntentType(str, Enum):
    EMERGENCY = "emergency"
    CONFIRMATION = "confirmation"
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
        # 1. Emergency Circuit Breaker patterns (<1ms zero-latency halt)
        self.emergency_patterns = [
            r"\b(jarvis\s+stop|stop\s+jarvis|emergency\s*stop|stand\s*down|abort|freeze|kill\s*all)\b",
            r"^(\s*stop\s*|\s*cancel\s*|\s*abort\s*)$"
        ]

        # 2. Confirmation gate patterns (approving pending Tier 2 / Tier 3 actions)
        self.confirmation_patterns = [
            r"\b(confirm|confirm\s+shutdown|confirm\s+restart|confirm\s+action|yes\s+proceed|proceed|approve|authorized)\b"
        ]

        # 3. Direct Action patterns with Tanglish & Hinglish normalization
        self.direct_action_patterns: list[Tuple[str, str, Optional[Dict[str, Any]]]] = [
            # Tanglish / Multilingual Audio
            (r"\b(volume\s+(konjam\s+)?(kammi|kurai)|konjam\s+kammi\s+pannu|thoda\s+(kam|volume\s+kam)\s+karo)\b", "control_system_audio", {"action": "decrease", "steps": 5}),
            (r"\b(volume\s+(konjam\s+)?(ethu|jaasti|increase)|konjam\s+volume\s+ethu|thoda\s+volume\s+badhao|aawaaz\s+badhao)\b", "control_system_audio", {"action": "increase", "steps": 5}),
            
            # Standard Audio & Media Controls
            (r"\b(increase|raise|turn\s+up|louder)\b.*\bvolume\b", "control_system_audio", {"action": "increase", "steps": 5}),
            (r"\b(decrease|lower|turn\s+down|quieter)\b.*\bvolume\b", "control_system_audio", {"action": "decrease", "steps": 5}),
            (r"\b(mute|unmute)\b.*\b(volume|audio|sound|pc)\b", "control_system_audio", {"action": "mute"}),
            (r"\bvolume\s+(\d{1,3})%?\b", "control_system_audio", None),
            (r"\b(play|pause|resume|next\s+track|previous\s+track|skip\s+song)\b", "audio_media", None),

            # Tanglish / Multilingual App Closing
            (r"\b(opera|chrome|calc|calculator|notepad|whatsapp)\s+(moodu|moodidu|bandh\s+karo)\b", "close_app", None),

            # Power & System Controls
            (r"\b(shut\s*down|power\s*off|turn\s*off)\b.*\b(computer|pc|system)\b", "pc_power", {"action": "shutdown"}),
            (r"\b(restart|reboot)\b.*\b(computer|pc|system)\b", "pc_power", {"action": "restart"}),
            (r"\b(sleep|hibernate|turn\s*off\s*display|lock\s*screen|lock\s*pc)\b", "pc_power", None),
            (r"\b(cancel\s+(scheduled\s+)?shutdown)\b", "pc_power", {"action": "cancel_shutdown"}),

            # Physical IoT
            (r"\b(turn\s+on|turn\s+off|switch\s+on|switch\s+off|toggle)\b.*\b(light|lamp|fan|relay)\b", "control_physical_device", None),

            # Browser & Navigation
            (r"\b(open|show|display)\b.*\b(bookmark|bookmarks)\b", "manage_browser", {"action": "open_bookmarks"}),
            (r"\b(close|shut)\b.*\b(tab|current\s+tab|active\s+tab)\b", "manage_browser", {"action": "close_tab"}),
            (r"\b(close|shut)\b.*\b(window|active\s+window|this\s+window)\b", "manage_browser", {"action": "close_window"}),
            (r"\b(new\s+tab|open\s+tab|browse|google|search\s+for|open\s+website)\b", "browse_web", None),

            # Messaging (WhatsApp)
            (r"\b(message|text|send\s+message)\b", "send_message", None),
            (r"\b(check|read)\b.*\b(message|messages|whatsapp|chat)\b", "send_message", {"action": "check_latest"}),

            # App Launch & Termination
            (r"\b(open|launch|start|run)\b.*\b(whatsapp|opera|browser|chrome|edge|notepad|calculator|calc|vs\s*code|code|terminal|wt|spotify|discord|instagram|youtube)\b", "launch_app", None),
            (r"\b(close|shut\s+down|kill|terminate)\b.*\b(all|all\s+apps|all\s+of\s+them|everything)\b", "close_app", {"app_name": "all"}),
            (r"\b(close|kill|terminate|shut\s+down)\b.*\b(opera|browser|chrome|edge|notepad|calculator|calc|code|terminal|whatsapp)\b", "close_app", None),

            # Mouse & Keyboard
            (r"\b(take\s+screenshot|capture\s+screen|screen\s+record)\b", "mouse_keyboard", None),
            (r"\b(press|type|scroll|click)\b", "mouse_keyboard", None),

            # Telemetry & Network
            (r"\b(cpu|ram|memory|disk|battery|temperature|vitals|hardware)\b", "query_system_telemetry", None),
            (r"\b(wifi|ip\s+address|ping|network\s+status|internet\s+status)\b", "network_control", None),
            (r"\b(take\s+note|quick\s+note|add\s+task|remind\s+me|set\s+timer)\b", "productivity_tool", None),

            # Compound Pipelines
            (r"\b(prepare\s+(my\s+)?workspace|start\s+my\s+development\s+environment)\b", "compound_workflow", {"workflow": "dev_environment"}),
            (r"\b(start\s+(my\s+)?aws\s+workspace)\b", "compound_workflow", {"workflow": "aws_workspace"}),
            (r"\b(movie\s+mode)\b", "compound_workflow", {"workflow": "movie_mode"}),
            (r"\b(prepare\s+(pc\s+for\s+)?shutdown)\b", "compound_workflow", {"workflow": "shutdown_prep"})
        ]

        # 4. Complex Planner patterns
        self.complex_plan_patterns = [
            r"\b(deploy|provision|terraform|kubernetes|docker\s+compose|debug|investigate|remediate|multi-step)\b"
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

        # 2. Confirmation Gate check
        for pat in self.confirmation_patterns:
            if re.search(pat, t):
                return RoutedIntent(
                    intent_type=IntentType.CONFIRMATION,
                    confidence=0.98,
                    recommended_model_tier="tier_1_fast",
                    raw_query=text
                )

        # 3. Fast-Path Direct Action check
        for item in self.direct_action_patterns:
            pat = item[0]
            tool_name = item[1]
            default_params = item[2] if len(item) > 2 else None
            match = re.search(pat, t)
            if match:
                return RoutedIntent(
                    intent_type=IntentType.DIRECT_ACTION,
                    confidence=0.95,
                    recommended_model_tier="tier_1_fast",
                    target_tool=tool_name,
                    parameters=default_params,
                    raw_query=text
                )

        # 4. Complex Multi-Step Planner check
        for pat in self.complex_plan_patterns:
            if re.search(pat, t):
                return RoutedIntent(
                    intent_type=IntentType.COMPLEX_PLAN,
                    confidence=0.90,
                    recommended_model_tier="tier_2_deep",
                    raw_query=text
                )

        # 5. Default: Conversational Reflex
        return RoutedIntent(
            intent_type=IntentType.CONVERSATION,
            confidence=0.85,
            recommended_model_tier="tier_1_fast",
            raw_query=text
        )


router = IntentRouter()
