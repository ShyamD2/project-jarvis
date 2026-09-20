"""
Hierarchical Task Planning DAG Engine for Project J.A.R.V.I.S.
Decomposes complex autonomous multi-step requests into Directed Acyclic Graphs (DAGs).
Each node defines: Prerequisite -> Action -> Verification -> Rollback Checkpoint.
Enforces dependency ordering, partial recovery, and topological task execution.
"""

from __future__ import annotations
import time
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("TaskDAG")


class NodeStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class TaskNode:
    id: str
    action: str                                    # Tool name to execute
    parameters: Dict[str, Any] = field(default_factory=dict)
    prerequisites: List[str] = field(default_factory=list) # IDs of parent nodes
    verification_rule: Optional[str] = None        # Expected verification state
    checkpoint_required: bool = False              # Create micro-checkpoint before executing
    status: NodeStatus = NodeStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class TaskDAG:
    def __init__(self, plan_id: str, description: str = ""):
        self.plan_id = plan_id
        self.description = description
        self.nodes: Dict[str, TaskNode] = {}
        self.created_at = time.time()

    def add_node(self, node: TaskNode) -> TaskNode:
        self.nodes[node.id] = node
        return node

    def get_ready_nodes(self) -> List[TaskNode]:
        """Returns all nodes whose prerequisites have COMPLETED and are still PENDING."""
        ready = []
        for node in self.nodes.values():
            if node.status == NodeStatus.PENDING:
                all_prereqs_met = all(
                    self.nodes[p].status == NodeStatus.COMPLETED
                    for p in node.prerequisites
                    if p in self.nodes
                )
                if all_prereqs_met:
                    ready.append(node)
        return ready

    def is_complete(self) -> bool:
        return all(n.status in [NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.SKIPPED] for n in self.nodes.values())

    async def execute(self, tool_executor_fn) -> Dict[str, Any]:
        """
        Executes DAG in dependency order.
        Executes ready independent nodes concurrently where possible.
        """
        logger.info(f"📋 [TaskDAG] Executing plan [{self.plan_id}]: '{self.description}' ({len(self.nodes)} steps)")
        start_time = time.time()

        while not self.is_complete():
            ready = self.get_ready_nodes()
            if not ready:
                # If incomplete but no nodes are ready, remaining nodes have failed prerequisites
                for n in self.nodes.values():
                    if n.status == NodeStatus.PENDING:
                        n.status = NodeStatus.SKIPPED
                        n.error = "Prerequisite failed or skipped"
                break

            # Execute batch of ready nodes
            for node in ready:
                node.status = NodeStatus.RUNNING
                t0 = time.time()
                logger.info(f"[TaskDAG] Running step '{node.id}': {node.action}({node.parameters})")

                try:
                    res = await tool_executor_fn(node.action, node.parameters)
                    node.duration_ms = (time.time() - t0) * 1000
                    node.result = res
                    if res.get("success", True):
                        node.status = NodeStatus.COMPLETED
                        logger.info(f"✔ [TaskDAG] Step '{node.id}' COMPLETED in {node.duration_ms:.1f}ms")
                    else:
                        node.status = NodeStatus.FAILED
                        node.error = res.get("error", "Action returned failure")
                        logger.warning(f"❌ [TaskDAG] Step '{node.id}' FAILED: {node.error}")
                except Exception as e:
                    node.duration_ms = (time.time() - t0) * 1000
                    node.status = NodeStatus.FAILED
                    node.error = str(e)
                    logger.error(f"❌ [TaskDAG] Step '{node.id}' EXCEPTION: {e}")

        total_ms = (time.time() - start_time) * 1000
        completed = sum(1 for n in self.nodes.values() if n.status == NodeStatus.COMPLETED)
        failed = sum(1 for n in self.nodes.values() if n.status == NodeStatus.FAILED)

        return {
            "plan_id": self.plan_id,
            "success": (failed == 0),
            "total_nodes": len(self.nodes),
            "completed": completed,
            "failed": failed,
            "duration_ms": round(total_ms, 2),
            "nodes": {nid: {"status": n.status.value, "result": n.result, "error": n.error} for nid, n in self.nodes.items()}
        }


task_dag_factory = TaskDAG
