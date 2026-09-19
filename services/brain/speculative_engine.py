"""
Speculative Pre-Computation Engine for Project J.A.R.V.I.S. (Pillar 9).
Proactively pre-computes solutions, diagnostics, commit messages, and test commands
in the background based on workspace state, git diffs, and recent error signals.
Provides 0ms instant responses for anticipated developer instructions.
"""

from __future__ import annotations
import os
import sys
import time
import subprocess
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisSpeculativeEngine")


class SpeculativePreComputationEngine:
    def __init__(self, cache_ttl_seconds: int = 300):
        self.cache_ttl = cache_ttl_seconds
        # Key: topic/intent hash -> Value: {payload, timestamp, confidence, category}
        self._speculative_cache: Dict[str, Dict[str, Any]] = {}
        self._last_git_status: Optional[str] = None
        self._last_error_context: Optional[str] = None

    def cache_size(self) -> int:
        self._prune_expired()
        return len(self._speculative_cache)

    def _prune_expired(self):
        now = time.time()
        expired_keys = [k for k, v in self._speculative_cache.items() if now - v.get("timestamp", 0) > self.cache_ttl]
        for k in expired_keys:
            del self._speculative_cache[k]

    def stage_speculative_result(
        self,
        key: str,
        category: str,
        title: str,
        content: str,
        confidence: float = 0.95,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Stages an anticipatory result in the zero-latency memory cache."""
        self._prune_expired()
        record = {
            "key": key.lower().strip(),
            "category": category,
            "title": title,
            "content": content,
            "confidence": confidence,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }
        self._speculative_cache[record["key"]] = record
        logger.info(f"⚡ [SpeculativeEngine] Staged 0ms response for '{record['key']}' ({category})")
        return record

    def get_speculative_answer(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a pre-computed answer in <1ms if the query matches an anticipated intent.
        """
        self._prune_expired()
        q = query.lower().strip()

        # 1. Exact or partial key match
        for key, item in self._speculative_cache.items():
            if key in q or q in key:
                logger.info(f"⚡ [SpeculativeEngine] 0ms Cache HIT for '{query}' -> [{key}]")
                return item

        # 2. Category intent heuristic matching
        if any(w in q for w in ["commit message", "generate commit", "what should i commit"]):
            if "git_commit" in self._speculative_cache:
                return self._speculative_cache["git_commit"]

        if any(w in q for w in ["why did it fail", "explain error", "fix the test", "how to fix this"]):
            if "last_error" in self._speculative_cache:
                return self._speculative_cache["last_error"]

        if any(w in q for w in ["test status", "run tests", "verify build"]):
            if "test_suggestion" in self._speculative_cache:
                return self._speculative_cache["test_suggestion"]

        return None

    def observe_git_state(self, workspace_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Scans git diff/status in the workspace and pre-computes candidate commit messages.
        Safe, non-blocking, eco-mode.
        """
        target_dir = workspace_path or PROJECT_ROOT
        try:
            res = subprocess.run(
                ["git", "status", "--short"],
                cwd=target_dir,
                capture_output=True,
                text=True,
                timeout=2
            )
            if res.returncode != 0 or not res.stdout.strip():
                return None

            status_output = res.stdout.strip()
            if status_output == self._last_git_status:
                return None  # No changes since last scan

            self._last_git_status = status_output
            lines = [l.strip() for l in status_output.splitlines() if l.strip()]
            modified = [l.split()[-1] for l in lines if l.startswith("M") or " M " in l]
            added = [l.split()[-1] for l in lines if l.startswith("A") or l.startswith("??")]

            summary_parts = []
            if modified:
                summary_parts.append(f"update {len(modified)} files ({', '.join(modified[:3])})")
            if added:
                summary_parts.append(f"add {len(added)} components ({', '.join(added[:3])})")

            commit_msg = f"feat: {'; '.join(summary_parts)}" if summary_parts else "chore: workspace sync"

            return self.stage_speculative_result(
                key="git_commit",
                category="git",
                title="Anticipated Git Commit Message",
                content=(
                    f"**Suggested Conventional Commit:**\n```bash\n"
                    f"git add .\n"
                    f"git commit -m \"{commit_msg}\"\n"
                    f"```\n\n"
                    f"*Detected changes:* {len(lines)} file(s) modified/added."
                ),
                confidence=0.92,
                metadata={"modified": modified, "added": added}
            )
        except Exception as e:
            logger.debug(f"[SpeculativeEngine] Git scan skipped: {e}")
            return None

    def observe_terminal_error(self, command: str, returncode: int, stderr: str) -> Optional[Dict[str, Any]]:
        """
        Proactively intercepts terminal failures and pre-synthesizes immediate fixes.
        """
        if returncode == 0 or not stderr.strip():
            return None

        self._last_error_context = stderr.strip()
        first_error_line = [l for l in stderr.splitlines() if "error" in l.lower() or "exception" in l.lower()]
        summary = first_error_line[0] if first_error_line else stderr.splitlines()[-1]

        # Heuristic fix generation
        remedy = "Review traceback details."
        if "ModuleNotFoundError" in stderr or "No module named" in stderr:
            mod = stderr.split("No module named")[-1].strip().strip("'\"")
            remedy = f"Run `pip install {mod}` or verify Python virtual environment path."
        elif "EADDRINUSE" in stderr or "already in use" in stderr:
            remedy = "Port collision detected. Run `/sre` to automatically isolate and terminate rogue port holders."
        elif "git index.lock" in stderr:
            remedy = "Stale git index lockfile. Run `/sre` or execute `rm -f .git/index.lock`."

        return self.stage_speculative_result(
            key="last_error",
            category="diagnostic",
            title=f"Instant Diagnostic for Failed Command: `{command}`",
            content=(
                f"### ⚡ Speculative Triage: Command Failed (Exit Code {returncode})\n\n"
                f"**Root Cause Summary:**\n`{summary}`\n\n"
                f"**Recommended Remedy:**\n{remedy}\n\n"
                f"*Pre-computed in background ready for instant remediation.*"
            ),
            confidence=0.98,
            metadata={"command": command, "returncode": returncode}
        )

    def get_status_report(self) -> Dict[str, Any]:
        """Returns diagnostic metrics on cached speculative assets."""
        self._prune_expired()
        return {
            "cached_entries": len(self._speculative_cache),
            "keys": list(self._speculative_cache.keys()),
            "ttl_seconds": self.cache_ttl,
            "has_error_staged": "last_error" in self._speculative_cache,
            "has_git_staged": "git_commit" in self._speculative_cache
        }


speculative_engine = SpeculativePreComputationEngine()
