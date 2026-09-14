"""
Context Manager & Reference Resolution Engine for Project J.A.R.V.I.S.
Maintains short-term conversational context (last 15 turns), tracks active computer/browser state,
and resolves references ("and RAM?", "the first result", "do that again", "close it").
"""

from __future__ import annotations
import re
import time
from typing import Dict, Any, List, Optional, Tuple
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.config import config

logger = get_logger("JarvisContextManager")


class ContextManager:
    def __init__(self, max_turns: Optional[int] = None):
        self.max_turns = max_turns or getattr(config, "max_context_messages", 15)
        self.turns: List[Dict[str, Any]] = []

        # Operational Context
        self.focused_app: Optional[str] = None
        self.active_window: Optional[str] = None
        self.last_browser_url: Optional[str] = None
        self.last_search_results: List[Dict[str, str]] = []
        self.last_executed_tool: Optional[str] = None
        self.last_tool_params: Dict[str, Any] = {}
        self.last_intent: Optional[str] = None

    def add_turn(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Records a conversational turn with timestamp and optional execution metadata."""
        turn = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }
        self.turns.append(turn)
        if len(self.turns) > self.max_turns:
            self.turns.pop(0)

        # Update operational state if provided in metadata
        if metadata:
            if "focused_app" in metadata:
                self.focused_app = metadata["focused_app"]
            if "active_window" in metadata:
                self.active_window = metadata["active_window"]
            if "browser_url" in metadata:
                self.last_browser_url = metadata["browser_url"]
            if "search_results" in metadata and isinstance(metadata["search_results"], list):
                self.last_search_results = metadata["search_results"]
            if "tool" in metadata:
                self.last_executed_tool = metadata["tool"]
            if "params" in metadata:
                self.last_tool_params = metadata["params"]
            if "intent" in metadata:
                self.last_intent = metadata["intent"]

    def record_search_results(self, results: List[Dict[str, str]]):
        """Caches search query results for subsequent ordinal selection ('open the first result')."""
        self.last_search_results = results
        logger.debug(f"[ContextManager] Cached {len(results)} search results")

    def record_tool_execution(self, tool_name: str, params: Dict[str, Any], focused_app: Optional[str] = None):
        """Records executed tool parameters for potential replay or pronoun targeting."""
        self.last_executed_tool = tool_name
        self.last_tool_params = params
        if focused_app:
            self.focused_app = focused_app

    def resolve_references(self, query: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Analyzes the user's input query in light of previous turns and operational context.
        Resolves pronouns ('it', 'that'), follow-ups ('and RAM?'), ordinals ('the first result'),
        and contextual repetitions ('do that again').
        Returns:
            (resolved_query: str, contextual_hints: Optional[dict])
        """
        q = query.strip()
        lower_q = q.lower()
        hints: Dict[str, Any] = {}

        # 1. Follow-up Telemetry queries: "And RAM?", "what about CPU?", "how about disk?"
        if re.search(r"^(?:and|what\s+about|how\s+about)\s+(?:the\s+)?(ram|cpu|disk|battery|gpu|memory)(?:\s+usage|\s+status)?\??$", lower_q):
            match = re.search(r"(ram|cpu|disk|battery|gpu|memory)", lower_q)
            if match:
                metric = match.group(1)
                if metric in ("ram", "memory"):
                    resolved = "check RAM usage"
                elif metric == "cpu":
                    resolved = "check CPU usage"
                elif metric == "disk":
                    resolved = "check free disk space"
                elif metric == "battery":
                    resolved = "check battery status"
                elif metric == "gpu":
                    resolved = "check GPU usage"
                else:
                    resolved = f"check {metric} usage"
                logger.info(f"🔗 [Context Resolved] '{q}' -> '{resolved}' (Metric: {metric})")
                return resolved, {"resolved_metric": metric, "context_type": "telemetry_followup"}

        # 2. Ordinal search selection: "open the first result", "click the second one", "open #1"
        ordinal_pattern = r"\b(?:open|click|view|go\s+to)\s+(?:the\s+)?(first|1st|second|2nd|third|3rd|fourth|4th|last)\s*(?:result|link|one|page)?\b"
        ord_match = re.search(ordinal_pattern, lower_q)
        if ord_match:
            ord_word = ord_match.group(1).lower()
            idx_map = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "4th": 3, "last": -1}
            idx = idx_map.get(ord_word, 0)

            if self.last_search_results:
                target_result = self.last_search_results[idx] if idx < len(self.last_search_results) else self.last_search_results[0]
                url = target_result.get("url") or target_result.get("link")
                if url:
                    resolved = f"open website {url}"
                    logger.info(f"🔗 [Context Resolved] '{q}' -> '{resolved}' (Ordinal: {ord_word})")
                    return resolved, {"resolved_url": url, "context_type": "search_ordinal"}
            else:
                # If no search results in memory, pass as general directive
                resolved = f"open the {ord_word} result"
                return resolved, {"ordinal": idx}

        # 3. Action Replay: "do that again", "repeat that", "once more", "again"
        if lower_q in ("do that again", "repeat that", "once more", "again", "do it again"):
            if self.last_executed_tool:
                hints = {
                    "replay_tool": self.last_executed_tool,
                    "replay_params": self.last_tool_params,
                    "context_type": "replay"
                }
                # Formulate a safe human query representation
                if self.last_executed_tool == "control_system_audio":
                    action = self.last_tool_params.get("action", "")
                    resolved = f"volume {action}"
                elif self.last_executed_tool == "launch_app":
                    resolved = f"open {self.last_tool_params.get('app_name', '')}"
                else:
                    resolved = f"execute {self.last_executed_tool}"
                logger.info(f"🔗 [Context Resolved] Replay '{q}' -> '{resolved}' ({self.last_executed_tool})")
                return resolved, hints

        # 4. Target Application Resolution: "close it", "minimize it", "focus it"
        target_it_match = re.search(r"^(?:close|minimize|maximize|focus)\s+(?:it|this|that|the\s+window|the\s+app)$", lower_q)
        if target_it_match:
            verb = lower_q.split()[0]
            if self.focused_app:
                resolved = f"{verb} {self.focused_app}"
                logger.info(f"🔗 [Context Resolved] Pronoun '{q}' -> '{resolved}' (Target: {self.focused_app})")
                return resolved, {"target_app": self.focused_app, "context_type": "pronoun_resolution"}
            elif self.active_window:
                resolved = f"{verb} {self.active_window}"
                return resolved, {"target_window": self.active_window, "context_type": "pronoun_resolution"}

        # 5. Volume adjustment pronouns: "make it louder", "make it softer", "turn it up", "turn it down"
        if re.search(r"\b(?:make\s+it|turn\s+it)\s+(?:louder|higher|up)\b", lower_q):
            return "increase volume by 5 steps", {"context_type": "audio_relative"}
        if re.search(r"\b(?:make\s+it|turn\s+it)\s+(?:softer|lower|down|quieter)\b", lower_q):
            return "decrease volume by 5 steps", {"context_type": "audio_relative"}

        # 6. Alternative Browser: "use the other browser", "switch browser"
        if "other browser" in lower_q or "switch browser" in lower_q:
            if self.focused_app and "opera" in self.focused_app.lower():
                return "open Google Chrome", {"switched_to": "chrome"}
            else:
                return "open Opera GX", {"switched_to": "opera"}

        return q, None

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Returns the bounded list of conversation turns."""
        return list(self.turns)

    def clear(self):
        """Clears conversational and operational memory."""
        self.turns.clear()
        self.focused_app = None
        self.active_window = None
        self.last_browser_url = None
        self.last_search_results.clear()
        self.last_executed_tool = None
        self.last_tool_params.clear()
        self.last_intent = None


context_manager = ContextManager()
