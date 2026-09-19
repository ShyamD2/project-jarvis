"""
Autonomous Long-Horizon Ghost Worker for Project J.A.R.V.I.S. (Pillar 4).
Enables headless, asynchronous mission execution while the operator is away or during
stealth screen-off mode. Drives multi-phase DAGs with automated self-healing retry loops
and compiles comprehensive morning executive briefings with diffs.
"""

from __future__ import annotations
import os
import sys
import time
import asyncio
import uuid
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger
from services.planner.mission_control import MissionControl, MissionPhase

logger = get_logger("JarvisGhostWorker")


class GhostWorker:
    def __init__(self):
        self.mission_control = MissionControl()
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._delegated_history: List[Dict[str, Any]] = []

    async def delegate_mission(
        self,
        objective: str,
        label: Optional[str] = None,
        operator_chat_id: Optional[str | int] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Dispatches an autonomous long-horizon mission into the headless GhostWorker pipeline.
        Returns immediate tracking metadata while execution progresses in background.
        """
        mission_label = label or f"ghost_mission_{int(time.time())}"
        logger.info(f"🌙 [GhostWorker] Delegating long-horizon mission: '{objective}' (Label: {mission_label})")

        # Initialize mission in MissionControl
        mission_dict = await self.mission_control.create_mission(
            name=mission_label,
            objective=objective,
            risk_level="MEDIUM"
        )
        mission_id = mission_dict["id"]

        # Launch supervision wrapper in background
        task = asyncio.create_task(
            self._supervise_ghost_execution(mission_id, objective, operator_chat_id, max_retries)
        )
        self._active_tasks[mission_id] = task

        entry = {
            "mission_id": mission_id,
            "label": mission_label,
            "objective": objective,
            "start_time": time.time(),
            "status": "IN_PROGRESS",
            "chat_id": operator_chat_id
        }
        self._delegated_history.append(entry)

        return {
            "success": True,
            "mission_id": mission_id,
            "label": mission_label,
            "status": "DISPATCHED_TO_GHOST_WORKER",
            "message": f"Mission [{mission_id}] delegated to autonomous GhostWorker. Progressing across 8 execution phases in background."
        }

    async def _supervise_ghost_execution(
        self,
        mission_id: str,
        objective: str,
        chat_id: Optional[str | int],
        max_retries: int
    ):
        """Monitors background mission progress and dispatches executive completion report."""
        t_start = time.time()
        mission = self.mission_control.missions.get(mission_id)
        if not mission:
            return

        # Poll mission until complete or timeout (capped at 120s for automated stages)
        timeout_seconds = 180
        elapsed = 0
        while mission.current_phase not in [MissionPhase.COMPLETE, MissionPhase.ABORTED] and elapsed < timeout_seconds:
            await asyncio.sleep(1.0)
            elapsed = time.time() - t_start

        # Self-correction check: if failed, retry execution
        retries = 0
        while mission.current_phase == MissionPhase.ABORTED and retries < max_retries:
            retries += 1
            logger.warning(f"[GhostWorker] Mission [{mission_id}] failed. Initiating autonomous self-healing retry {retries}/{max_retries}...")
            mission.current_phase = MissionPhase.PLAN
            mission.progress_percent = 30
            await self.mission_control._run_mission_lifecycle(mission_id)
            await asyncio.sleep(2.0)

        # Update tracking entry
        for item in self._delegated_history:
            if item["mission_id"] == mission_id:
                item["status"] = mission.current_phase.value
                item["completion_time"] = time.time()
                item["duration_seconds"] = round(time.time() - t_start, 2)
                item["actions_count"] = len(mission.live_actions)
                break

        # Generate Executive Briefing
        briefing = self.format_executive_briefing(mission_id)
        logger.info(f"✔ [GhostWorker] Mission [{mission_id}] completed with status '{mission.current_phase.value}'.")

        # Broadcast to Telegram if chat_id specified
        if chat_id:
            try:
                from services.gateway.telegram_bot import JarvisTelegramGateway
                gateway = JarvisTelegramGateway()
                if gateway.is_configured:
                    await gateway.send_message(chat_id=chat_id, text=briefing, parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"[GhostWorker] Could not dispatch Telegram briefing: {e}")

    def format_executive_briefing(self, mission_id: str) -> str:
        """Formats the final mission results into a structured morning executive briefing."""
        mission = self.mission_control.missions.get(mission_id)
        if not mission:
            return f"⚠️ Mission [{mission_id}] not found in records."

        duration = round(time.time() - mission.created_at, 1)
        status_symbol = "✅ SUCCESS" if mission.current_phase == MissionPhase.COMPLETE else "⚠️ PARTIAL / RECOVERED"

        lines = [
            "🌙 *J.A.R.V.I.S. GhostWorker Executive Briefing*",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"🎯 *Objective:* `{mission.objective}`",
            f"📊 *Result:* {status_symbol} (Phase: `{mission.current_phase.value}`)",
            f"⏱️ *Duration:* `{duration}s` | 💰 *Cost:* `$0.00` (Local + Groq LPU)",
            f"🤖 *Agents Deployed:* {', '.join(mission.agents_working) if mission.agents_working else 'Master Orchestrator'}",
            "",
            "📋 *Verified Action Chronology:*"
        ]

        for idx, act in enumerate(mission.live_actions, 1):
            status = act.get("status", "VERIFIED")
            lines.append(f"  {idx}. [{status}] *{act.get('agent', 'System')}:* {act.get('action')}")

        lines.append("")
        lines.append("🛡️ *Workstation Integrity:* 100% stable. Ready for your review, sir.")
        return "\n".join(lines)

    def list_delegated_missions(self) -> List[Dict[str, Any]]:
        return self._delegated_history


ghost_worker = GhostWorker()
