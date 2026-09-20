"""
AIManager for Project J.A.R.V.I.S.
Central nervous system coordinating Primary AI (OpenRouter / Groq / Google Gemini)
with intelligent cascading and offline cognitive reflex fallback.
All JARVIS components communicate through AIManager.
"""

import os
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from services.brain.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from services.brain.providers.openrouter_provider import OpenRouterProvider
from services.brain.providers.gemini_provider import GeminiProvider
from services.brain.providers.groq_provider import GroqProvider
from services.brain.providers.mock_provider import MockLLMProvider
from services.brain.providers.ollama_provider import OllamaProvider
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisAIManager")


class AIManager(BaseLLMProvider):
    def __init__(self):
        self.openrouter = OpenRouterProvider()
        self.gemini = GeminiProvider()
        self.groq = GroqProvider()
        self.ollama = OllamaProvider()
        self.local = MockLLMProvider("jarvis-local-cognitive-brain")
        default_pref = "groq" if self.groq.is_configured else ("openrouter" if self.openrouter.is_configured else "gemini")
        self.preferred_provider = os.getenv("JARVIS_PRIMARY_AI", default_pref).strip().lower()

    def set_primary_provider(self, name: str):
        name_clean = name.strip().lower()
        if name_clean in ["openrouter", "groq", "gemini"]:
            self.preferred_provider = name_clean
            logger.info(f"[AIManager] Primary AI engine set to: {name_clean}")

    def refresh_keys(self):
        """Refreshes API keys dynamically from environment or .env."""
        self.openrouter.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.openrouter.model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct").strip()
        self.gemini.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.groq.api_key = os.getenv("GROQ_API_KEY", "").strip()
        env_pref = os.getenv("JARVIS_PRIMARY_AI", "").strip().lower()
        if env_pref:
            self.preferred_provider = env_pref

    def get_key_status(self) -> Dict[str, Any]:
        """
        Evaluates key presence without exposing raw key secrets.
        """
        self.refresh_keys()
        has_openrouter = self.openrouter.is_configured
        has_gemini = self.gemini.is_configured
        has_groq = self.groq.is_configured

        configured = []
        if has_openrouter:
            configured.append(f"OpenRouter ({self.openrouter.model})")
        if has_groq:
            configured.append("Groq")
        if has_gemini:
            configured.append("Gemini")

        if configured:
            status_message = f"JARVIS AI systems online ({self.preferred_provider.upper()} active). Configured: {', '.join(configured)}."
        else:
            status_message = "AI API keys are not configured. Please add your OpenRouter, Groq, or Gemini key."

        if self.preferred_provider == "openrouter" and has_openrouter:
            active_label = f"openrouter-{self.openrouter.model} (primary)"
        elif self.preferred_provider == "groq" and has_groq:
            active_label = f"groq-{getattr(self.groq, 'model', 'default')} (high-speed)"
        elif self.preferred_provider == "gemini" and has_gemini:
            active_label = "google-gemini-flash (primary)"
        elif has_openrouter:
            active_label = f"openrouter-{self.openrouter.model}"
        elif has_groq:
            active_label = f"groq-{getattr(self.groq, 'model', 'default')}"
        elif has_gemini:
            active_label = "google-gemini-flash"
        else:
            active_label = "local-cognitive-reflex (offline)"

        return {
            "status_message": status_message,
            "openrouter_status": "Configured" if has_openrouter else "Not configured",
            "openrouter_model": self.openrouter.model,
            "gemini_status": "Configured" if has_gemini else "Not configured",
            "groq_status": "Configured" if has_groq else "Not configured",
            "ollama_status": f"Configured ({self.ollama.model})",
            "ollama_model": self.ollama.model,
            "preferred_provider": self.preferred_provider,
            "active_provider": active_label
        }

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        messages: Optional[List[Dict[str, Any]]] = None
    ) -> LLMResponse:
        """
        Coordinates primary and fallback AI generation with resilient multi-tier routing:
        Preferred Provider -> Fallbacks -> Local Cognitive Reflex
        """
        self.refresh_keys()

        # 1. Preferred Provider Attempt
        if self.preferred_provider == "openrouter" and self.openrouter.is_configured:
            try:
                logger.info(f"[AIManager] Invoking OpenRouter ({self.openrouter.model})...")
                return await self.openrouter.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    tools=tools,
                    temperature=temperature,
                    messages=messages
                )
            except Exception as e:
                logger.warning(f"[AIManager] OpenRouter failed: {e}. Cascading to fallback providers...")

        elif self.preferred_provider == "groq" and self.groq.is_configured:
            try:
                groq_model = getattr(self.groq, "model", "groq")
                logger.info(f"[AIManager] Invoking Groq High-Speed Provider: ({groq_model})")
                return await self.groq.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    tools=tools,
                    temperature=temperature,
                    messages=messages
                )
            except Exception as e:
                logger.warning(f"[AIManager] Groq Provider failed: {e}. Cascading to fallback providers...")

        elif self.preferred_provider == "gemini" and self.gemini.is_configured:
            try:
                gemini_model = getattr(self.gemini, "model", "gemini-flash")
                logger.info(f"[AIManager] Invoking Google Gemini Provider: ({gemini_model})")
                return await asyncio.wait_for(
                    self.gemini.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        tools=tools,
                        temperature=temperature
                    ),
                    timeout=4.0
                )
            except Exception as e:
                logger.warning(f"[AIManager] Gemini failed: {e}. Cascading to fallback providers...")

        # 2. Resilient Cascades (Try any remaining configured providers)
        # Try OpenRouter if not already attempted
        if self.preferred_provider != "openrouter" and self.openrouter.is_configured:
            try:
                logger.info(f"[AIManager] Fallback to OpenRouter ({self.openrouter.model})...")
                return await self.openrouter.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    tools=tools,
                    temperature=temperature,
                    messages=messages
                )
            except Exception as e:
                logger.warning(f"[AIManager] OpenRouter fallback failed: {e}")

        # Try Groq if not already attempted
        if self.preferred_provider != "groq" and self.groq.is_configured:
            try:
                groq_model = getattr(self.groq, "model", "groq")
                logger.info(f"[AIManager] Fallback to Groq ({groq_model})...")
                return await self.groq.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    tools=tools,
                    temperature=temperature,
                    messages=messages
                )
            except Exception as e:
                logger.warning(f"[AIManager] Groq fallback failed: {e}")

        # Try Gemini if not already attempted
        if self.preferred_provider != "gemini" and self.gemini.is_configured:
            try:
                logger.info(f"[AIManager] Fallback to Google Gemini...")
                return await asyncio.wait_for(
                    self.gemini.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        tools=tools,
                        temperature=temperature
                    ),
                    timeout=4.0
                )
            except Exception as e:
                logger.warning(f"[AIManager] Gemini fallback failed: {e}")

        # 3. Local Offline Autonomous Brain (Ollama)
        try:
            if await self.ollama.is_available(timeout=0.6):
                logger.info(f"[AIManager] Cascading to Local Offline Brain (Ollama - {self.ollama.model})...")
                return await self.ollama.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    tools=tools,
                    temperature=temperature
                )
        except Exception as e:
            logger.warning(f"[AIManager] Ollama fallback failed: {e}")

        # 4. No cloud provider or Ollama succeeded -> Local Cognitive Reflex
        logger.info("[AIManager] Engaging local cognitive reflex engine.")
        p_clean = prompt.strip().lower()
        if p_clean in ["hello", "hello jarvis", "hi", "hey jarvis"]:
            return LLMResponse(
                content="AI API keys are not configured. Please add your OpenRouter, Groq, or Gemini key into your .env file to enable cloud reasoning, sir.",
                model="local-reflex-advisory"
            )

        return await self.local.generate(prompt, system_prompt, tools, temperature)

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Streams text chunks through OpenRouter -> Groq -> Gemini fallback cascade."""
        self.refresh_keys()

        # Preferred Provider
        if self.preferred_provider == "openrouter" and self.openrouter.is_configured:
            try:
                async for chunk in self.openrouter.stream(prompt, system_prompt, temperature):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"[AIManager Stream] OpenRouter failed: {e}. Falling back...")

        elif self.preferred_provider == "groq" and self.groq.is_configured:
            try:
                async for chunk in self.groq.stream(prompt, system_prompt, temperature):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"[AIManager Stream] Groq failed: {e}. Falling back...")

        # Fallbacks
        if self.preferred_provider != "openrouter" and self.openrouter.is_configured:
            try:
                async for chunk in self.openrouter.stream(prompt, system_prompt, temperature):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"[AIManager Stream] OpenRouter fallback failed: {e}")

        if self.preferred_provider != "groq" and self.groq.is_configured:
            try:
                async for chunk in self.groq.stream(prompt, system_prompt, temperature):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"[AIManager Stream] Groq fallback failed: {e}")

        if self.gemini.is_configured:
            try:
                async for chunk in self.gemini.stream(prompt, system_prompt, temperature):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"[AIManager Stream] Gemini fallback failed: {e}")

        # Local Ollama Streaming Fallback
        try:
            if await self.ollama.is_available(timeout=0.6):
                async for chunk in self.ollama.stream(prompt, system_prompt, temperature):
                    yield chunk
                return
        except Exception as e:
            logger.warning(f"[AIManager Stream] Ollama fallback failed: {e}")

        yield "AI API keys are not configured. Please add your OpenRouter, Groq, or Gemini key into your .env file."


ai_manager = AIManager()
