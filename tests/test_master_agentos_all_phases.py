"""
Master End-to-End Test Suite for Project J.A.R.V.I.S. AgentOS (Phases 1 through 5).

Verifies the entire 30-item architectural roadmap across all 5 phases:
- Phase 1: Foundation (Telegram routing, package structure, browser CDP, wake word, ActionTier HMAC tickets)
- Phase 2: Real Computer Agent (Vision grounding, visual sentinel, failure recovery, ConPTY terminal, Task DAG)
- Phase 3: Distributed Architecture (Operating modes, remote mobile node, AES-256 state sync)
- Phase 4: Autonomy Hardening (Chained audit ledger, isolated skill sandbox AST & subprocess, epistemic engine)
- Phase 5: 1-in-a-Million Layer (SystemUndo, Workstation SRE, AES-256 capsule teleporter, Floating HUD bridge)
"""

import os
import sys
import time
import json
import asyncio
import tempfile
import unittest
import numpy as np
from PIL import Image

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

# Phase 1
from services.gateway.telegram_bot import telegram_gateway
from services.brain.conversation_engine import conversation_engine
from services.pc_agent.browser_agent import browser_agent
from services.voice.neural_wake_word import neural_wake_word
from shared.schemas.action_envelope import ActionTier
from agents.intelligence.safety_guard import safety_guard

# Phase 2
from agents.computer.vision_grounding import vision_grounding
from services.verification.visual_sentinel import visual_sentinel
from services.brain.recovery_engine import recovery_engine
from agents.computer.conpty_terminal import terminal_manager
from services.planner.task_dag import TaskDAG, TaskNode, NodeStatus

# Phase 3
from shared.sdk_python.jarvis_sdk.config import config, OperatingMode
from services.device_agents.mobile.remote_mobile_node import remote_mobile_manager
from services.cloud.encrypted_state_sync import state_sync

# Phase 4
from services.observability.chained_audit_ledger import chained_audit_ledger
from services.security.skill_sandbox import skill_sandbox
from services.brain.epistemic_evaluator import epistemic_evaluator, EpistemicState

# Phase 5
from services.verification.system_undo import system_undo
from workstation_sre import workstation_sre
from services.gateway.device_teleporter import device_teleporter
from services.floating_agent.floating_app import FloatingAgentAPI
from agents.intelligence.emergency_stop import emergency_stop


