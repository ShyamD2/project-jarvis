"""
Distributed-Aware Multi-Tier Rate Limiter for Project J.A.R.V.I.S. (Phase 36 Item 9).
Implements sliding-window rate limiting with automatic IP lockout.
Supports in-memory tracking with Redis-ready interface for multi-device/distributed nodes.
"""

from __future__ import annotations
import time
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisRateLimiter")


class RateLimiter:
    def __init__(self):
        # Maps endpoint/tier -> identity -> list of timestamps
        self._history: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        # Maps identity -> lockout expiry timestamp
        self._lockouts: Dict[str, float] = {}

    def is_allowed(
        self,
        identity: str,
        category: str = "standard_api",
        max_requests: int = 60,
        window_seconds: int = 60,
        lockout_seconds: int = 300
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluates whether a request from an identity is permitted under sliding-window limits.
        Returns: (allowed: bool, reason: Optional[str])
        """
        now = time.time()

        # 1. Check active lockout
        if identity in self._lockouts:
            if now < self._lockouts[identity]:
                remaining = int(self._lockouts[identity] - now)
                return False, f"RATE_LIMITED: Identity '{identity}' is locked out for {remaining}s."
            else:
                del self._lockouts[identity]

        # 2. Prune expired entries in sliding window
        window_start = now - window_seconds
        timestamps = self._history[category][identity]
        self._history[category][identity] = [t for t in timestamps if t > window_start]

        # 3. Check limit
        current_count = len(self._history[category][identity])
        if current_count >= max_requests:
            # Trigger lockout if excessive
            self._lockouts[identity] = now + lockout_seconds
            logger.warning(f"🚨 [RateLimiter] Rate limit exceeded for '{identity}' on '{category}'. Locked out for {lockout_seconds}s.")
            return False, f"RATE_LIMITED: Exceeded limit of {max_requests} req / {window_seconds}s on category '{category}'."

        # 4. Record new request
        self._history[category][identity].append(now)
        return True, None

    def reset(self, identity: Optional[str] = None):
        """Resets rate limiting state (useful for test isolation)."""
        if identity:
            self._lockouts.pop(identity, None)
            for cat in self._history:
                self._history[cat].pop(identity, None)
        else:
            self._history.clear()
            self._lockouts.clear()


rate_limiter = RateLimiter()
