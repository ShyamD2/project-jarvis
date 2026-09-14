"""
Autonomous Agent Runtime for J.A.R.V.I.S. Brain.
Executes the ReAct loop: Understand -> Plan -> Authorize -> Execute -> Verify -> Respond.
Integrates Emergency Stand-Down, 4-Tier Safety Guard, and Structured Audit Trail.
"""

from typing import Dict, Any, Optional, List
import time

from services.brain.intent_router import router as intent_router, IntentType, RoutedIntent
from services.brain.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from services.brain.providers.mock_provider import MockLLMProvider
from services.brain.providers.ai_manager import ai_manager
from services.memory.feedback_learning import learner
from services.brain.ml_operator_learner import ml_learner
from services.brain.tools.registry import registry as tool_registry
from agents.intelligence.emergency_stop import emergency_stop
from agents.intelligence.safety_guard import safety_guard
from agents.intelligence.audit_logger import audit_logger
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

        # 1. UNDERSTAND & ROUTE INTENT (Adaptive ML Fast-Path first)
        ml_fast = ml_learner.compute_fast_path_match(query)
        if ml_fast and ml_fast[2] >= 0.82:
            fast_tool, fast_args, fast_conf = ml_fast
            routed = RoutedIntent(
                intent_type=IntentType.DIRECT_ACTION,
                confidence=fast_conf,
                recommended_model_tier="tier_1_fast",
                target_tool=fast_tool,
                parameters=fast_args,
                raw_query=query
            )
            logger.info(f"⚡ [Runtime: ML Fast-Path] Matched operator intent '{fast_tool}' in <2ms (Confidence: {fast_conf:.2f})")
        else:
            routed = intent_router.route(query)
            logger.info(f"Intent classified: {routed.intent_type.value} (Confidence: {routed.confidence:.2f})")

        # Circuit Breaker: Instant Emergency Stop (<1ms)
        if routed.intent_type == IntentType.EMERGENCY:
            res = emergency_stop.trigger_emergency_stop(source="vocal_command", reason=query)
            audit_logger.record_entry(
                user_query=query,
                intent="emergency_stop",
                tool="EmergencyStopController.trigger_emergency_stop",
                parameters={"reason": query},
                risk_tier="CRITICAL",
                result="SUCCESS",
                duration_ms=(time.time() - start_time) * 1000,
                details={"status": "HALTED"}
            )
            return {
                "response": "Standing down immediately, sir. All active workflows and automations are halted.",
                "intent": routed.intent_type.value,
                "actions_executed": [{"tool": "emergency_stop", "status": "halted"}],
                "verified": True,
                "latency_ms": (time.time() - start_time) * 1000
            }

        # Confirmation Gate: User approving a pending Tier 2 or Tier 3 ticket
        if routed.intent_type == IntentType.CONFIRMATION:
            pending_ticket = safety_guard.get_latest_pending_ticket()
            if pending_ticket:
                safety_guard.confirm_ticket(pending_ticket.approval_id, approver="operator", method="voice")
                logger.info(f"[Runtime] Confirmed pending ticket {pending_ticket.approval_id} for {pending_ticket.action_name}")

                # Execute confirmed action immediately
                exec_res = await tool_registry.execute_tool(
                    name=pending_ticket.action_name,
                    parameters=pending_ticket.parameters,
                    caller_agent="jarvis_core_agent",
                    approval_id=pending_ticket.approval_id,
                    raw_query=query
                )
                duration_ms = (time.time() - start_time) * 1000
                return {
                    "response": f"Confirmation verified, sir. Proceeding with {pending_ticket.action_name.replace('_', ' ')} immediately.",
                    "intent": "confirmation_verified",
                    "actions_executed": [{"tool": pending_ticket.action_name, "status": "executed", "result": exec_res.get("result")}],
                    "verified": exec_res.get("success", True),
                    "latency_ms": duration_ms
                }
            else:
                return {
                    "response": "Sir, there are no pending operations awaiting confirmation.",
                    "intent": "confirmation_none",
                    "actions_executed": [],
                    "verified": True,
                    "latency_ms": (time.time() - start_time) * 1000
                }

        # Check if Emergency Stop is currently active
        if emergency_stop.is_stopped:
            if "resume" in query.lower() or "continue" in query.lower() or "stand up" in query.lower():
                emergency_stop.resume_operations()
                return {
                    "response": "Emergency stand-down lifted, sir. All systems are operational.",
                    "intent": "operations_resumed",
                    "actions_executed": [],
                    "verified": True,
                    "latency_ms": (time.time() - start_time) * 1000
                }
            else:
                return {
                    "response": "Sir, emergency stand-down is currently active. Say 'Jarvis, resume operations' to re-enable autonomous execution.",
                    "intent": "emergency_active",
                    "actions_executed": [],
                    "verified": True,
                    "latency_ms": (time.time() - start_time) * 1000
                }

        # Fast-Path Direct Tool Execution for well-defined intents with parameters
        if routed.intent_type == IntentType.DIRECT_ACTION and routed.target_tool and routed.parameters:
            logger.info(f"[Runtime] Fast-Path Direct Execution for tool: {routed.target_tool}")
            exec_res = await tool_registry.execute_tool(
                name=routed.target_tool,
                parameters=routed.parameters,
                caller_agent="jarvis_core_agent",
                raw_query=query
            )

            if exec_res.get("status") == "confirmation_required":
                return {
                    "response": exec_res.get("prompt_user", "Confirmation required to proceed, sir."),
                    "intent": "confirmation_required",
                    "ticket_id": exec_res.get("ticket_id"),
                    "tier": exec_res.get("tier"),
                    "actions_executed": [{"tool": routed.target_tool, "status": "confirmation_required", "ticket_id": exec_res.get("ticket_id")}],
                    "verified": True,
                    "latency_ms": (time.time() - start_time) * 1000
                }

            res_data = exec_res.get("result", {})
            return {
                "response": self._synthesize_tool_response(routed.target_tool, routed.parameters, res_data),
                "intent": routed.intent_type.value,
                "actions_executed": [{"tool": routed.target_tool, "arguments": routed.parameters, "result": res_data, "status": "completed"}],
                "verified": exec_res.get("success", True),
                "latency_ms": (time.time() - start_time) * 1000
            }

        # Select Provider Tier
        active_provider = self.deep_provider if routed.recommended_model_tier == "tier_2_deep" else self.fast_provider

        # 2. PLAN & SELECT TOOLS
        tool_specs = tool_registry.to_llm_tool_specs()

        recent_context = ""
        try:
            from services.memory.short_term import short_term_memory
            history_text = short_term_memory.format_for_prompt(limit=4)
            if history_text:
                recent_context = f"\nRecent Dialogue Context:\n{history_text}\n"
        except Exception as e:
            logger.debug(f"[AgentRuntime] Memory context lookup: {e}")

        intent_hint = ""
        if routed.target_tool:
            intent_hint = (
                f"\nDetected Intent Tool: '{routed.target_tool}'. "
                f"You MUST invoke tool '{routed.target_tool}' with appropriate parameters to fulfill this instruction."
            )

        system_prompt = (
            "You are J.A.R.V.I.S., Tony Stark's brilliant, highly efficient cyber-physical AI assistant. "
            "Address the user as 'sir'. Execute required tools with precision and return concise, elegant responses. "
            "You have access to real tools across 3 pillars: Computer (pc_power, audio_media, display_control, mouse_keyboard, file_manager, network_control, launch_app, close_app), "
            "Cloud (devops_tool, aws_management), and Intelligence (productivity_tool, compound_workflow, analyze_screen). "
            "Understand English, Tamil (Tanglish), and Hindi (Hinglish): "
            "- 'kammi pannu' / 'kam karo' = decrease/lower "
            "- 'ethu' / 'badhao' = increase/raise "
            "- 'moodu' / 'bandh karo' = close application "
            "- 'thoda' / 'konjam' = a little bit. "
            f"{intent_hint}"
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
                exec_res = await tool_registry.execute_tool(
                    name=tc.tool_name,
                    parameters=tc.arguments,
                    caller_agent="jarvis_core_agent",
                    raw_query=query
                )

                if exec_res.get("status") == "confirmation_required":
                    return {
                        "response": exec_res.get("prompt_user", "Sir, this action requires your explicit confirmation to proceed."),
                        "intent": "confirmation_required",
                        "ticket_id": exec_res.get("ticket_id"),
                        "tier": exec_res.get("tier"),
                        "actions_executed": [{
                            "tool": tc.tool_name,
                            "status": "confirmation_required",
                            "tier": exec_res.get("tier"),
                            "ticket_id": exec_res.get("ticket_id")
                        }],
                        "verified": True,
                        "latency_ms": (time.time() - start_time) * 1000
                    }

                tool_output = exec_res.get("result", {})
                logical_ok = bool(exec_res.get("success", False))

                executed_actions.append({
                    "tool": tc.tool_name,
                    "arguments": tc.arguments,
                    "result": tool_output,
                    "status": exec_res.get("status", "completed"),
                    "duration_ms": exec_res.get("duration_ms", 0.0),
                    "verified": logical_ok
                })

                # Broadcast action event to Mesh for UI animation
                action_event = JarvisEvent(
                    source="brain.runtime",
                    type=f"action.{tc.tool_name}",
                    data={"tool": tc.tool_name, "result": tool_output}
                )
                try:
                    mesh.publish(action_event)
                except Exception:
                    pass

            if routed.intent_type in [IntentType.DIRECT_ACTION, IntentType.CONVERSATION]:
                break

        total_latency = (time.time() - start_time) * 1000

        # 4. RESPOND: Formulate verified response
        final_response = llm_response.content
        if not final_response or not final_response.strip():
            if executed_actions:
                summaries = [self._synthesize_tool_response(a["tool"], a.get("arguments", {}), a.get("result", {})) for a in executed_actions]
                final_response = f"Right away, sir. {', and '.join(summaries)}."
            else:
                final_response = "At your service, sir. Instructions received."

        # Continuous ML Learning: Record operator command and performance
        first_tool = executed_actions[0]["tool"] if executed_actions else None
        first_args = executed_actions[0].get("arguments") if executed_actions else None
        ml_learner.record_successful_turn(query, first_tool, first_args, total_latency)

        return {
            "response": final_response,
            "intent": routed.intent_type.value,
            "model": llm_response.model,
            "actions_executed": executed_actions,
            "iterations": iteration,
            "verified": all(a.get("verified", True) for a in executed_actions),
            "latency_ms": round(total_latency, 2)
        }

    def _synthesize_tool_response(self, tool_name: str, args: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Helper to create concise, elegant natural language summaries for tool outputs"""
        if tool_name in ["control_system_audio", "audio_media"]:
            act = args.get("action", "volume")
            return f"Audio volume adjusted ({act})"
        elif tool_name == "pc_power":
            act = args.get("action", "power")
            return f"Power command executed ({act})"
        elif tool_name == "launch_app":
            app = args.get("app", "Application")
            return f"{app.capitalize()} has been launched"
        elif tool_name == "close_app":
            app = args.get("app_name", "target")
            return f"{app.capitalize()} has been closed"
        elif tool_name == "manage_browser":
            return "Browser navigation action executed"
        elif tool_name == "send_message":
            return "WhatsApp message prepared and dispatched"
        elif tool_name == "mouse_keyboard":
            return f"Input automation executed ({args.get('action')})"
        elif tool_name == "network_control":
            return f"Network telemetry retrieved (IP: {result.get('local_ip', 'active')})"
        elif tool_name == "devops_tool":
            return f"DevOps {args.get('subsystem')} operation executed"
        elif tool_name == "aws_management":
            return f"AWS Cloud {args.get('action')} operation completed"
        elif tool_name == "productivity_tool":
            return f"Productivity action completed ({args.get('action')})"
        elif tool_name == "compound_workflow":
            return result.get("message", f"Workflow {args.get('workflow')} executed")
        elif tool_name == "analyze_screen":
            return f"Here is what I observe on your screen: {result.get('analysis', 'Screen analyzed')}"
        return f"Action '{tool_name}' executed successfully"


runtime = AgentRuntime()
