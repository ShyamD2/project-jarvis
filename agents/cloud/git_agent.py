"""
Git & GitHub CI/CD Agent for J.A.R.V.I.S. (Cloud Pillar).
Manages repository state, branches, commits, push, pull, logs, and cloning.
"""

from __future__ import annotations
import subprocess
import os
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisGitAgent")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


class GitAgent:
    def __init__(self, repo_dir: str = PROJECT_ROOT):
        self.repo_dir = repo_dir

    def get_status(self) -> Dict[str, Any]:
        """Runs git status --short"""
        logger.info("[GitAgent] Checking git repository status...")
        try:
            res = subprocess.run(
                ["git", "status", "--short"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            changes = [line.strip() for line in res.stdout.split("\n") if line.strip()]
            return {
                "success": res.returncode == 0,
                "clean": len(changes) == 0,
                "changed_files_count": len(changes),
                "changes": changes[:20],
                "channel_1_logical": True
            }
        except Exception as e:
            logger.error(f"[GitAgent] git status failed: {e}")
            return {"success": False, "error": str(e)}

    def stage_and_commit(self, message: str) -> Dict[str, Any]:
        """Stages all changes and creates a commit"""
        logger.info(f"[GitAgent] Staging files and creating commit: '{message}'")
        try:
            subprocess.run(["git", "add", "."], cwd=self.repo_dir, check=True)
            res = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_dir,
                capture_output=True,
                text=True
            )
            return {
                "success": res.returncode == 0,
                "output": res.stdout.strip(),
                "channel_1_logical": res.returncode == 0
            }
        except Exception as e:
            logger.error(f"[GitAgent] git commit failed: {e}")
            return {"success": False, "error": str(e)}

    def push(self, remote: str = "origin", branch: Optional[str] = None) -> Dict[str, Any]:
        """Pushes commits to upstream remote git branch (Tier 2 Disruptive)"""
        logger.info(f"[GitAgent] Pushing to {remote}/{branch or 'current'}")
        cmd = ["git", "push", remote]
        if branch:
            cmd.append(branch)
        try:
            res = subprocess.run(cmd, cwd=self.repo_dir, capture_output=True, text=True, timeout=30)
            return {"success": res.returncode == 0, "output": res.stdout.strip() or res.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def pull(self, remote: str = "origin", branch: Optional[str] = None) -> Dict[str, Any]:
        """Pulls latest updates from upstream remote"""
        logger.info(f"[GitAgent] Pulling from {remote}/{branch or 'current'}")
        cmd = ["git", "pull", remote]
        if branch:
            cmd.append(branch)
        try:
            res = subprocess.run(cmd, cwd=self.repo_dir, capture_output=True, text=True, timeout=30)
            return {"success": res.returncode == 0, "output": res.stdout.strip() or res.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_branches(self) -> Dict[str, Any]:
        """Lists local git branches and active branch"""
        try:
            res = subprocess.run(["git", "branch"], cwd=self.repo_dir, capture_output=True, text=True, timeout=5)
            lines = [l.strip() for l in res.stdout.split("\n") if l.strip()]
            active = next((l.replace("*", "").strip() for l in lines if l.startswith("*")), "main")
            return {"success": True, "active_branch": active, "branches": lines}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_log(self, count: int = 5) -> Dict[str, Any]:
        """Retrieves recent commit log"""
        try:
            res = subprocess.run(
                ["git", "log", f"-n", str(count), "--oneline"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            commits = [l.strip() for l in res.stdout.split("\n") if l.strip()]
            return {"success": True, "count": len(commits), "commits": commits}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def clone(self, repo_url: str, destination: Optional[str] = None) -> Dict[str, Any]:
        """Clones a remote repository"""
        logger.info(f"[GitAgent] Cloning {repo_url}")
        cmd = ["git", "clone", repo_url]
        if destination:
            cmd.append(destination)
        try:
            res = subprocess.run(cmd, cwd=self.repo_dir, capture_output=True, text=True, timeout=60)
            return {"success": res.returncode == 0, "output": res.stdout.strip() or res.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}


git_agent = GitAgent()
