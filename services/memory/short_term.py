"""
Short-Term Working Memory for J.A.R.V.I.S.
Maintains active conversation turns, goal progress, and transient working variables.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import List, Dict, Any, Optional
from collections import deque


@dataclass
class ConversationTurn:
    role: str                       # "user" or "jarvis"
    content: str
    timestamp: float = field(default_factory=time.time)
    intent: Optional[str] = None
    actions_taken: List[str] = field(default_factory=list)


class ShortTermMemory:
    def __init__(self, max_turns: int = 20):
        self.history: deque[ConversationTurn] = deque(maxlen=max_turns)
        self.active_goal: Optional[str] = None
        self.goal_steps_completed: List[str] = []
        self.context_scratchpad: Dict[str, Any] = {}

    def add_turn(self, role: str, content: str, intent: Optional[str] = None, actions_taken: Optional[List[str]] = None):
        turn = ConversationTurn(
            role=role,
            content=content,
            intent=intent,
            actions_taken=actions_taken or []
        )
        self.history.append(turn)

    def set_active_goal(self, goal: str):
        self.active_goal = goal
        self.goal_steps_completed.clear()

    def record_step(self, step_description: str):
        self.goal_steps_completed.append(step_description)

    def clear_goal(self):
        self.active_goal = None
        self.goal_steps_completed.clear()

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        turns = list(self.history)[-limit:]
        return [
            {
                "role": t.role,
                "content": t.content,
                "intent": t.intent,
                "actions": t.actions_taken,
                "time": t.timestamp
            }
            for t in turns
        ]

    def format_for_prompt(self, limit: int = 6) -> str:
        """Formats recent dialogue turns for LLM prompt injection"""
        turns = list(self.history)[-limit:]
        lines = []
        for t in turns:
            prefix = "User" if t.role == "user" else "J.A.R.V.I.S."
            lines.append(f"{prefix}: {t.content}")
        return "\n".join(lines)


short_term_memory = ShortTermMemory()
