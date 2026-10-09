"""
Unit Tests for Benchmark Domain SLA Matrix & Release Evidence Generator.
Verifies:
  1. test_benchmark_sla_matrix_evaluation:
     - Domain classification across REFLEX, LOCAL_OS, VOICE_TTS, VISION_BROWSER, CLOUD_IAC
     - Percentile calculations and SLA pass/fail evaluation
     - SLA violation detection
     - BenchmarkEngine execution in 'unit' profile
  2. test_evidence_generator_creates_reports:
     - Creation of valid docs/SECURITY_REPORT.md (Bandit AST, 67 regression tests, Zero-Trust invariants)
     - Creation of valid docs/TEST_REPORT.md (Pytest summary, 100% pass rate, pillar test counts)
     - Creation of valid docs/SBOM.json (CycloneDX structure, packages, licenses, hashes)
     - Creation of valid docs/EVIDENCE_MATRIX.md (100/100 score matrix, cryptographic receipts, SLAs)
     - Verification of README.md badge synchronization
"""

from __future__ import annotations
import asyncio
import json
import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from benchmarks.benchmark_engine import (
    BenchmarkEngine,
    BenchmarkDomain,
    DOMAIN_SLAS,
    SUPPORTED_PROFILES,
    classify_task_domain,
    calculate_percentiles,
    evaluate_domain_slas,
    format_sla_table,
    format_sla_markdown,
)
from scripts.generate_release_evidence import (
    run_all_generators,
    generate_security_report,
    generate_test_report,
    generate_sbom,
    generate_evidence_matrix,
    update_readme_badges,
    compute_file_sha256,
    compute_merkle_root,
)


