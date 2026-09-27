"""
Short-Term Working Memory for J.A.R.V.I.S. (Phase 4 AI & Agent Architecture).
Maintains active conversation turns, goal progress, transient working variables,
and hierarchical rolling context summarization with zero context loss.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import List, Dict, Any, Optional, Callable
from collections import deque


@dataclass
class ConversationTurn:
    role: str                       # "user" or "jarvis"
    content: str
    timestamp: float = field(default_factory=time.time)
    intent: Optional[str] = None
    actions_taken: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "intent": self.intent,
            "actions": self.actions_taken,
            "time": self.timestamp
        }


class ShortTermMemory:
    """
    Working memory supporting rolling summarization.
    When active turns exceed threshold, older turns are distilled into a compact
    semantic summary and archived, ensuring zero context loss across long sessions.
    """
    def __init__(self, max_active_turns: int = 12, summary_batch_size: int = 4):
        self.max_active_turns = max_active_turns
        self.summary_batch_size = summary_batch_size
        self.history: deque[ConversationTurn] = deque()
        self.archived_turns: List[ConversationTurn] = []
        self.condensed_summary: Optional[str] = None
        self.active_goal: Optional[str] = None
        self.goal_steps_completed: List[str] = []
        self.context_scratchpad: Dict[str, Any] = {}
        self._archive_callback: Optional[Callable[[List[ConversationTurn], str], None]] = None

    def register_archive_callback(self, cb: Callable[[List[ConversationTurn], str], None]):
        """Registers a callback to receive archived turns and updated summary (e.g. for episodic storage)."""
        self._archive_callback = cb

    def add_turn(
        self,
        role: str,
        content: str,
        intent: Optional[str] = None,
        actions_taken: Optional[List[str]] = None
    ):
        turn = ConversationTurn(
            role=role,
            content=content,
            intent=intent,
            actions_taken=actions_taken or []
        )
        self.history.append(turn)

        # Check if rolling summarization threshold reached
        if len(self.history) > self.max_active_turns:
            self._roll_and_summarize()

    def _roll_and_summarize(self, keep_turns: int = 4):
        """Distills the oldest batch of turns into the rolling context summary and archives them."""
        num_to_roll = min(self.summary_batch_size, max(0, len(self.history) - keep_turns))
        if num_to_roll <= 0:
            if len(self.history) > keep_turns:
                num_to_roll = len(self.history) - keep_turns
            else:
                return

        evicted: List[ConversationTurn] = []
        for _ in range(num_to_roll):
            if self.history:
                evicted.append(self.history.popleft())

        if not evicted:
            return

        # Distill semantic synopsis from evicted turns
        synopsis_parts = []
        for turn in evicted:
            prefix = "User requested" if turn.role == "user" else "J.A.R.V.I.S. responded"
            snippet = turn.content.strip().replace("\n", " ")
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."
            if turn.actions_taken:
                actions_str = f" [actions: {', '.join(turn.actions_taken)}]"
            else:
                actions_str = ""
            synopsis_parts.append(f"{prefix} '{snippet}'{actions_str}")

        new_segment = "; ".join(synopsis_parts)
        if self.condensed_summary:
            # Merge while capping summary length to prevent token explosion
            self.condensed_summary = f"{self.condensed_summary} | Then: {new_segment}"
            if len(self.condensed_summary) > 600:
                self.condensed_summary = "..." + self.condensed_summary[-550:]
        else:
            self.condensed_summary = f"Earlier dialogue: {new_segment}"

        self.archived_turns.extend(evicted)

        if self._archive_callback:
            try:
                self._archive_callback(evicted, self.condensed_summary)
            except Exception:
                pass

    def compress_history(self) -> str:
        """Manually forces compression of active history into summary, keeping only the last 2 turns."""
        while len(self.history) > 2:
            before_len = len(self.history)
            self._roll_and_summarize(keep_turns=2)
            if len(self.history) >= before_len:
                # Guaranteed progress
                evicted = [self.history.popleft()]
                self.archived_turns.extend(evicted)
        return self.condensed_summary or ""

    def set_active_goal(self, goal: str):
        self.active_goal = goal
        self.goal_steps_completed.clear()

    def record_step(self, step_description: str):
        self.goal_steps_completed.append(step_description)

    def clear_goal(self):
        self.active_goal = None
        self.goal_steps_completed.clear()

    def clear_all(self):
        """Resets working memory, archived turns, and summary."""
        self.history.clear()
        self.archived_turns.clear()
        self.condensed_summary = None
        self.clear_goal()
        self.context_scratchpad.clear()

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        turns = list(self.history)[-limit:]
        return [t.to_dict() for t in turns]

    def get_full_context(self) -> Dict[str, Any]:
        """Returns the full hierarchical working memory representation."""
        return {
            "condensed_summary": self.condensed_summary,
            "active_turns": [t.to_dict() for t in self.history],
            "archived_turn_count": len(self.archived_turns),
            "active_goal": self.active_goal,
            "goal_steps": list(self.goal_steps_completed),
            "scratchpad_keys": list(self.context_scratchpad.keys())
        }

    def format_for_prompt(self, limit: int = 6) -> str:
        """
        Formats dialogue turns for LLM prompt injection.
        Prepends the condensed summary if prior conversation was distilled.
        """
        turns = list(self.history)[-limit:]
        lines = []

        if self.condensed_summary:
            lines.append(f"[Conversation Context Summary: {self.condensed_summary}]")
            lines.append("---")

        for t in turns:
            prefix = "User" if t.role == "user" else "J.A.R.V.I.S."
            lines.append(f"{prefix}: {t.content}")

        return "\n".join(lines)


short_term_memory = ShortTermMemory()
