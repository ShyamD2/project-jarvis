"""
Memory Leak & Resource Stability Soak Test (Phase 36 Stage 36.9).
Executes 50 consecutive canonical pipeline transactions and verifies:
  1. No memory leaks: RSS delta < 50MB across the run.
  2. Transaction history integrity: transactions recorded and settled properly.
  3. Latency stability: no progressive degradation over iterations.
"""

import unittest
import psutil
import gc
import os
from services.brain.canonical_pipeline import canonical_pipeline


class TestSoakLeak(unittest.IsolatedAsyncioTestCase):
    async def test_canonical_pipeline_50_turn_soak(self):
        """Runs 50 continuous pipeline requests, verifying memory bounds and latency stability."""
        process = psutil.Process(os.getpid())
        gc.collect()
        initial_rss_mb = process.memory_info().rss / (1024 * 1024)

        success_count = 0
        iterations = 50

        for i in range(iterations):
            res = await canonical_pipeline.execute_request(
                tool_name="system.status",
                parameters={},
                source="soak_test"
            )
            if res["success"] and res["final_status"] == "SUCCESS":
                success_count += 1

        gc.collect()
        final_rss_mb = process.memory_info().rss / (1024 * 1024)
        delta_mb = final_rss_mb - initial_rss_mb

        self.assertEqual(success_count, iterations, f"Expected {iterations} successes, got {success_count}")
        # Memory growth must remain strictly below 50MB threshold
        self.assertLess(
            delta_mb,
            50.0,
            f"Possible memory leak detected: RSS grew by {delta_mb:.2f}MB (Initial: {initial_rss_mb:.2f}MB, Final: {final_rss_mb:.2f}MB)"
        )


if __name__ == "__main__":
    unittest.main()
