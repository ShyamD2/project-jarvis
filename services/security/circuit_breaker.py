"""
Circuit Breaker Pattern for Project J.A.R.V.I.S. Tools & Integrations (Phase 36 Stage 36.8).
Protects external APIs, subsystems, and the host from cascading failures:
  - States: CLOSED (healthy), OPEN (tripped / fast-fail), HALF_OPEN (probing).
  - Configurable failure threshold and automatic recovery timeout window.
"""

from __future__ import annotations
import time
from enum import Enum
from typing import Dict, Any, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisCircuitBreaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"         # Normal operation; calls proceed
    OPEN = "OPEN"             # Tripped; fast-failing calls
    HALF_OPEN = "HALF_OPEN"   # Probing single trial request


class CircuitBreakerEntry:
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout_seconds: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time: float = 0.0
        self.last_state_change: float = time.time()
        self.total_trips = 0

    def can_execute(self) -> bool:
        now = time.time()
        if self.state == CircuitState.CLOSED:
            return True

        elif self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed to test probe
            if (now - self.last_failure_time) >= self.recovery_timeout_seconds:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                logger.info(f"🟡 [CircuitBreaker] '{self.name}' entering HALF_OPEN probe state.")
                return True
            return False

        elif self.state == CircuitState.HALF_OPEN:
            # In half-open, allow only single trial call
            return True

        return False

    def record_success(self):
        if self.state in [CircuitState.HALF_OPEN, CircuitState.OPEN]:
            logger.info(f"🟢 [CircuitBreaker] '{self.name}' recovered: transitioning to CLOSED.")
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.last_state_change = time.time()

    def record_failure(self, error: Optional[str] = None):
        now = time.time()
        self.consecutive_failures += 1
        self.last_failure_time = now

        if self.state == CircuitState.HALF_OPEN or self.consecutive_failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = now
            self.total_trips += 1
            logger.error(
                f"🔴 [CircuitBreaker] '{self.name}' TRIPPED to OPEN ({self.consecutive_failures} failures). "
                f"Fast-failing calls for {self.recovery_timeout_seconds}s. Reason: {error or 'Exceeded failure threshold'}"
            )

    def trip(self, reason: str = "Manual or policy trip"):
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()
        self.last_state_change = time.time()
        self.total_trips += 1
        logger.error(f"🔴 [CircuitBreaker] '{self.name}' manually TRIPPED to OPEN: {reason}")

    def reset(self):
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.last_state_change = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_seconds": self.recovery_timeout_seconds,
            "total_trips": self.total_trips,
            "last_failure_time": self.last_failure_time
        }


class CircuitBreakerRegistry:
    def __init__(self, default_failure_threshold: int = 3, default_recovery_timeout: float = 30.0):
        self._circuits: Dict[str, CircuitBreakerEntry] = {}
        self.default_threshold = default_failure_threshold
        self.default_timeout = default_recovery_timeout

    def get_circuit(self, name: str) -> CircuitBreakerEntry:
        if name not in self._circuits:
            self._circuits[name] = CircuitBreakerEntry(
                name=name,
                failure_threshold=self.default_threshold,
                recovery_timeout_seconds=self.default_timeout
            )
        return self._circuits[name]

    def can_execute(self, name: str) -> bool:
        return self.get_circuit(name).can_execute()

    def record_success(self, name: str):
        self.get_circuit(name).record_success()

    def record_failure(self, name: str, error: Optional[str] = None):
        self.get_circuit(name).record_failure(error)

    def trip(self, name: str, reason: str = "Manual trip"):
        self.get_circuit(name).trip(reason)

    def reset(self, name: str):
        self.get_circuit(name).reset()

    def get_all_circuits(self) -> Dict[str, Dict[str, Any]]:
        return {k: v.to_dict() for k, v in self._circuits.items()}


circuit_breaker_registry = CircuitBreakerRegistry()
circuit_breaker = circuit_breaker_registry
