"""
Unit and Integration Tests for Cryptographic Proof-of-Execution Receipts.
Validates receipt generation, HMAC-SHA256 tamper detection, action dispatcher emission,
SQLite/JSONL ledger persistence, and FastAPI verification routes.
"""

import os
import sys
import json
import uuid
import time
import shutil
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from shared.schemas.action_envelope import ActionEnvelope, TargetWorld, ActionTier
from services.verification.proof_of_execution import (
    ProofOfExecutionEngine,
    ExecutionReceipt,
    proof_engine,
)
from agents.action_dispatcher import action_dispatcher
from fastapi.testclient import TestClient
from services.jarvis_core.main import app


class TestProofOfExecution:
    """Test suite for Cryptographic Proof of Execution receipts."""

    def test_proof_of_execution_generation(self):
        """Verifies receipt structure, timestamps, duration, and cryptographic hashes."""
        action_id = f"act_gen_{uuid.uuid4().hex[:8]}"
        request_name = "test_launch_app"
        planned_action = "computer:test_launch_app"
        risk_tier = "TIER_1_SOFT"

        authorization = {
            "lease_id": "lease_alpha_001",
            "nonce": "nonce_123456",
            "authorized_by": "OPERATOR",
            "parameter_hash": "param_hash_abc",
        }
        execution = {
            "started_at": "2026-10-07T12:00:00.000Z",
            "finished_at": "2026-10-07T12:00:00.045Z",
            "duration_ms": 45.2,
            "exit_code": 0,
        }
        before_state = {"app": "notepad", "running": False, "memory_mb": 120}
        after_state = {"app": "notepad", "running": True, "memory_mb": 150}
        state_delta = {
            "running": {"before": False, "after": True},
            "memory_mb": {"before": 120, "after": 150},
        }
        verification = {
            "logical": True,
            "sensory": True,
            "state_match": True,
            "contract_mode": "process_state",
        }
        rollback = {"available": True, "executed": False}
        final_status = "VERIFIED"

        receipt = proof_engine.generate_receipt(
            action_id=action_id,
            request=request_name,
            planned_action=planned_action,
            risk_tier=risk_tier,
            authorization=authorization,
            execution=execution,
            before_state=before_state,
            after_state=after_state,
            state_delta=state_delta,
            verification=verification,
            rollback=rollback,
            final_status=final_status,
            store=True,
        )

        # 1. Structure Verification
        assert isinstance(receipt, ExecutionReceipt)
        assert receipt.action_id == action_id
        assert receipt.request == request_name
        assert receipt.planned_action == planned_action
        assert receipt.risk_tier == risk_tier

        # 2. Authorization & Execution Verification
        assert receipt.authorization["lease_id"] == "lease_alpha_001"
        assert receipt.authorization["authorized_by"] == "OPERATOR"
        assert receipt.execution["duration_ms"] == 45.2
        assert receipt.execution["exit_code"] == 0
        assert receipt.execution["started_at"] == "2026-10-07T12:00:00.000Z"
        assert receipt.execution["finished_at"] == "2026-10-07T12:00:00.045Z"

        # 3. State & Delta Verification
        assert receipt.before_state["running"] is False
        assert receipt.after_state["running"] is True
        assert receipt.state_delta["running"]["after"] is True

        # 4. Verification & Rollback
        assert receipt.verification["logical"] is True
        assert receipt.verification["sensory"] is True
        assert receipt.verification["state_match"] is True
        assert receipt.verification["contract_mode"] == "process_state"
        assert receipt.rollback["available"] is True
        assert receipt.rollback["executed"] is False
        assert receipt.final_status == "VERIFIED"

        # 5. Hashes & Signature Validation
        assert len(receipt.receipt_hash) == 64
        assert all(c in "0123456789abcdef" for c in receipt.receipt_hash)
        assert len(receipt.signature) == 64
        assert all(c in "0123456789abcdef" for c in receipt.signature)

        # 6. Integrity Check
        assert proof_engine.verify_receipt_integrity(receipt) is True

        # 7. Dict serialization
        r_dict = receipt.to_dict()
        assert isinstance(r_dict, dict)
        assert r_dict["action_id"] == action_id
        assert proof_engine.verify_receipt_integrity(r_dict) is True

    def test_proof_receipt_integrity_validation(self):
        """Verifies hash matches and tampered receipts strictly fail integrity validation."""
        receipt = proof_engine.generate_receipt(
            action_id=f"act_tamper_{uuid.uuid4().hex[:8]}",
            request="toggle_relay",
            planned_action="physical:toggle_relay",
            risk_tier="TIER_1_SOFT",
            authorization={"lease_id": "lease_xyz", "authorized_by": "OPERATOR"},
            execution={"duration_ms": 12.0, "exit_code": 0},
            before_state={"relay": 0},
            after_state={"relay": 1},
            final_status="VERIFIED",
            store=False,
        )

        # Baseline: Valid receipt passes integrity check
        assert proof_engine.verify_receipt_integrity(receipt) is True
        receipt_dict = receipt.to_dict()
        assert proof_engine.verify_receipt_integrity(receipt_dict) is True

        # Tamper 1: Modify before_state
        tampered_before = dict(receipt_dict)
        tampered_before["before_state"] = {"relay": 999}
        assert proof_engine.verify_receipt_integrity(tampered_before) is False

        # Tamper 2: Modify after_state
        tampered_after = dict(receipt_dict)
        tampered_after["after_state"] = {"relay": 0}
        assert proof_engine.verify_receipt_integrity(tampered_after) is False

        # Tamper 3: Modify final_status from VERIFIED to BLOCKED
        tampered_status = dict(receipt_dict)
        tampered_status["final_status"] = "BLOCKED"
        assert proof_engine.verify_receipt_integrity(tampered_status) is False

        # Tamper 4: Modify risk_tier
        tampered_tier = dict(receipt_dict)
        tampered_tier["risk_tier"] = "TIER_3_DESTRUCTIVE"
        assert proof_engine.verify_receipt_integrity(tampered_tier) is False

        # Tamper 5: Modify execution exit_code
        tampered_exec = dict(receipt_dict)
        tampered_exec["execution"] = dict(tampered_exec["execution"])
        tampered_exec["execution"]["exit_code"] = 1
        assert proof_engine.verify_receipt_integrity(tampered_exec) is False

        # Tamper 6: Invalidate receipt_hash
        tampered_hash = dict(receipt_dict)
        tampered_hash["receipt_hash"] = "0" * 64
        assert proof_engine.verify_receipt_integrity(tampered_hash) is False

        # Tamper 7: Invalidate signature
        tampered_sig = dict(receipt_dict)
        tampered_sig["signature"] = "f" * 64
        assert proof_engine.verify_receipt_integrity(tampered_sig) is False

        # Tamper 8: Malicious recalculation of hash without valid HMAC master secret
        tampered_payload = dict(receipt_dict)
        tampered_payload["final_status"] = "VERIFIED"
        tampered_payload["action_id"] = "forged_action_id"
        canonical = proof_engine.compute_canonical_json(tampered_payload)
        forged_hash = proof_engine.compute_receipt_hash(canonical)
        tampered_payload["receipt_hash"] = forged_hash
        # Keeping previous signature -> Signature mismatch
        assert proof_engine.verify_receipt_integrity(tampered_payload) is False

        # Tamper 9: Sign with wrong master secret
        tampered_payload["signature"] = proof_engine.compute_signature(
            canonical, secret="attacker_secret_phrase"
        )
        assert proof_engine.verify_receipt_integrity(tampered_payload) is False

        # Tamper 10: None or missing fields
        assert proof_engine.verify_receipt_integrity(None) is False
        assert proof_engine.verify_receipt_integrity({}) is False

    @pytest.mark.anyio
    async def test_dispatcher_emits_proof_receipt(self):
        """Verifies ActionDispatcher.dispatch emits a cryptographically valid proof_of_execution."""
        action = ActionEnvelope(
            action_id=f"act_dispatch_{uuid.uuid4().hex[:8]}",
            name="launch_app",
            target_world=TargetWorld.COMPUTER,
            target_agent="windows_agent",
            tier=ActionTier.TIER_1_SOFT,
            parameters={"app": "notepad"},
        )

        # Mock windows_agent launch_app to avoid launching real OS apps during test
        with patch("agents.action_dispatcher.windows_agent.launch_app") as mock_launch:
            mock_launch.return_value = {
                "success": True,
                "channel_1_logical": True,
                "pid": 9876,
            }

            result = await action_dispatcher.dispatch(action)

            # Verification of dispatch response
            assert result["success"] is True
            assert result["status"] == "dispatched"
            assert "proof_of_execution" in result

            proof = result["proof_of_execution"]
            assert proof["action_id"] == action.action_id
            assert proof["request"] == "launch_app"
            assert proof["final_status"] == "VERIFIED"
            assert "receipt_hash" in proof
            assert "signature" in proof
            assert "started_at" in proof["execution"]
            assert "finished_at" in proof["execution"]
            assert proof["execution"]["duration_ms"] >= 0
            assert proof["before_state"]["action"] == "launch_app"
            assert proof["after_state"]["action"] == "launch_app"
            assert proof["verification"]["logical"] is True

            # Cryptographic validation
            assert proof_engine.verify_receipt_integrity(proof) is True

            # Verify persisted in ledger
            retrieved = proof_engine.get_receipt(action.action_id)
            assert retrieved is not None
            assert retrieved["action_id"] == action.action_id
            assert retrieved["receipt_hash"] == proof["receipt_hash"]

    @pytest.mark.anyio
    async def test_dispatcher_emits_proof_receipt_on_blocked_action(self):
        """Verifies blocked actions also emit an immutable proof receipt with status BLOCKED."""
        action_destructive = ActionEnvelope(
            action_id=f"act_destr_{uuid.uuid4().hex[:8]}",
            name="format_c_drive",
            target_world=TargetWorld.COMPUTER,
            target_agent="windows_agent",
            tier=ActionTier.TIER_3_DESTRUCTIVE,
            parameters={"drive": "C:"},
        )

        # Tier 3 without approval token is denied
        result = await action_dispatcher.dispatch(action_destructive, approval_token=None)

        assert result["success"] is False
        assert result["status"] == "denied"
        assert "proof_of_execution" in result

        proof = result["proof_of_execution"]
        assert proof["action_id"] == action_destructive.action_id
        assert proof["final_status"] == "BLOCKED"
        assert proof["execution"]["exit_code"] == 1
        assert proof["verification"]["logical"] is False

        # Integrity of blocked action receipt
        assert proof_engine.verify_receipt_integrity(proof) is True

    def test_proof_receipt_storage_and_retrieval(self):
        """Verifies storing and querying receipts from SQLite and JSONL ledger."""
        tmp_dir = tempfile.mkdtemp()
        try:
            isolated_engine = ProofOfExecutionEngine(storage_dir=tmp_dir)

            r1 = isolated_engine.generate_receipt(
                action_id="act_store_001",
                request="ping",
                planned_action="digital:ping",
                risk_tier="TIER_1_SOFT",
                final_status="VERIFIED",
            )
            r2 = isolated_engine.generate_receipt(
                action_id="act_store_002",
                request="restart_service",
                planned_action="digital:restart_service",
                risk_tier="TIER_2_MUTATING",
                final_status="FAILED",
            )
            r3 = isolated_engine.generate_receipt(
                action_id="act_store_003",
                request="delete_bucket",
                planned_action="digital:delete_bucket",
                risk_tier="TIER_3_DESTRUCTIVE",
                final_status="BLOCKED",
            )

            # Test single receipt retrieval
            retrieved_1 = isolated_engine.get_receipt("act_store_001")
            assert retrieved_1 is not None
            assert retrieved_1["action_id"] == "act_store_001"
            assert retrieved_1["final_status"] == "VERIFIED"
            assert isolated_engine.verify_receipt_integrity(retrieved_1) is True

            retrieved_2 = isolated_engine.get_receipt("act_store_002")
            assert retrieved_2 is not None
            assert retrieved_2["final_status"] == "FAILED"
            assert isolated_engine.verify_receipt_integrity(retrieved_2) is True

            retrieved_none = isolated_engine.get_receipt("non_existent_action_xyz")
            assert retrieved_none is None

            # Test listing receipts
            all_receipts = isolated_engine.list_receipts(limit=50)
            assert len(all_receipts) == 3
            # Check ordered latest first
            assert all_receipts[0]["action_id"] == "act_store_003"
            assert all_receipts[1]["action_id"] == "act_store_002"
            assert all_receipts[2]["action_id"] == "act_store_001"

            # Test limit pagination
            limited_receipts = isolated_engine.list_receipts(limit=2)
            assert len(limited_receipts) == 2
            assert limited_receipts[0]["action_id"] == "act_store_003"
            assert limited_receipts[1]["action_id"] == "act_store_002"

            # Test ledger files on disk
            jsonl_file = os.path.join(tmp_dir, "execution_receipts.jsonl")
            assert os.path.exists(jsonl_file)
            with open(jsonl_file, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
            assert len(lines) == 3

            db_file = os.path.join(tmp_dir, "execution_receipts.db")
            assert os.path.exists(db_file)

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_api_verification_receipt_endpoints(self):
        """Verifies GET /api/v1/verification/receipts and GET /api/v1/verification/receipts/{action_id} endpoints."""
        client = TestClient(app)

        test_action_id = f"act_api_{uuid.uuid4().hex[:8]}"
        receipt = proof_engine.generate_receipt(
            action_id=test_action_id,
            request="api_test_action",
            planned_action="digital:api_test_action",
            risk_tier="TIER_1_SOFT",
            final_status="VERIFIED",
            store=True,
        )

        # 1. Query list of receipts
        resp_list = client.get("/api/v1/verification/receipts?limit=10")
        assert resp_list.status_code == 200
        list_data = resp_list.json()
        assert list_data["status"] == "success"
        assert "receipts" in list_data
        assert any(r["action_id"] == test_action_id for r in list_data["receipts"])

        # 2. Query specific verified receipt
        resp_item = client.get(f"/api/v1/verification/receipts/{test_action_id}")
        assert resp_item.status_code == 200
        item_data = resp_item.json()
        assert item_data["status"] == "success"
        assert item_data["action_id"] == test_action_id
        assert item_data["integrity_verified"] is True
        assert item_data["receipt_hash"] == receipt.receipt_hash

        # 3. Query non-existent action ID returns 404
        resp_404 = client.get("/api/v1/verification/receipts/non_existent_act_12345")
        assert resp_404.status_code == 404
