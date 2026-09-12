"""
Autonomous Agent Runtime for J.A.R.V.I.S. Brain.
Executes the ReAct loop: Understand -> Plan -> Authorize -> Execute -> Verify -> Respond.
"""

from typing import Dict, Any, Optional, List
import time

from services.brain.intent_router import router as intent_router, IntentType
from services.brain.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from services.brain.providers.mock_provider import MockLLMProvider
from services.brain.providers.ai_manager import ai_manager
from services.memory.feedback_learning import learner
from services.brain.tools.registry import registry as tool_registry
from shared.schemas.action_envelope import ActionTier, TargetWorld, ActionEnvelope
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.config import config
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.schemas.event_envelope import JarvisEvent

logger = get_logger("JarvisAgentRuntime")


class AgentRuntime:
    def __init__(
        self,
        fast_provider: Optional[BaseLLMProvider] = None,
        deep_provider: Optional[BaseLLMProvider] = None,
        max_loop_iterations: int = 5
    ):
        self.fast_provider = fast_provider or ai_manager
        self.deep_provider = deep_provider or ai_manager
        self.max_loop_iterations = max_loop_iterations

    async def execute_turn(self, query: str) -> Dict[str, Any]:
        """
        Main entry point for processing any user instruction or sensory event.
        Follows the strict master architecture:
        UNDERSTAND -> PLAN -> AUTHORIZE -> EXECUTE -> VERIFY -> RESPOND
        """
        start_time = time.time()
        logger.info(f"Processing input query: '{query}'")

        # 0. CONTINUOUS LEARNING & PREFERENCE INGESTION
        learning_result = learner.inspect_and_learn(query)
        if learning_result:
            if learning_result.get("type") == "correction_learned" and learning_result.get("desired_action"):
                logger.info(f"🧠 [Runtime] Auto-executing corrected instruction: '{learning_result['desired_action']}'")
                query = learning_result["desired_action"]
            else:
                return {
                    "response": learning_result["acknowledgement"],
                    "intent": "learning_update",
                    "actions_executed": [],
                    "verified": True,
                    "latency_ms": (time.time() - start_time) * 1000
                }

        # Apply learned adaptations and preferences
        adapted_query = learner.apply_learned_adaptations(query)
        if adapted_query != query:
            logger.info(f"🧠 [Runtime] Adapted instruction based on memory: '{adapted_query}'")
            query = adapted_query

        # 1. UNDERSTAND & ROUTE INTENT
        routed = intent_router.route(query)
        logger.info(f"Intent classified: {routed.intent_type.value} (Confidence: {routed.confidence:.2f})")

        # Circuit Breaker check
        if routed.intent_type == IntentType.EMERGENCY:
            config.emergency_stand_down = True
            event = JarvisEvent(
                source="brain.agent_runtime",
                type="system.emergency_stand_down",
                data={"query": query, "status": "FROZEN"}
            )
            mesh.publish(event)
            return {
                "response": "Standing down immediately, sir. All active workflows are frozen.",
                "intent": routed.intent_type.value,
                "actions_executed": [],
                "verified": True,
                "latency_ms": (time.time() - start_time) * 1000
            }

        # Select Provider Tier
        active_provider = self.deep_provider if routed.recommended_model_tier == "tier_2_deep" else self.fast_provider

        # 2. PLAN & SELECT TOOLS
        # 2. PLAN & SELECT TOOLS
        tool_specs = tool_registry.to_llm_tool_specs()

        # Inject recent dialogue history from short-term memory if available
        recent_context = ""
        try:
            from services.memory.short_term import short_term_memory
            history_text = short_term_memory.format_for_prompt(limit=4)
            if history_text:
                recent_context = f"\nRecent Dialogue Context:\n{history_text}\n"
        except Exception as e:
            logger.debug(f"[AgentRuntime] Memory context lookup: {e}")

        system_prompt = (
            "You are J.A.R.V.I.S., Tony Stark's brilliant, highly efficient cyber-physical AI assistant. "
            "Address the user as 'sir'. Execute required tools with precision and return concise, elegant responses."
            f"{recent_context}"
        )

        llm_response: LLMResponse = await active_provider.generate(
            prompt=query,
            system_prompt=system_prompt,
            tools=tool_specs
        )

        executed_actions: List[Dict[str, Any]] = []
        iteration = 0

        # 3. AUTHORIZE, EXECUTE & VERIFY LOOP (ReAct)
        while llm_response.tool_calls and iteration < self.max_loop_iterations:
            iteration += 1
            for tc in llm_response.tool_calls:
                # Execute through strict Agent -> Tool Registry -> Policy Engine -> Tool -> Result chain
                exec_res = await tool_registry.execute_tool(
                    name=tc.tool_name,
                    parameters=tc.arguments,
                    caller_agent="jarvis_core_agent"
                )

                if exec_res.get("status") == "permission_blocked":
                    executed_actions.append({
                        "tool": tc.tool_name,
                        "status": "permission_blocked",
                        "risk_level": exec_res.get("risk_level"),
                        "rationale": exec_res.get("rationale"),
                        "requires_approval": exec_res.get("requires_approval", False),
                        "approval_id": exec_res.get("approval_id"),
                        "verified": False
                    })
                    continue

                tool_output = exec_res.get("result", {})

                # VERIFY: Strict fail-closed dual-channel validation check
                logical_ok = bool(
                    exec_res.get("success", False)
                    and tool_output.get("channel_1_logical", tool_output.get("success", False))
                )

                # Physical IoT actions require genuine environmental/device verification
                is_physical = any(k in tc.tool_name.lower() for k in ("relay", "light", "esp32", "device"))
                if is_physical:
                    sensory_ok = bool(
                        tool_output.get("channel_2_lux") is not None
                        or tool_output.get("channel_2_sensory") is not None
                        or tool_output.get("sensory_verified", False)
                    )
                else:
                    sensory_ok = True

                action_verified = bool(logical_ok and sensory_ok)

                executed_actions.append({
                    "tool": tc.tool_name,
                    "arguments": tc.arguments,
                    "result": tool_output,
                    "status": exec_res.get("status", "completed"),
                    "duration_ms": exec_res.get("duration_ms", 0.0),
                    "verified": action_verified
                })

                # Broadcast action execution to Mesh for UI animation
                action_event = JarvisEvent(
                    source="brain.runtime",
                    type=f"action.{tc.tool_name}",
                    data={"tool": tc.tool_name, "result": tool_output}
                )
                mesh.publish(action_event)

            # In single-turn fast-path, break after first round
            if routed.intent_type in [IntentType.DIRECT_ACTION, IntentType.CONVERSATION]:
                break

        total_latency = (time.time() - start_time) * 1000

        # 4. RESPOND: Formulate verified response
        final_response = llm_response.content
        if not final_response or not final_response.strip():
            if executed_actions:
                summaries = []
                for act in executed_actions:
                    t_name = act.get("tool", "")
                    res = act.get("result", {})
                    if t_name in ["launch_app", "open_app"]:
                        app_name = act.get("arguments", {}).get("app") or act.get("arguments", {}).get("app_name") or "application"
                        pid = res.get("pid")
                        if pid:
                            summaries.append(f"{app_name.capitalize()} has been launched (PID: {pid})")
                        else:
                            summaries.append(f"{app_name.capitalize()} has been launched")
                    elif "light" in t_name or "relay" in t_name or "device" in t_name:
                        summaries.append("Physical IoT device state updated")
                    elif t_name == "prepare_workspace":
                        summaries.append("Your developer workspace is prepared")
                    elif act.get("status") == "permission_blocked":
                        summaries.append(f"Action '{t_name}' was intercepted by policy engine (approval required)")
                    else:
                        summaries.append(f"Action '{t_name}' executed successfully")
                final_response = f"Right away, sir. {', and '.join(summaries)}."
            else:
                final_response = "At your service, sir. Instructions received."

        return {
            "response": final_response,
            "intent": routed.intent_type.value,
            "model": llm_response.model,
            "actions_executed": executed_actions,
            "iterations": iteration,
            "verified": all(a.get("verified", True) for a in executed_actions),
            "latency_ms": round(total_latency, 2)
        }


runtime = AgentRuntime()