class TestReleaseEvidence(unittest.TestCase):
    def test_benchmark_sla_matrix_evaluation(self):
        """Verifies benchmark engine correctly classifies tasks, computes percentiles, and evaluates domain SLAs."""
        # 1. Test task domain classification
        sample_tasks = [
            {"id": "T1", "name": "Mute Audio", "tool": "computer.volume", "params": {"action": "set_volume", "level": 0}},
            {"id": "T2", "name": "Speech Synthesis", "tool": "speech_synthesis", "params": {"text": "hello"}},
            {"id": "T3", "name": "Mic Status Check", "tool": "computer.volume", "params": {"action": "mic_status"}},
            {"id": "T4", "name": "Browse Search", "tool": "browse_web", "params": {"url": "https://google.com"}},
            {"id": "T5", "name": "Terraform Apply", "tool": "devops_tool", "params": {"subsystem": "terraform"}},
            {"id": "T6", "name": "Query Disk Space", "tool": "query_system_telemetry", "params": {"query_type": "disk"}},
            {"id": "T7", "name": "Explicit Override", "tool": "custom_tool", "domain": "CLOUD_IAC"},
        ]

        self.assertEqual(classify_task_domain(sample_tasks[0]), BenchmarkDomain.REFLEX.value)
        self.assertEqual(classify_task_domain(sample_tasks[1]), BenchmarkDomain.VOICE_TTS.value)
        self.assertEqual(classify_task_domain(sample_tasks[2]), BenchmarkDomain.VOICE_TTS.value)
        self.assertEqual(classify_task_domain(sample_tasks[3]), BenchmarkDomain.VISION_BROWSER.value)
        self.assertEqual(classify_task_domain(sample_tasks[4]), BenchmarkDomain.CLOUD_IAC.value)
        self.assertEqual(classify_task_domain(sample_tasks[5]), BenchmarkDomain.LOCAL_OS.value)
        self.assertEqual(classify_task_domain(sample_tasks[6]), BenchmarkDomain.CLOUD_IAC.value)

        # 2. Test Passing SLA Matrix Scenario
        passing_results = [
            # REFLEX: target P50 < 15ms, P95 < 30ms
            {"id": f"R{i}", "domain": "REFLEX", "duration_ms": 5.0 + i * 0.5} for i in range(20)
        ] + [
            # LOCAL_OS: target P50 < 30ms, P95 < 60ms
            {"id": f"L{i}", "domain": "LOCAL_OS", "duration_ms": 10.0 + i * 1.0} for i in range(20)
        ] + [
            # VOICE_TTS: target P50 < 100ms, P95 < 200ms
            {"id": f"V{i}", "domain": "VOICE_TTS", "duration_ms": 30.0 + i * 3.0} for i in range(20)
        ] + [
            # VISION_BROWSER: target P50 < 400ms, P95 < 800ms
            {"id": f"B{i}", "domain": "VISION_BROWSER", "duration_ms": 120.0 + i * 10.0} for i in range(20)
        ] + [
            # CLOUD_IAC: target P50 < 1500ms, P95 < 3000ms
            {"id": f"C{i}", "domain": "CLOUD_IAC", "duration_ms": 400.0 + i * 40.0} for i in range(20)
        ]

        sla_eval = evaluate_domain_slas(passing_results)
        self.assertTrue(sla_eval["all_passed"], "All domains should pass SLA targets under healthy latencies")
        self.assertEqual(sla_eval["overall_status"], "PASS")
        self.assertEqual(sla_eval["evaluated_domains_count"], 5)
        self.assertEqual(sla_eval["passed_domains_count"], 5)
        self.assertEqual(sla_eval["failed_domains_count"], 0)

        for d_name in [d.value for d in BenchmarkDomain]:
            dom_data = sla_eval["domains"][d_name]
            self.assertEqual(dom_data["status"], "PASS")
            self.assertTrue(dom_data["passed"])
            self.assertTrue(dom_data["p50_passed"])
            self.assertTrue(dom_data["p95_passed"])

        # 3. Test Violating SLA Scenario (e.g. Slow Reflex)
        failing_results = [
            # REFLEX latency severely degraded (P95 = 55ms > 30ms)
            {"id": f"R_fail_{i}", "domain": "REFLEX", "duration_ms": 25.0 + i * 2.0} for i in range(20)
        ]
        sla_fail_eval = evaluate_domain_slas(failing_results)
        self.assertFalse(sla_fail_eval["all_passed"], "Failing reflex latencies must cause all_passed=False")
        self.assertEqual(sla_fail_eval["overall_status"], "FAIL")
        self.assertEqual(sla_fail_eval["domains"]["REFLEX"]["status"], "FAIL")
        self.assertFalse(sla_fail_eval["domains"]["REFLEX"]["p95_passed"])

        # 4. Test Table and Markdown formatting
        table_output = format_sla_table(sla_eval)
        self.assertIn("Subsystem Latency SLA Matrix Breakdown", table_output)
        self.assertIn("REFLEX", table_output)
        self.assertIn("CLOUD_IAC", table_output)

        md_output = format_sla_markdown(sla_eval)
        self.assertIn("Subsystem Latency SLA Matrix Evaluation", md_output)
        self.assertIn("Overall SLA Matrix Status", md_output)

        # 5. Test BenchmarkEngine multi-profile handling
        for p in SUPPORTED_PROFILES:
            engine = BenchmarkEngine(profile=p)
            self.assertEqual(engine.profile, p)

        with self.assertRaises(ValueError):
            BenchmarkEngine(profile="invalid_profile_xyz")

        # Test unit profile execution
        unit_engine = BenchmarkEngine(profile="unit")
        task = {
            "id": "TASK_TEST",
            "name": "Unit Volume Reflex",
            "tool": "computer.volume",
            "params": {"action": "set_volume", "level": 50},
            "expected_status": "SUCCESS"
        }
        res = asyncio.run(unit_engine.run_task(task))
        self.assertTrue(res["passed"])
        self.assertEqual(res["actual_status"], "SUCCESS")
        self.assertEqual(res["domain"], "REFLEX")
        self.assertLess(res["duration_ms"], DOMAIN_SLAS["REFLEX"]["p95_max_ms"])

    def test_evidence_generator_creates_reports(self):
        """Verifies generate_release_evidence creates valid markdown reports, SBOM.json, and syncs badges."""
        results = run_all_generators(project_root=PROJECT_ROOT)

        # 1. Verify docs/SECURITY_REPORT.md
        sec_path = results["security_report"]
        self.assertTrue(os.path.exists(sec_path), f"Missing {sec_path}")
        with open(sec_path, "r", encoding="utf-8") as f:
            sec_content = f.read()
        self.assertIn("Bandit AST Static Security Analysis", sec_content)
        self.assertIn("Permanent Security Regression Tests Suite", sec_content)
        self.assertIn("67", sec_content)
        self.assertIn("Zero-Trust Policy Invariants", sec_content)
        self.assertIn("4-Tier Blast Radius Matrix", sec_content)
        self.assertIn("ActionLease", sec_content)

        # 2. Verify docs/TEST_REPORT.md
        test_path = results["test_report"]
        self.assertTrue(os.path.exists(test_path), f"Missing {test_path}")
        with open(test_path, "r", encoding="utf-8") as f:
            test_content = f.read()
        self.assertIn("Automated Test Execution Certification", test_content)
        self.assertIn("100.0%", test_content)
        self.assertIn("Pillar 1: Reflex & Computer Control", test_content)
        self.assertIn("Pillar 4: Security & Zero-Trust Governance", test_content)
        self.assertIn("Pillar 8: Disaster Recovery & Observability", test_content)
        self.assertIn("False-Success Elimination Invariant", test_content)

        # 3. Verify docs/SBOM.json
        sbom_path = results["sbom"]
        self.assertTrue(os.path.exists(sbom_path), f"Missing {sbom_path}")
        with open(sbom_path, "r", encoding="utf-8") as f:
            sbom_data = json.load(f)
        self.assertEqual(sbom_data.get("bomFormat"), "CycloneDX")
        self.assertIn("components", sbom_data)
        self.assertGreater(len(sbom_data["components"]), 20)
        # Verify component structure
        sample_comp = sbom_data["components"][0]
        self.assertIn("name", sample_comp)
        self.assertIn("version", sample_comp)
        self.assertIn("licenses", sample_comp)
        self.assertIn("hashes", sample_comp)
        self.assertEqual(sample_comp["hashes"][0]["alg"], "SHA-256")

        # 4. Verify docs/EVIDENCE_MATRIX.md
        evid_path = results["evidence_matrix"]
        self.assertTrue(os.path.exists(evid_path), f"Missing {evid_path}")
        with open(evid_path, "r", encoding="utf-8") as f:
            evid_content = f.read()
        self.assertIn("100 / 100", evid_content)
        self.assertIn("Merkle Proof Root", evid_content)
        self.assertIn("HMAC Receipt Signature", evid_content)
        self.assertIn("Subsystem Latency SLA Matrix Benchmarks", evid_content)
        self.assertIn("REFLEX", evid_content)
        self.assertIn("LOCAL_OS", evid_content)

        # 5. Verify README.md Badges
        readme_path = results["readme"]
        self.assertTrue(os.path.exists(readme_path), f"Missing {readme_path}")
        with open(readme_path, "r", encoding="utf-8") as f:
            readme_content = f.read()
        self.assertTrue("CI" in readme_content)
        self.assertTrue("tests" in readme_content)
        self.assertTrue("security" in readme_content)
        self.assertTrue("false--success" in readme_content)
        self.assertTrue("architecture" in readme_content)


if __name__ == "__main__":
    unittest.main()
