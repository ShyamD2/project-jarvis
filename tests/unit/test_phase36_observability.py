"""
Unit & Integration Test Suite for Observability & Tracing Architecture (Stage 36.4).
Verifies:
  1. W3C traceparent formatting, parsing, injection, and extraction.
  2. Per-stage latency breakdown across pipeline stages (Item 114).
  3. Sandboxed event replay with dry-run mutation protection (Item 112).
  4. Prometheus exposition format generation for metrics scraping.
  5. Pre-logging secret redactor sanitization (Item 113).
"""

import unittest
from services.observability.traces import obs_tracer, normalize_trace_id, normalize_span_id
from services.observability.metrics import obs_metrics
from services.observability.event_recorder import obs_recorder
from services.security.secret_redactor import secret_redactor
from services.brain.canonical_pipeline import canonical_pipeline


class TestPhase36Observability(unittest.IsolatedAsyncioTestCase):
    def test_w3c_traceparent_formatting_and_parsing(self):
        """Verifies W3C traceparent compliant generation (00-{32 hex}-{16 hex}-01) and round-trip parsing."""
        span = obs_tracer.start_span("test_w3c_span")
        tp = span.to_traceparent()
        self.assertTrue(tp.startswith("00-"))
        parts = tp.split("-")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], "00")
        self.assertEqual(len(parts[1]), 32)
        self.assertEqual(len(parts[2]), 16)
        self.assertEqual(parts[3], "01")

        # Parse traceparent back
        t_id, p_id, flags = obs_tracer.parse_traceparent(tp)
        self.assertEqual(t_id, span.trace_id)
        self.assertEqual(p_id, span.span_id)
        self.assertEqual(flags, "01")

    def test_w3c_header_injection_and_extraction(self):
        """Verifies context propagation via HTTP headers."""
        span = obs_tracer.start_span("http_egress_test")
        headers = {}
        obs_tracer.inject_traceparent(headers, span)
        self.assertIn("traceparent", headers)
        self.assertIn("x-trace-id", headers)

        extracted_trace, extracted_span = obs_tracer.extract_traceparent(headers)
        self.assertEqual(extracted_trace, span.trace_id)
        self.assertEqual(extracted_span, span.span_id)

    async def test_per_stage_latency_breakdown(self):
        """Verifies per-stage latency tracking across all canonical pipeline phases (Item 114)."""
        res = await canonical_pipeline.execute_request(
            tool_name="system.status",
            parameters={},
            source="test_observability"
        )
        self.assertTrue(res["success"])
        self.assertIn("stage_latencies", res)
        latencies = res["stage_latencies"]

        required_stages = [
            "pipeline_ingress_ms",
            "policy_check_ms",
            "permission_eval_ms",
            "tool_execution_ms",
            "verification_ms",
            "world_model_settlement_ms"
        ]
        for stage in required_stages:
            self.assertIn(stage, latencies)
            self.assertIsInstance(latencies[stage], (int, float))
            self.assertGreaterEqual(latencies[stage], 0.0)

        # Traceparent must be present in response
        self.assertIn("traceparent", res)
        self.assertTrue(res["traceparent"].startswith("00-"))

    def test_sandboxed_event_replay(self):
        """Verifies event replay with dry-run mutation sandbox protection (Item 112)."""
        # Record sample mutating and read-only events
        mock_events = [
            {
                "event": "query_status",
                "timeline_type": "system",
                "data": {"tool": "system_status_report", "risk_tier": "TIER_0_READ_ONLY"}
            },
            {
                "event": "restart_host",
                "timeline_type": "mission",
                "data": {"tool": "pc_power", "action": "restart", "risk_tier": "TIER_3_DESTRUCTIVE"}
            },
            {
                "event": "deploy_container",
                "timeline_type": "mission",
                "data": {"tool": "devops_tool", "action": "deploy", "risk_tier": "TIER_2_MUTATING"}
            }
        ]

        # Dry-run replay must simulate mutating events safely
        result = obs_recorder.replay_events(mock_events, dry_run=True)
        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["total_events"], 3)
        self.assertEqual(result["replayed_count"], 3)
        self.assertEqual(result["simulated_mutations"], 2)

    def test_prometheus_metrics_exposition(self):
        """Verifies Prometheus text exposition format generation."""
        obs_metrics.increment("jarvis_test_counter", 5, labels={"env": "test"})
        prom_text = obs_metrics.get_prometheus_metrics()

        self.assertIn("# HELP jarvis_system_cpu_percent", prom_text)
        self.assertIn("# TYPE jarvis_system_cpu_percent gauge", prom_text)
        self.assertIn("# HELP jarvis_pipeline_requests_total", prom_text)
        self.assertIn("jarvis_system_cpu_percent", prom_text)
        self.assertIn("jarvis_system_memory_percent", prom_text)
        self.assertIn("jarvis_system_disk_percent", prom_text)

    def test_secret_redactor_invariants(self):
        """Verifies pre-logging redactor scrubs credentials from logs and audit strings (Item 113)."""
        sample_log = "Error connecting with AKIAIOSFODNN7EXAMPLE using key sk-1234567890abcdef1234567890abcdef and Bearer eyJhbGciOiJIUzI1NiJ9"
        redacted = secret_redactor.redact_text(sample_log)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", redacted)
        self.assertNotIn("sk-1234567890abcdef1234567890abcdef", redacted)
        self.assertIn("[REDACTED_AWS_KEY_ID]", redacted)
        self.assertIn("[REDACTED_API_KEY]", redacted)


if __name__ == "__main__":
    unittest.main()
