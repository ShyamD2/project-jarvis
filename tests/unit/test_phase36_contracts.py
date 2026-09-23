"""
Unit Test Suite for Phase 36 Contracts and Envelopes (Stage 36.1).
Validates UniversalTransactionRecord, ActionEnvelope, ExecutionClass,
JarvisEvent CloudEvents v1.0, VerificationResult terminal states,
and JarvisTool ExecutionResult contracts.
"""

import unittest
import time
import uuid

from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld, ExecutionClass, UniversalTransactionRecord
from shared.schemas.event_envelope import JarvisEvent
from shared.schemas.verification_contract import VerificationResult, VerificationStatus
from services.brain.tools.base import JarvisTool, ToolDefinition, ExecutionResult


class DummyTestTool(JarvisTool):
    async def execute(self, target: str = "test", **kwargs) -> ExecutionResult:
        return ExecutionResult(
            tool_name=self.name,
            target=target,
            raw_result={"status": "ok", "target": target}
        )

    async def verify(self, execution_result: ExecutionResult, **kwargs) -> VerificationResult:
        return VerificationResult(
            action_id=execution_result.execution_id,
            status=VerificationStatus.VERIFIED,
            match=True,
            confidence=0.99,
            observed_state={"target": execution_result.target, "active": True},
            expected_state={"target": execution_result.target, "active": True}
        )


class TestPhase36Contracts(unittest.IsolatedAsyncioTestCase):
    def test_action_envelope_execution_classes(self):
        # 1. Reflex Action
        reflex_action = ActionEnvelope(
            name="computer.volume",
            target_world=TargetWorld.COMPUTER,
            target_agent="audio_agent",
            tier=ActionTier.TIER_0_REFLEX,
            parameters={"level": 50}
        )
        self.assertEqual(reflex_action.execution_class, ExecutionClass.REFLEX)
        self.assertEqual(reflex_action.version, "2.0")
        self.assertEqual(reflex_action.schema_version, 2)

        # 2. Mission Action
        mission_action = ActionEnvelope(
            name="terraform.apply",
            target_world=TargetWorld.DIGITAL,
            target_agent="aws_agent",
            tier=ActionTier.TIER_3_DESTRUCTIVE,
            parameters={"plan": "main.tfplan"}
        )
        self.assertEqual(mission_action.execution_class, ExecutionClass.MISSION)
        self.assertTrue(mission_action.requires_approval)

        # Serialization round-trip
        data = mission_action.to_dict()
        self.assertEqual(data["execution_class"], "mission")
        deserialized = ActionEnvelope.from_dict(data)
        self.assertEqual(deserialized.name, mission_action.name)
        self.assertEqual(deserialized.execution_class, ExecutionClass.MISSION)

    def test_universal_transaction_record(self):
        tx = UniversalTransactionRecord(
            mission_id="m_1024",
            task_id="t_001",
            action_id="a_042",
            trace_id="tr_999",
            user_id="operator",
            source="telegram",
            tool="computer.open_app",
            arguments_hash="sha256_mock_hash",
            risk_tier="TIER_1_SOFT",
            final_status="SUCCESS"
        )
        d = tx.to_dict()
        self.assertEqual(d["mission_id"], "m_1024")
        self.assertEqual(d["final_status"], "SUCCESS")
        self.assertIn("timestamp", d)

    def test_jarvis_event_cloudevents_v1(self):
        evt = JarvisEvent(
            source="sensory.microphone",
            type="sensory.voice_transcript",
            data={"transcript": "hello jarvis"},
            correlation_id="corr_123",
            causation_id="caus_456",
            idempotency_key="idemp_789",
            mission_id="m_001"
        )
        # Check canonical aliases (Item 23)
        self.assertEqual(evt.event_id, evt.id)
        self.assertEqual(evt.event_type, "sensory.voice_transcript")
        self.assertEqual(evt.payload["transcript"], "hello jarvis")
        self.assertEqual(evt.correlation_id, "corr_123")
        self.assertEqual(evt.schema_version, 2)

        # Roundtrip
        j_str = evt.to_json()
        restored = JarvisEvent.from_json(j_str)
        self.assertEqual(restored.correlation_id, "corr_123")
        self.assertEqual(restored.event_type, "sensory.voice_transcript")

    def test_verification_contract_terminal_states(self):
        # 1. Verified
        v_ok = VerificationResult(
            action_id="act_1",
            status=VerificationStatus.VERIFIED,
            observed_state={"running": True},
            expected_state={"running": True}
        )
        self.assertTrue(v_ok.match)
        self.assertEqual(v_ok.status, VerificationStatus.VERIFIED)

        # 2. Failed
        v_fail = VerificationResult(
            action_id="act_2",
            status=VerificationStatus.FAILED,
            observed_state={"running": False},
            expected_state={"running": True},
            failure_reason="Process did not spawn"
        )
        self.assertFalse(v_fail.match)
        self.assertEqual(v_fail.status, VerificationStatus.FAILED)

        # 3. Unknown (Terminal truth model)
        v_unknown = VerificationResult(
            action_id="act_3",
            status=VerificationStatus.UNKNOWN,
            failure_reason="Asynchronous task accepted but post-condition unobservable"
        )
        self.assertEqual(v_unknown.status, VerificationStatus.UNKNOWN)

    async def test_jarvis_tool_contract(self):
        tool = DummyTestTool(
            ToolDefinition(
                name="dummy.test",
                description="Test tool for Phase 36 contracts",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_0_REFLEX
            )
        )
        self.assertEqual(tool.tool_api_version, "2.0")
        self.assertEqual(tool.schema_version, 2)

        # Execute
        exec_res = await tool.execute(target="test_service")
        self.assertIsInstance(exec_res, ExecutionResult)
        self.assertEqual(exec_res.tool_name, "dummy.test")
        self.assertEqual(exec_res.transport_status, "COMPLETED")

        # Verify
        verif_res = await tool.verify(exec_res)
        self.assertIsInstance(verif_res, VerificationResult)
        self.assertEqual(verif_res.status, VerificationStatus.VERIFIED)
        self.assertTrue(verif_res.match)


if __name__ == "__main__":
    unittest.main()
