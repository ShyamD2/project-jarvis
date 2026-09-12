"""
Google Gemini AI Provider for J.A.R.V.I.S. Brain.
Integrates Gemini 2.5 Flash as the primary high-speed reasoning engine with function calling.
"""

import os
import json
import time
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator
from services.brain.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("GeminiProvider")


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-flash-latest"):
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "").strip()
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    @property
    def is_configured(self) -> bool:
        """Returns True if a valid API key is present."""
        return bool(self.api_key and self.api_key.strip() and not self.api_key.startswith("PASTE_"))

    def _convert_tool_specs_to_gemini(self, tool_specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Converts generic tool schemas to Google Gemini functionDeclaration schema."""
        declarations = []
        for ts in tool_specs:
            params = ts.get("parameters", {})
            properties = {}
            required = []

            for p_name, p_spec in params.items():
                p_type = p_spec.get("type", "string").upper()
                if p_type == "STRING":
                    properties[p_name] = {"type": "STRING", "description": p_spec.get("description", p_name)}
                elif p_type in ["INTEGER", "INT", "NUMBER", "FLOAT"]:
                    properties[p_name] = {"type": "NUMBER", "description": p_spec.get("description", p_name)}
                elif p_type in ["BOOLEAN", "BOOL"]:
                    properties[p_name] = {"type": "BOOLEAN", "description": p_spec.get("description", p_name)}
                elif p_type in ["ARRAY", "LIST"]:
                    properties[p_name] = {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": p_spec.get("description", p_name)
                    }
                else:
                    properties[p_name] = {"type": "STRING", "description": p_spec.get("description", p_name)}

                if p_spec.get("required"):
                    required.append(p_name)

            declarations.append({
                "name": ts["name"],
                "description": ts.get("description", ""),
                "parameters": {
                    "type": "OBJECT",
                    "properties": properties,
                    "required": required
                }
            })
        return declarations

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7
    ) -> LLMResponse:
        """Executes a non-streaming completion via Gemini API with function calling."""
        if not self.is_configured:
            raise ValueError("GEMINI_API_KEY is not configured.")

        start_time = time.time()
        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        sys_instruction = system_prompt or (
            "You are J.A.R.V.I.S., Tony Stark's cyber-physical AI assistant. "
            "Speak concisely and elegantly, addressing the user as 'sir'. "
            "Use available tools to perform computer, browser, and cloud operations."
        )

        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": sys_instruction}]},
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 1024
            }
        }

        if tools:
            gemini_declarations = self._convert_tool_specs_to_gemini(tools)
            if gemini_declarations:
                payload["tools"] = [{"functionDeclarations": gemini_declarations}]

        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        latency = (time.time() - start_time) * 1000
        text = ""
        tool_calls: List[ToolCall] = []

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
            content=text.strip(),
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
        """Streams text chunks directly from Gemini's streamGenerateContent endpoint."""
        if not self.is_configured:
            raise ValueError("GEMINI_API_KEY is not configured.")

        url = f"{self.base_url}/models/{self.model}:streamGenerateContent"
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        sys_instruction = system_prompt or (
            "You are J.A.R.V.I.S., a witty, refined British AI assistant addressing the user as 'sir'."
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": sys_instruction}]},
            "generationConfig": {"temperature": temperature}
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    clean_line = line.strip()
                    if clean_line.startswith("data: "):
                        clean_line = clean_line[6:]
                    try:
                        chunk_json = json.loads(clean_line)
                        cands = chunk_json.get("candidates", [])
                        if cands:
                            for part in cands[0].get("content", {}).get("parts", []):
                                if "text" in part:
                                    yield part["text"]
                    except Exception:
                        pass
