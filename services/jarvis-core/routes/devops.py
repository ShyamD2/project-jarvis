"""
DevOps & SRE API Router for Project J.A.R.V.I.S.
Exposes Docker container controls, Git repository state, CI/CD pipeline triggers, and rollback tests.
"""

import os
import sys
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "agents/cloud"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/verification"))

from docker_agent import docker_agent
from git_agent import git_agent
from rollback_engine import rollback_engine

router = APIRouter(prefix="/api/v1/devops", tags=["DevOps & SRE"])


class RestartContainerRequest(BaseModel):
    container: str = Field(..., description="Container name or ID")


class GitCommitRequest(BaseModel):
    message: str = Field(..., description="Commit message")


@router.get("/docker/containers")
async def get_docker_containers():
    """Lists real running Docker containers or reports offline daemon"""
    containers = docker_agent.list_containers()
    is_running = len(containers) > 0 or docker_agent.is_daemon_running()
    return {
        "status": "online" if is_running else "offline",
        "docker_running": is_running,
        "count": len(containers),
        "containers": containers,
        "message": f"{len(containers)} active containers running" if is_running else "Docker Desktop daemon is offline. Click 'Launch Docker Desktop' to start."
    }


@router.post("/docker/launch")
async def launch_docker_desktop():
    """Activates Docker Desktop executable on Windows"""
    paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe"),
        os.path.expandvars(r"%ProgramFiles%\Docker\Docker\Docker Desktop.exe"),
    ]
    for p in paths:
        if os.path.exists(p):
            import subprocess
            subprocess.Popen(f'cmd.exe /c start "" "{p}"', shell=True)
            return {"status": "launching", "path": p}
    return {"status": "error", "message": "Docker Desktop executable not found on host"}


@router.post("/docker/restart")
async def restart_container(req: RestartContainerRequest):
    """Restarts a targeted Docker container"""
    res = docker_agent.restart_container(req.container)
    return {
        "status": "restarted",
        "container": req.container,
        "result": res
    }


@router.get("/git/status")
async def get_git_status():
    """Returns local git working directory status"""
    status = git_agent.get_status()
    return {
        "status": "success",
        "git": status
    }


@router.post("/git/commit")
async def create_git_commit(req: GitCommitRequest):
    """Stages files and creates a git commit"""
    res = git_agent.stage_and_commit(req.message)
    return {
        "status": "committed" if res.get("success") else "error",
        "result": res
    }


# Managed runtime deployment configuration for atomic rollback demonstration
_RUNTIME_DEPLOYMENT_CONFIG: Dict[str, Any] = {
    "version": "1.0.0",
    "cluster_mode": "active-passive",
    "traffic_allocation": {"blue": 100, "green": 0},
    "max_connections": 1000
}


def _restore_deployment_config(saved_state: Dict[str, Any]) -> bool:
    _RUNTIME_DEPLOYMENT_CONFIG.clear()
    _RUNTIME_DEPLOYMENT_CONFIG.update(saved_state)
    return True


rollback_engine.register_rollback_handler("deployment_config", _restore_deployment_config)


@router.post("/rollback/test")
async def test_rollback_engine():
    """Executes a real mutating state transaction that fails verification and triggers atomic rollback with verification"""
    initial_state = dict(_RUNTIME_DEPLOYMENT_CONFIG)

    # 1. Begin transaction checkpoint
    tx_id = rollback_engine.begin_transaction(
        "canary_cluster_upgrade",
        {"deployment_config": dict(initial_state)}
    )

    # 2. Mutate state
    _RUNTIME_DEPLOYMENT_CONFIG["version"] = "2.0.0-rc1-failing"
    _RUNTIME_DEPLOYMENT_CONFIG["traffic_allocation"] = {"blue": 0, "green": 100}
    _RUNTIME_DEPLOYMENT_CONFIG["max_connections"] = 50
    mutated_state = dict(_RUNTIME_DEPLOYMENT_CONFIG)

    # 3. Simulate failure during verification and trigger atomic rollback
    error_msg = "Corroboration failure: Healthcheck endpoint returned 502 Bad Gateway on green deployment"
    success = rollback_engine.rollback_transaction(tx_id, error_msg)

    # 4. Verify actual restoration of state
    is_restored = (_RUNTIME_DEPLOYMENT_CONFIG == initial_state)

    return {
        "status": "verified_rollback" if is_restored else "rollback_failed",
        "tx_id": tx_id,
        "mutation_applied": mutated_state,
        "restored_state": dict(_RUNTIME_DEPLOYMENT_CONFIG),
        "verified_restored": is_restored,
        "rollback_success": success,
        "error_handled": error_msg
    }
