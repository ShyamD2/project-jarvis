"""
Unified Multi-AI Reasoning Provider for J.A.R.V.I.S. Brain.
Supports:
1. Google Gemini (GEMINI_API_KEY)
2. OpenAI GPT-4o / GPT-4o-mini (OPENAI_API_KEY)
3. Groq Llama-3.3-70B (GROQ_API_KEY)
4. Local Ollama (http://localhost:11434)
5. Local Cognitive Reflex Engine (Zero-dependency offline fallback)
"""

import os
import json
import time
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator
from services.brain.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from services.brain.providers.mock_provider import MockLLMProvider
from services.brain.providers.ollama_provider import OllamaProvider
from services.brain.tools.registry import registry as tool_registry
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("UnifiedAIProvider")


class UnifiedAIProvider(BaseLLMProvider):
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.groq_key = os.getenv("GROQ_API_KEY", "").strip()
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
        self.ollama_provider = OllamaProvider(base_url=self.ollama_url)
        self.local_provider = MockLLMProvider("jarvis-local-cognitive-brain")

    @property
    def active_backend(self) -> str:
        if self.gemini_key:
            return "google-gemini-2.5-flash"
        elif self.openai_key:
            return "openai-gpt-4o"
        elif self.groq_key:
            return "groq-llama-3.3-70b"
        return "ollama-local / local-cognitive-reflex-engine"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7
    ) -> LLMResponse:
        # 1. Try Gemini
        if self.gemini_key:
            try:
                return await self._call_gemini(prompt, system_prompt, temperature)
            except Exception as e:
                logger.warning(f"Gemini API call failed, attempting fallback: {e}")

        # 2. Try OpenAI
        if self.openai_key:
            try:
                return await self._call_openai(prompt, system_prompt, temperature)
            except Exception as e:
                logger.warning(f"OpenAI API call failed, attempting fallback: {e}")

        # 3. Try Groq
        if self.groq_key:
            try:
                return await self._call_groq(prompt, system_prompt, temperature)
            except Exception as e:
                logger.warning(f"Groq API call failed, attempting fallback: {e}")

        # 4. Try Local Ollama if active
        try:
            return await self.ollama_provider.generate(prompt, system_prompt, tools, temperature)
        except Exception as e:
            logger.info(f"Local Ollama daemon unreachable ({e}); engaging local cognitive reflex engine.")

        # 5. Fallback to Local Cognitive Engine
        return await self.local_provider.generate(prompt, system_prompt, tools, temperature)

    async def _call_gemini(self, prompt: str, system_prompt: Optional[str], temperature: float) -> LLMResponse:
        start_time = time.time()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_key}"
        
        sys_instruction = system_prompt or (
            "You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), the cyber-physical AI assistant created for Tony Stark. "
            "You speak with a refined, witty British tone, addressing the user as 'sir'. "
            "Execute user tasks, assist with computer operations, and provide intelligent, succinct responses."
        )

        # Build tools schema for Gemini
        tool_specs = tool_registry.to_llm_tool_specs()
        declarations = []
        for ts in tool_specs:
            declarations.append({
                "name": ts["name"],
                "description": ts["description"],
                "parameters": {
                    "type": "OBJECT",
                    "properties": {k: {"type": "STRING"} for k in ts.get("parameters", {}).keys()}
                }
            })

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": sys_instruction}]},
            "generationConfig": {"temperature": temperature},
            "tools": [{"functionDeclarations": declarations}] if declarations else []
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        latency = (time.time() - start_time) * 1000
        text = ""
        tool_calls = []

        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for p in parts:
                if "text" in p:
                    text += p["text"]
                if "functionCall" in p:
                    fc = p["functionCall"]
                    tool_calls.append(ToolCall(tool_name=fc["name"], arguments=fc.get("args", {})))

        return LLMResponse(
            content=text or "Instruction processed across autonomous fabric, sir.",
            tool_calls=tool_calls,
            model="gemini-2.5-flash",
            latency_ms=round(latency, 2)
        )

    async def _call_openai(self, prompt: str, system_prompt: Optional[str], temperature: float) -> LLMResponse:
        start_time = time.time()
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"}

        sys_msg = system_prompt or "You are J.A.R.V.I.S., a witty, refined British AI assistant addressing the user as 'sir'."
        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt}
        ]

        payload = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": temperature
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        latency = (time.time() - start_time) * 1000
        choice = data["choices"][0]
        return LLMResponse(
            content=choice["message"].get("content", ""),
            model="gpt-4o-mini",
            latency_ms=round(latency, 2)
        )

    async def _call_groq(self, prompt: str, system_prompt: Optional[str], temperature: float) -> LLMResponse:
        start_time = time.time()
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"}

        sys_msg = system_prompt or "You are J.A.R.V.I.S., a witty, refined British AI assistant addressing the user as 'sir'."
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        latency = (time.time() - start_time) * 1000
        choice = data["choices"][0]
        return LLMResponse(
            content=choice["message"].get("content", ""),
            model="llama-3.3-70b-versatile",
            latency_ms=round(latency, 2)
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        res = await self.generate(prompt, system_prompt, temperature=temperature)
        for word in res.content.split():
            yield word + " "


unified_provider = UnifiedAIProvider()
