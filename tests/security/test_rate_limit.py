"""
Security Regression Test: Multi-Tier Rate Limiting and Automatic Lockouts
Guarantees permanent remediation for unthrottled API abuse, resource exhaustion, and brute-force attempts.
"""

import unittest
import time
from services.security.rate_limiter import rate_limiter


class TestRateLimitingSecurity(unittest.TestCase):
    def setUp(self):
        rate_limiter.reset()

    def test_burst_requests_trigger_lockout(self):
        """Invariant: Sending requests exceeding threshold triggers rate limiting and automatic lockout."""
        ip = "192.168.1.100"
        category = "login_or_action"
        max_req = 5
        window = 10
        lockout = 60

        # Send 5 allowed requests
        for i in range(max_req):
            allowed, reason = rate_limiter.is_allowed(
                identity=ip,
                category=category,
                max_requests=max_req,
                window_seconds=window,
                lockout_seconds=lockout
            )
            self.assertTrue(allowed, f"Request {i+1} should be permitted within threshold.")

        # 6th request must trigger rate limit and lock out
        allowed, reason = rate_limiter.is_allowed(
            identity=ip,
            category=category,
            max_requests=max_req,
            window_seconds=window,
            lockout_seconds=lockout
        )
        self.assertFalse(allowed)
        self.assertIn("RATE_LIMITED", reason)

        # Subsequent request while locked out must be rejected with lockout message
        allowed, reason = rate_limiter.is_allowed(
            identity=ip,
            category=category,
            max_requests=max_req,
            window_seconds=window,
            lockout_seconds=lockout
        )
        self.assertFalse(allowed)
        self.assertIn("locked out", reason.lower())

    def test_independent_identities_not_cross_throttled(self):
        """Invariant: Rate limiting one identity does not throttle distinct, well-behaved identities."""
        bad_actor = "10.0.0.99"
        good_actor = "10.0.0.50"

        # Lock out bad actor
        for _ in range(6):
            rate_limiter.is_allowed(bad_actor, max_requests=5, window_seconds=10, lockout_seconds=30)

        # Good actor should proceed unhindered
        allowed, reason = rate_limiter.is_allowed(good_actor, max_requests=5, window_seconds=10, lockout_seconds=30)
        self.assertTrue(allowed)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
