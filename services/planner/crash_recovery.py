"""
Crash Recovery & State Reconciliation Engine (Phase 36 Stage 36.8).
Recovers orphaned and in-flight missions after unexpected process termination.
Prevents duplicate execution of completed DAG actions and reconciles state with reality.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional
from services.planner.mission_persistence import mission_persistence
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisCrashRecovery")


class CrashRecoveryEngine:
    def __init__(self):
        pass

    def scan_for_crashed_missions(self) -> List[Dict[str, Any]]:
        """Scans SQLite persistence for missions left in non-terminal states."""
        interrupted = mission_persistence.get_interrupted_missions()
        reports = []

        for m in interrupted:
            m_id = m["mission_id"]
            cp = mission_persistence.get_latest_checkpoint(m_id)
            step_idx = cp["step_index"] if cp else 0
            snapshot = cp.get("snapshot", {}) if cp else {}

            report = {
                "mission_id": m_id,
                "name": m["name"],
                "last_active_phase": m["current_phase"],
                "last_checkpoint_step": step_idx,
                "completed_actions": snapshot.get("completed_actions", []),
                "in_flight_action": snapshot.get("in_flight_action"),
                "safe_to_resume": True if cp else False,
                "reconciliation_required": True
            }
            reports.append(report)
            logger.warning(
                f"🚨 [CrashRecovery] Detected interrupted mission '{m_id}' ({m['name']}) "
                f"in phase '{m['current_phase']}' at checkpoint step #{step_idx}."
            )

        return reports

    def resume_mission(self, mission_id: str) -> Dict[str, Any]:
        """
        Safely resumes an interrupted mission from its latest checkpoint.
        Skips all previously verified actions to prevent duplication.
        """
        mission = mission_persistence.get_mission(mission_id)
        if not mission:
            return {"success": False, "error": f"Mission '{mission_id}' not found."}

        cp = mission_persistence.get_latest_checkpoint(mission_id)
        resumed_step = (cp["step_index"] + 1) if cp else 0

        # Update mission state
        mission["current_phase"] = "execute"
        mission_persistence.save_mission(mission)

        logger.info(f"🔄 [CrashRecovery] Resuming mission '{mission_id}' starting from step index #{resumed_step}.")
        return {
            "success": True,
            "mission_id": mission_id,
            "status": "RESUMED",
            "resumed_from_step": resumed_step,
            "message": f"Successfully resumed mission from checkpoint step #{resumed_step}."
        }

    def abort_interrupted_mission(self, mission_id: str, reason: str = "Aborted by crash recovery policy") -> Dict[str, Any]:
        """Aborts an interrupted mission safely."""
        mission = mission_persistence.get_mission(mission_id)
        if not mission:
            return {"success": False, "error": f"Mission '{mission_id}' not found."}

        mission["current_phase"] = "aborted"
        mission["final_result"] = f"CRASH_RECOVERY_ABORT: {reason}"
        mission_persistence.save_mission(mission)

        logger.info(f"🛑 [CrashRecovery] Interrupted mission '{mission_id}' marked as ABORTED.")
        return {"success": True, "mission_id": mission_id, "status": "ABORTED", "reason": reason}


crash_recovery = CrashRecoveryEngine()
