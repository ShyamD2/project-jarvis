"""
Groq AI Provider for J.A.R.V.I.S. Brain.
Integrates Groq Llama-3.3-70B as the secondary, ultra-fast fallback reasoning engine.
"""

import os
import json
import time
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator
from services.brain.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("GroqProvider")


class GroqProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key if api_key is not None else os.getenv("GROQ_API_KEY", "").strip()
        self.model = model or os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        self.base_url = "https://api.groq.com/openai/v1"
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Returns or creates a persistent client with keep-alive connection pooling."""
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(max_keepalive_connections=20, max_connections=50, keepalive_expiry=120.0)
            try:
                import h2
                has_h2 = True
            except ImportError:
                has_h2 = False
            self._client = httpx.AsyncClient(timeout=25.0, limits=limits, http2=has_h2)
        return self._client

    @property
    def is_configured(self) -> bool:
        """Returns True if a valid API key is present."""
        return bool(self.api_key and self.api_key.strip() and not self.api_key.startswith("PASTE_"))

    def is_available(self) -> bool:
        """Alias for is_configured."""
        return self.is_configured

    def _convert_tool_specs_to_openai(self, tool_specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Converts generic tool schemas to OpenAI/Groq function calling format."""
        openai_tools = []
        for ts in tool_specs:
            params = ts.get("parameters", {})
            properties = {}
            required = []

            for p_name, p_spec in params.items():
                p_type = p_spec.get("type", "string").lower()
                if p_type in ["int", "integer", "number", "float"]:
                    p_type = "number"
                elif p_type in ["bool", "boolean"]:
                    p_type = "boolean"
                elif p_type in ["array", "list"]:
                    p_type = "array"
                else:
                    p_type = "string"

                properties[p_name] = {
                    "type": p_type,
                    "description": p_spec.get("description", p_name)
                }
                if p_spec.get("required"):
                    required.append(p_name)

            openai_tools.append({
                "type": "function",
                "function": {
                    "name": ts["name"],
                    "description": ts.get("description", ""),
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            })
        return openai_tools

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        messages: Optional[List[Dict[str, Any]]] = None
    ) -> LLMResponse:
        """Executes non-streaming completion via Groq with tool calling and multi-turn support."""
        if not self.is_configured:
            raise ValueError("GROQ_API_KEY is not configured.")

        start_time = time.time()
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        sys_msg = system_prompt or (
            "You are J.A.R.V.I.S., Tony Stark's cyber-physical AI assistant. "
            "Speak concisely, addressing the user as 'sir'."
        )

        if messages:
            chat_messages = messages
        else:
            chat_messages = [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt}
            ]

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": 4096
        }

        if tools:
            groq_tools = self._convert_tool_specs_to_openai(tools)
            if groq_tools:
                payload["tools"] = groq_tools
                payload["tool_choice"] = "auto"

        client = self._get_client()
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

        latency = (time.time() - start_time) * 1000
        choice = data["choices"][0]
        message = choice.get("message", {})
        content = message.get("content") or ""
        tool_calls: List[ToolCall] = []

        if "tool_calls" in message and message["tool_calls"]:
            for tc in message["tool_calls"]:
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except Exception:
                    args = {}
                tool_calls.append(
                    ToolCall(
                        tool_name=fn.get("name", ""),
                        arguments=args,
                        call_id=tc.get("id")
                    )
                )

        return LLMResponse(
            content=content.strip(),
            tool_calls=tool_calls,
            model=self.model,
            latency_ms=round(latency, 2)
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Streams text chunks directly from Groq's streaming API."""
        if not self.is_configured:
            raise ValueError("GROQ_API_KEY is not configured.")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        sys_msg = system_prompt or (
            "You are J.A.R.V.I.S., a witty, refined British AI assistant addressing the user as 'sir'."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "stream": True
        }

        client = self._get_client()
        async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    clean_line = line.strip()
                    if clean_line.startswith("data: "):
                        clean_line = clean_line[6:]
                    if clean_line == "[DONE]":
                        break
                    try:
                        chunk = json.loads(clean_line)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                    except Exception:
                        pass
