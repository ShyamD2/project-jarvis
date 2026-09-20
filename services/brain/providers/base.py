"""
Base LLM Provider interface for J.A.R.V.I.S. Brain.
Supports streaming, function calling, and multi-model routing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, AsyncGenerator


@dataclass
class ToolCall:
    tool_name: str
    arguments: Dict[str, Any]
    call_id: Optional[str] = None


@dataclass
class LLMResponse:
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    model: str = "unknown"
    finish_reason: str = "stop"
    tokens_prompt: int = 0
    tokens_completion: int = 0
    latency_ms: float = 0.0


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        messages: Optional[List[Dict[str, Any]]] = None
    ) -> LLMResponse:
        """Execute non-streaming inference with optional tools and multi-turn messages"""
        pass

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Stream token chunks for low-latency voice and UI synthesis"""
        pass
