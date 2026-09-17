"""
Conversational Engine for Project J.A.R.V.I.S.
Provides high-level multi-turn orchestration, context & reference resolution,
safety confirmation tickets for Tier 3 destructive actions, compound command decomposition,
and instant Emergency STOP prioritization.
"""

from __future__ import annotations
import re
import time
from typing import Dict, Any, Optional, List, Tuple
from shared.sdk_python.jarvis_sdk.logger import get_logger
from services.brain.context_manager import context_manager
from services.brain.response_generator import response_generator
from services.brain.agent_runtime import runtime as brain_runtime
from agents.intelligence.emergency_stop import emergency_stop
from services.voice.tts_engine import tts_engine

logger = get_logger("JarvisConversationEngine")


class ConversationEngine:
    DESTRUCTIVE_PATTERNS = [
        (r"\b(?:shut\s*down|power\s*off)\s*(?:the\s+)?(?:pc|computer|system)?\b", "shutdown_pc", "Shutting down the computer will close all running applications. Are you certain you wish to proceed, sir?"),
        (r"\brestart\s*(?:the\s+)?(?:pc|computer|system)\b", "restart_pc", "Restarting the workstation will terminate current processes. Shall I proceed with the restart, sir?"),
        (r"\bterraform\s+destroy\b", "terraform_destroy", "Terraform destroy will tear down cloud resources. Would you like me to proceed with destroying the infrastructure, sir?"),
        (r"\b(?:delete|destroy|terminate)\s+(?:all\s+)?(?:aws|cloud|database|cluster)\b", "cloud_destroy", "This destructive cloud action cannot be undone. Are you sure you wish to proceed, sir?")
    ]

    EMERGENCY_STOP_KEYWORDS = {
        "stop", "halt", "cancel", "stand down", "abort", "emergency stop",
        "jarvis stop", "jarvis halt", "jarvis cancel", "jarvis stand down"
    }

    CONFIRMATION_AFFIRMATIVE = {"yes", "yeah", "yep", "proceed", "go ahead", "do it", "confirm", "sure", "affirmative", "yes please"}
    CONFIRMATION_NEGATIVE = {"no", "nope", "cancel", "never mind", "abort", "stop", "don't", "do not"}

    def __init__(self):
        self.pending_confirmation: Optional[Dict[str, Any]] = None

    async def process_turn(self, raw_input: str) -> Dict[str, Any]:
        """
        Processes a user turn with conversational context, compound parsing,
        safety gatekeeping, and instant emergency stop priority.
        """
        start_time = time.time()
        user_text = raw_input.strip()
        lower_text = user_text.lower()
        logger.info(f"🧠 [Conversation Engine] Ingestion: '{user_text}'")

        clean_stop_check = re.sub(r"[^\w\s]", "", lower_text).strip()

        # 1. PENDING CONFIRMATION TICKET RESOLUTION
        if self.pending_confirmation:
            if clean_stop_check in self.CONFIRMATION_AFFIRMATIVE:
                # User confirmed the dangerous action
                pending = self.pending_confirmation
                self.pending_confirmation = None
                logger.info(f"✅ [Safety Guard] Destructive action '{pending['action']}' confirmed by operator.")
                # Execute original deferred instruction
                exec_res = await brain_runtime.execute_turn(pending["query"])
                final_resp = response_generator.polish_text(exec_res.get("response", "Action executed, sir."))
                context_manager.add_turn("user", user_text)
                context_manager.add_turn("jarvis", final_resp, {"confirmed_action": pending["action"]})
                return {
                    "response": final_resp,
                    "intent": pending["action"],
                    "actions_executed": exec_res.get("actions_executed", []),
                    "verified": exec_res.get("verified", True),
                    "latency_ms": (time.time() - start_time) * 1000
                }
            elif clean_stop_check in self.CONFIRMATION_NEGATIVE:
                # User cancelled
                pending = self.pending_confirmation
                self.pending_confirmation = None
                logger.info(f"❌ [Safety Guard] Destructive action '{pending['action']}' cancelled by operator.")
                response = "Cancelled, sir. No changes were made."
                context_manager.add_turn("user", user_text)
                context_manager.add_turn("jarvis", response)
                return {
                    "response": response,
                    "intent": "action_cancelled",
                    "actions_executed": [],
                    "verified": True,
                    "latency_ms": (time.time() - start_time) * 1000
                }

        # 2. EMERGENCY STOP PRIORITY (<1ms)
        if clean_stop_check in self.EMERGENCY_STOP_KEYWORDS:
            logger.warning("🚨 [Conversation Engine] Instant Emergency STOP triggered by voice keyword.")
            tts_engine.interrupt()
            self.pending_confirmation = None
            stop_res = emergency_stop.trigger_emergency_stop(source="voice_command", reason=user_text)
            response = "All systems halted and standing down, sir."
            context_manager.add_turn("user", user_text)
            context_manager.add_turn("jarvis", response, {"intent": "emergency_stop"})
            return {
                "response": response,
                "intent": "emergency_stop",
                "actions_executed": ["EmergencyStopController.trigger_emergency_stop"],
                "verified": True,
                "latency_ms": (time.time() - start_time) * 1000
            }

        # 3. SAFETY CONFIRMATION CHECK FOR TIER 3 DESTRUCTIVE ACTIONS
        for pattern, action_name, confirm_prompt in self.DESTRUCTIVE_PATTERNS:
            if re.search(pattern, lower_text):
                logger.warning(f"🛡 [Safety Gatekeeper] Tier 3 destructive command detected: '{action_name}'. Requiring confirmation.")
                self.pending_confirmation = {
                    "action": action_name,
                    "query": user_text,
                    "created_at": time.time()
                }
                context_manager.add_turn("user", user_text)
                context_manager.add_turn("jarvis", confirm_prompt, {"requires_confirmation": True})
                return {
                    "response": confirm_prompt,
                    "intent": "require_confirmation",
                    "requires_confirmation": True,
                    "actions_executed": [],
                    "verified": True,
                    "latency_ms": (time.time() - start_time) * 1000
                }

        # 3.5. INTELLIGENT WEB APP, MUSIC STREAMING & DESTINATION FAST-PATH
        # Fulfills user requirements:
        # - "play believer in amazon music", "play starboy on spotify", "play believer on youtube", "play believer"
        # - "amazon music on web", "open prime video", "open ibm career website", "open hotstar"
        try:
            from agents.computer.web_app_resolver import web_app_resolver

            # A. Music Streaming Intent
            music_info = web_app_resolver.parse_music_intent(user_text)
            if music_info:
                song, platform, url = music_info
                res = web_app_resolver.open_target(user_text)
                reply = f"Playing {song.title()} on {platform}, sir."
                action_record = {
                    "tool": "browse_web",
                    "arguments": {"url": url, "song": song, "platform": platform, "mode": "music_streaming"},
                    "result": res,
                    "status": "completed"
                }
                context_manager.add_turn("user", user_text)
                context_manager.add_turn("jarvis", reply, {"intent": "music_stream", "song": song, "platform": platform})
                return {
                    "response": reply,
                    "intent": "music_stream",
                    "actions_executed": [action_record],
                    "verified": True,
                    "latency_ms": (time.time() - start_time) * 1000
                }

            # B. Smart Web Destination & Online Services
            is_explicit_web = bool(re.search(r"\b(on\s+web|in\s+browser|website|web\s+page|online)\b", lower_text))
            is_open_prefix = bool(re.search(r"^(?:open|launch|go to|visit)\s+", lower_text))
            
            if is_explicit_web or is_open_prefix:
                dest = web_app_resolver.resolve_destination(user_text)
                is_canonical_or_url = dest.get("success") and dest.get("type") in ["canonical", "url", "domain"]
                is_career_or_site = any(w in lower_text for w in ["website", "site", "careers", "career", ".com", ".org", ".net", ".io"])
                
                if is_canonical_or_url or (is_explicit_web and dest.get("success")) or (is_career_or_site and dest.get("success")):
                    res = web_app_resolver.open_target(user_text)
                    dest_name = dest.get("name", "the requested website")
                    target_url = dest.get("url")
                    reply = f"Opening {dest_name} in your browser, sir."
                    action_record = {
                        "tool": "browse_web",
                        "arguments": {"url": target_url, "name": dest_name, "mode": "web_destination"},
                        "result": res,
                        "status": "completed"
                    }
                    context_manager.add_turn("user", user_text)
                    context_manager.add_turn("jarvis", reply, {"intent": "browse_web", "url": target_url})
                    return {
                        "response": reply,
                        "intent": "browse_web",
                        "actions_executed": [action_record],
                        "verified": True,
                        "latency_ms": (time.time() - start_time) * 1000
                    }
        except Exception as e_web:
            logger.debug(f"[ConversationEngine] Web/music fast-path notice: {e_web}")

        # 4. CONTEXT & REFERENCE RESOLUTION ("and RAM?", "the first result", "do that again")
        resolved_query, hints = context_manager.resolve_references(user_text)
        if resolved_query != user_text:
            logger.info(f"🔗 [Conversation Engine] Query contextualized: '{user_text}' -> '{resolved_query}'")

        # 5. COMPOUND MULTI-STEP COMMAND HANDLING
        steps = self._decompose_compound_command(resolved_query)
        if len(steps) > 1:
            logger.info(f"📋 [Conversation Engine] Decomposed compound command into {len(steps)} steps: {steps}")
            all_actions = []
            responses = []
            for step in steps:
                step_res = await brain_runtime.execute_turn(step)
                all_actions.extend(step_res.get("actions_executed", []))
                resp_text = step_res.get("response", "")
                if resp_text:
                    responses.append(resp_text)
                # Small pause between UI steps if needed
                time.sleep(0.05)

            combined_resp = " and ".join([r.rstrip(".") for r in responses])
            if combined_resp:
                combined_resp = response_generator.polish_text(combined_resp)
            else:
                combined_resp = "Sequence executed successfully, sir."

            context_manager.add_turn("user", user_text)
            context_manager.add_turn("jarvis", combined_resp, {"compound_steps": steps})
            return {
                "response": combined_resp,
                "intent": "compound_command",
                "actions_executed": all_actions,
                "verified": True,
                "latency_ms": (time.time() - start_time) * 1000
            }

        # 6. DIRECT EXECUTION VIA BRAIN RUNTIME
        result = await brain_runtime.execute_turn(resolved_query)

        # Polish response through natural personality generator
        raw_resp = result.get("response", "")
        natural_resp = response_generator.polish_text(raw_resp) if raw_resp else "Instruction processed, sir."

        # Track tool execution and focused app in context
        actions = result.get("actions_executed", [])
        if actions:
            last_action = actions[-1]
            tool_name = last_action.get("tool")
            tool_args = last_action.get("params") or last_action.get("arguments", {})
            focused_app = tool_args.get("app_name") or tool_args.get("target")
            context_manager.record_tool_execution(tool_name, tool_args, focused_app=focused_app)

        context_manager.add_turn(
            role="user",
            content=user_text,
            metadata={"resolved_query": resolved_query, "hints": hints}
        )
        context_manager.add_turn(
            role="jarvis",
            content=natural_resp,
            metadata={"intent": result.get("intent"), "actions": [a.get("tool") for a in actions]}
        )

        return {
            "response": natural_resp,
            "intent": result.get("intent"),
            "actions_executed": actions,
            "verified": result.get("verified", True),
            "latency_ms": (time.time() - start_time) * 1000
        }

    def _decompose_compound_command(self, query: str) -> List[str]:
        """
        Splits compound sequential instructions such as:
        'open Chrome, go to GitHub, and open my repository'
        """
        # Split on ", and ", " and then ", " then ", or ", next "
        parts = re.split(r",?\s*(?:and\s+then|then|next|and)\s+", query, flags=re.IGNORECASE)
        cleaned = [p.strip() for p in parts if p.strip()]
        return cleaned if len(cleaned) > 1 else [query]


conversation_engine = ConversationEngine()