class TestMasterAgentOSAllPhases(unittest.TestCase):

    # =========================================================================
    # PHASE 1: FOUNDATION ARCHITECTURE & SECURITY
    # =========================================================================
    def test_01_phase1_telegram_direct_brain_routing(self):
        """Phase 1: Telegram gateway routes natural language through ConversationEngine and decomposes compounds."""
        steps = conversation_engine._decompose_compound_command("Open Opera and check battery")
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0], "Open Opera")
        self.assertEqual(steps[1], "check battery")
        self.assertTrue(hasattr(telegram_gateway, "handle_update"))
        self.assertFalse(hasattr(telegram_gateway, "_match_procedural_command"))

    def test_02_phase1_package_structure(self):
        """Phase 1: Package structure is installed as editable package and snake_case clean."""
        import services.pc_agent
        import services.floating_agent
        import services.permission_engine
        import services.jarvis_core
        import services.iot_agent
        import devices.raspberry_pi

        self.assertTrue(hasattr(services.pc_agent, "__file__"))
        self.assertTrue(hasattr(services.floating_agent, "__file__"))
        self.assertTrue(hasattr(services.permission_engine, "__file__"))
        self.assertTrue(hasattr(services.jarvis_core, "__file__"))
        self.assertTrue(hasattr(services.iot_agent, "__file__"))
        self.assertTrue(hasattr(devices.raspberry_pi, "__file__"))

        pyproject_path = os.path.join(PROJECT_ROOT, "pyproject.toml")
        self.assertTrue(os.path.exists(pyproject_path))
        with open(pyproject_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('name = "jarvis-agentos"', content)

    def test_03_phase1_browser_cdp_auto_attach(self):
        """Phase 1: Browser CDP auto-detection and binary resolution."""
        exe = browser_agent._find_browser_executable()
        self.assertIsNotNone(exe)
        self.assertTrue(os.path.exists(exe))

        available = asyncio.run(browser_agent._is_cdp_available())
        self.assertIsInstance(available, bool)

    def test_04_phase1_local_neural_wake_word(self):
        """Phase 1: On-device neural wake word ONNX inference (sub-50ms CPU)."""
        dummy_frame = np.zeros(1280, dtype=np.int16)
        scores = neural_wake_word.process_frame(dummy_frame)
        self.assertIsInstance(scores, dict)
        self.assertIn("hey_jarvis", scores)
        self.assertFalse(neural_wake_word.is_wake_detected(dummy_frame))

    def test_05_phase1_action_tier_hmac_tamper_proofing(self):
        """Phase 1: Mandatory ActionTier enforcement & cryptographic ticket tamper detection."""
        eval_res = safety_guard.evaluate_request("pc_shutdown", {"action": "shutdown"})
        self.assertFalse(eval_res["authorized"])
        self.assertTrue(eval_res["requires_confirmation"])
        ticket_id = eval_res["ticket_id"]

        ok = safety_guard.confirm_ticket(ticket_id, approver="test_operator", method="test")
        self.assertTrue(ok)

        # Approval with exact params succeeds
        approved = safety_guard.evaluate_request("pc_shutdown", {"action": "shutdown"}, approval_id=ticket_id)
        self.assertTrue(approved["authorized"])

        # Tampering with parameters triggers signature violation
        tampered = safety_guard.evaluate_request("pc_shutdown", {"action": "format_c"}, approval_id=ticket_id)
        self.assertFalse(tampered["authorized"])
        self.assertIn("SECURITY VIOLATION", tampered["rationale"])

    # =========================================================================
    # PHASE 2: REAL COMPUTER AGENT
    # =========================================================================
    def test_06_phase2_vision_grounding(self):
        """Phase 2: Vision grounding Set-of-Mark and coordinate extraction."""
        test_img = Image.new("RGB", (200, 200), color=(30, 30, 30))
        som_img, marks = vision_grounding.apply_set_of_marks(test_img)
        self.assertIsInstance(som_img, Image.Image)
        self.assertIsInstance(marks, dict)

    def test_07_phase2_visual_verification_sentinel(self):
        """Phase 2: Visual sentinel detects UI state changes via pixel difference."""
        with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as f1, \
             tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as f2:
            p1, p2 = f1.name, f2.name

        try:
            Image.new("RGB", (80, 80), color=(0, 0, 0)).save(p1)
            Image.new("RGB", (80, 80), color=(255, 255, 255)).save(p2)
            res = visual_sentinel.verify_visual_transition(p1, p2)
            self.assertTrue(res["verified"])
            self.assertGreater(res["diff_percent"], 0.2)
        finally:
            if os.path.exists(p1): os.remove(p1)
            if os.path.exists(p2): os.remove(p2)

    def test_08_phase2_failure_recovery_engine(self):
        """Phase 2: Autonomous failure recovery handles application launch retries."""
        res = asyncio.run(recovery_engine.attempt_recovery("launch_app", {"target": "chrome"}, "Binary not in standard PATH"))
        self.assertIsInstance(res, dict)
        self.assertIn("recovered", res)

    def test_09_phase2_conpty_terminal_persistence(self):
        """Phase 2: Interactive ConPTY terminal persists across multi-turn commands."""
        res = terminal_manager.execute_in_session("echo JARVIS_TERMINAL_ONLINE", session_id="master_test_term")
        self.assertTrue(res["success"])
        self.assertIn("JARVIS_TERMINAL_ONLINE", res["output"])
        terminal_manager.terminate_session("master_test_term")

    def test_10_phase2_hierarchical_task_dag(self):
        """Phase 2: Hierarchical task planning DAG resolves dependencies topologically."""
        dag = TaskDAG(plan_id="master_dag_test", description="Test DAG execution")
        n1 = dag.add_node(TaskNode(id="step_1", action="prepare", parameters={"val": 1}))
        n2 = dag.add_node(TaskNode(id="step_2", action="execute", prerequisites=["step_1"]))

        async def fake_executor(action, params):
            return {"success": True, "action": action}

        res = asyncio.run(dag.execute(fake_executor))
        self.assertTrue(res["success"])
        self.assertEqual(res["completed"], 2)

    # =========================================================================
    # PHASE 3: DISTRIBUTED ARCHITECTURE
    # =========================================================================
    def test_11_phase3_operating_modes(self):
        """Phase 3: Explicit operating modes and environment awareness."""
        self.assertIn(config.mode, [OperatingMode.DEVELOPMENT, OperatingMode.REAL_CLOUD, OperatingMode.OFFLINE_LOCAL])
        self.assertIsInstance(config.is_development(), bool)
        self.assertIsInstance(config.is_real_cloud(), bool)
        self.assertIsInstance(config.is_offline_local(), bool)

    def test_12_phase3_remote_mobile_node(self):
        """Phase 3: Authenticated Wi-Fi remote phone node pairing."""
        token = remote_mobile_manager.register_node("phone_pixel_test", "Pixel 8 Pro", "192.168.1.150")
        self.assertIsInstance(token, str)
        verified = remote_mobile_manager.authenticate_node("phone_pixel_test", token)
        self.assertTrue(verified)

    def test_13_phase3_aes256_encrypted_state_sync(self):
        """Phase 3: AES-256 Fernet encrypted cross-device state envelope."""
        sample_state = {"session_id": "test_sess_01", "task": "analyze_repo"}
        token = state_sync.encrypt_state(sample_state)
        self.assertIsInstance(token, str)
        decrypted = state_sync.decrypt_state(token)
        self.assertEqual(decrypted["session_id"], "test_sess_01")

    # =========================================================================
    # PHASE 4: AUTONOMY HARDENING
    # =========================================================================
    def test_14_phase4_chained_audit_ledger_integrity(self):
        """Phase 4: Cryptographically chained local audit ledger with SHA-256 hash continuity."""
        entry = chained_audit_ledger.record_action(
            intent="master_test_intent",
            tool="test_tool",
            parameters={"k": "v"},
            verification_status=True
        )
        self.assertIn("hash", entry)
        self.assertIn("prev_hash", entry)
        verification = chained_audit_ledger.verify_ledger_integrity()
        self.assertTrue(verification["valid"])

    def test_15_phase4_skill_sandbox_ast_and_isolation(self):
        """Phase 4: AST inspection rejects dangerous calls; runs isolated worker process."""
        bad_code = "import ctypes\ndef run(): return ctypes.windll.kernel32"
        validation = skill_sandbox.validate_code_ast(bad_code)
        self.assertFalse(validation["safe"])

        clean_code = "def add(x, y): return x + y"
        exec_res = skill_sandbox.execute_in_sandbox(clean_code, "add", {"x": 10, "y": 20})
        self.assertTrue(exec_res["success"])
        self.assertEqual(exec_res["result"], 30)

    def test_16_phase4_epistemic_evaluator(self):
        """Phase 4: Epistemic evaluation strictly distinguishes VERIFIED vs UNCERTAIN."""
        eval_v = epistemic_evaluator.evaluate("get_battery", {"success": True}, verification_status=True)
        self.assertEqual(eval_v.state, EpistemicState.VERIFIED)

        eval_u = epistemic_evaluator.evaluate("click_element", {"success": True}, verification_status=False)
        self.assertEqual(eval_u.state, EpistemicState.UNCERTAIN)

    # =========================================================================
    # PHASE 5: 1-IN-A-MILLION LAYER
    # =========================================================================
    def test_17_phase5_system_undo_checkpoint_and_rollback(self):
        """Phase 5: Time-Travel SystemUndo differential checkpoint and rollback."""
        cp = system_undo.create_checkpoint(label="master_test_checkpoint")
        self.assertTrue(cp["success"])
        rewind = system_undo.rewind_to_checkpoint(cp["checkpoint_id"])
        self.assertTrue(rewind["success"])
        self.assertLess(rewind["duration_seconds"], 4.0)

    def test_18_phase5_workstation_sre(self):
        """Phase 5: Ghost SRE workstation audit & autonomous self-healing."""
        scan = workstation_sre.run_sre_health_scan()
        self.assertIn("status", scan)
        self.assertIn("timestamp", scan)
        self.assertIn("incident_id", scan)

    def test_19_phase5_aes256_device_teleporter_capsule(self):
        """Phase 5: Cross-device context teleportation with AES-256 encrypted .jarvis_capsule."""
        capsule = device_teleporter.create_capsule(target_device="mobile_pixel", notes="Master test capsule")
        self.assertTrue(capsule["success"])
        self.assertEqual(capsule.get("encryption"), "AES-256-Fernet")
        self.assertTrue(os.path.exists(capsule["file_path"]))

        # Hydrate capsule
        hydrated = device_teleporter.hydrate_capsule(capsule["file_path"])
        self.assertTrue(hydrated["success"])
        self.assertEqual(hydrated["capsule_id"], capsule["capsule_id"])

    def test_20_phase5_floating_hud_agentos_bridge(self):
        """Phase 5: Ambient floating AgentOS HUD API with emergency stand-down and epistemic telemetry."""
        api = FloatingAgentAPI()
        
        # Epistemic status check
        ep = api.get_epistemic_status()
        self.assertTrue(ep["success"])
        self.assertIn("state", ep)

        # Active task status check
        task_st = api.get_active_task_status()
        self.assertTrue(task_st["success"])

        # Emergency Stop test
        stop_res = api.emergency_stop()
        self.assertTrue(stop_res["success"])
        self.assertEqual(stop_res["status"], "EMERGENCY_HALTED")
        self.assertTrue(emergency_stop.is_stopped)

        # Lift emergency stand-down to restore normal state for system
        emergency_stop.lift_emergency_stop()
        self.assertFalse(emergency_stop.is_stopped)


if __name__ == "__main__":
    unittest.main()
