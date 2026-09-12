"""
AIManager for Project J.A.R.V.I.S.
Central nervous system coordinating Primary AI (Google Gemini) and Secondary Fallback (Groq).
All JARVIS components communicate through AIManager.
"""

import os
from typing import List, Dict, Any, Optional, AsyncGenerator
from services.brain.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from services.brain.providers.gemini_provider import GeminiProvider
from services.brain.providers.groq_provider import GroqProvider
from services.brain.providers.mock_provider import MockLLMProvider
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisAIManager")


class AIManager(BaseLLMProvider):
    def __init__(self):
        self.gemini = GeminiProvider()
        self.groq = GroqProvider()
        self.local = MockLLMProvider("jarvis-local-cognitive-brain")

    def refresh_keys(self):
        """Refreshes API keys dynamically from environment or .env."""
        self.gemini.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.groq.api_key = os.getenv("GROQ_API_KEY", "").strip()

    def get_key_status(self) -> Dict[str, Any]:
        """
        Evaluates key presence without exposing raw key secrets.
        Returns:
        Both: 'JARVIS AI systems online.'
        Only Gemini: 'JARVIS online. Gemini is active.'
        Only Groq: 'JARVIS online. Groq is active.'
        Neither: 'AI API keys are not configured. Please add your Gemini or Groq key.'
        """
        self.refresh_keys()
        has_gemini = self.gemini.is_configured
        has_groq = self.groq.is_configured

        if has_gemini and has_groq:
            status_message = "JARVIS AI systems online."
        elif has_gemini:
            status_message = "JARVIS online. Gemini is active."
        elif has_groq:
            status_message = "JARVIS online. Groq is active."
        else:
            status_message = "AI API keys are not configured. Please add your Gemini or Groq key."

        return {
            "status_message": status_message,
            "gemini_status": "Configured" if has_gemini else "Not configured",
            "groq_status": "Configured" if has_groq else "Not configured",
            "active_provider": (
                f"google-gemini-flash (primary)" if has_gemini else (
                    f"groq-{getattr(self.groq, 'model', 'default')} (fallback)" if has_groq else "local-cognitive-reflex (offline)"
                )
            )
        }

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7
    ) -> LLMResponse:
        """
        Coordinates primary and fallback AI generation:
        JARVIS -> AIManager -> Gemini -> (if failure) -> Groq -> JARVIS
        """
        self.refresh_keys()
        gemini_attempted = False
        gemini_failed = False

        # 1. Primary: Google Gemini
        if self.gemini.is_configured:
            gemini_attempted = True
            try:
                gemini_model = getattr(self.gemini, "model", "gemini-flash")
                logger.info(f"[AIManager] Invoking Primary AI Provider: Google Gemini ({gemini_model})")
                return await self.gemini.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    tools=tools,
                    temperature=temperature
                )
            except Exception as e:
                gemini_failed = True
                logger.warning(f"[AIManager] Primary AI (Gemini) failed: {e}. Cascading to fallback provider...")

        # 2. Secondary / Fallback: Groq
        if self.groq.is_configured:
            try:
                groq_model = getattr(self.groq, "model", "groq")
                logger.info(f"[AIManager] Invoking Fallback AI Provider: Groq ({groq_model})")
                return await self.groq.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    tools=tools,
                    temperature=temperature
                )
            except Exception as e:
                logger.error(f"[AIManager] Fallback AI (Groq) failed: {e}")
                if gemini_attempted:
                    return LLMResponse(
                        content="Both primary (Gemini) and fallback (Groq) AI providers are currently unavailable. Please check your network connection or API limits, sir.",
                        model="error-fallback"
                    )

        # 3. Handle cases where Gemini failed and Groq was not configured
        if gemini_failed:
            return LLMResponse(
                content="The primary AI provider (Gemini) encountered an error, and secondary provider (Groq) is not configured, sir.",
                model="error-gemini-only"
            )

        # 4. Neither key is configured: Offline / Local Cognitive Reflex
        logger.info("[AIManager] No cloud API keys configured. Engaging local cognitive reflex engine.")
        # If user asks conversational questions without keys, give helpful guidance
        p_clean = prompt.strip().lower()
        if p_clean in ["hello", "hello jarvis", "hi", "hey jarvis"]:
            return LLMResponse(
                content="AI API keys are not configured. Please add your Gemini or Groq key into your .env file to enable cloud reasoning, sir.",
                model="local-reflex-advisory"
            )

        return await self.local.generate(prompt, system_prompt, tools, temperature)

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Streams text chunks through Gemini -> Groq fallback cascade."""
        self.refresh_keys()

        if self.gemini.is_configured:
            try:
                async for chunk in self.gemini.stream(prompt, system_prompt, temperature):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"[AIManager Stream] Primary (Gemini) failed: {e}. Falling back to Groq...")

        if self.groq.is_configured:
            try:
                async for chunk in self.groq.stream(prompt, system_prompt, temperature):
                    yield chunk
                return
            except Exception as e:
                logger.error(f"[AIManager Stream] Fallback (Groq) failed: {e}")

        yield "AI API keys are not configured. Please add your Gemini or Groq key into your .env file."


ai_manager = AIManager()
