"""
Isolated Test Mock LLM Provider for Project J.A.R.V.I.S.
Configurable test double designed exclusively for unit/integration test fixtures,
supporting deterministic assertions, canned replies, tool calls, and fault injection.
"""

from __future__ import annotations
import time
from typing import List, Dict, Any, Optional, AsyncGenerator
from services.brain.providers.base import BaseLLMProvider, LLMResponse, ToolCall


class MockLLMProvider(BaseLLMProvider):
    """
    Test fixture provider that records calls, generates deterministic canned responses,
    and supports intentional exception raising for resilience testing.
    """

    def __init__(
        self,
        model_name: str = "mock-test-brain",
        default_response: str = "Mock test response",
        default_tool_calls: Optional[List[ToolCall]] = None,
        should_fail: bool = False,
        error_to_raise: Optional[Exception] = None
    ):
        self.model_name = model_name
        self.default_response = default_response
        self.default_tool_calls = default_tool_calls or []
        self.should_fail = should_fail
        self.error_to_raise = error_to_raise or RuntimeError("Simulated MockLLMProvider failure")
        self.calls: List[Dict[str, Any]] = []
        self._pattern_responses: Dict[str, tuple[str, List[ToolCall]]] = {}

    def set_pattern_response(self, pattern: str, response: str, tool_calls: Optional[List[ToolCall]] = None):
        """Map a substring pattern in the prompt to a specific response and tool call list."""
        self._pattern_responses[pattern.lower()] = (response, tool_calls or [])

    def reset(self):
        """Clears call history and pattern mappings."""
        self.calls.clear()
        self._pattern_responses.clear()
        self.should_fail = False

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7
    ) -> LLMResponse:
        start_time = time.time()
        self.calls.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "tools": tools,
            "temperature": temperature,
            "timestamp": start_time
        })

        if self.should_fail:
            raise self.error_to_raise

        # Check pattern responses
        p_lower = prompt.lower()
        response_text = self.default_response
        tool_calls = list(self.default_tool_calls)

        for pat, (resp, t_calls) in self._pattern_responses.items():
            if pat in p_lower:
                response_text = resp
                tool_calls = list(t_calls)
                break

        latency = (time.time() - start_time) * 1000
        return LLMResponse(
            content=response_text,
            tool_calls=tool_calls,
            model=self.model_name,
            finish_reason="tool_calls" if tool_calls else "stop",
            tokens_prompt=len(prompt.split()),
            tokens_completion=len(response_text.split()),
            latency_ms=round(latency, 2)
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        res = await self.generate(prompt, system_prompt=system_prompt, temperature=temperature)
        for word in res.content.split():
            yield word + " "
