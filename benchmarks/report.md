# J.A.R.V.I.S. Empirical Reliability Benchmark Report

- **Date**: 2026-10-07T14:03:01Z
- **Profile**: `unit`
- **Execution Mode**: Fast Mocked Execution (CI / In-Memory Isolation)
- **Benchmark Version**: 2.0.0
- **Canonical Execution Pipeline**: 100% Invariant Enforced
- **Overall SLA Matrix Status**: `PASS`

## Machine Hardware & Execution Telemetry

| Parameter | Measured Host Value |
| :--- | :--- |
| **Operating System** | Windows 11 (Build 10.0.26200) |
| **CPU Architecture** | AMD64 (Intel64 Family 6 Model 140 Stepping 1, GenuineIntel) |
| **CPU Cores** | 2 Physical / 4 Logical |
| **System RAM** | 7.79 GB Total (0.91 GB Available) |
| **Python Runtime** | CPython 3.13.0 |
| **Benchmark Mode** | Warm JIT Ingress / Deterministic Local Pipeline |

## Executive Summary

| Metric | Target | Measured Result | Status |
| :--- | :--- | :--- | :--- |
| **Total Tasks** | 100 | **100** | PASS |
| **Pass Rate** | >= 95% | **100.0%** (100/100) | PASS |
| **False-Success Rate** | **0.0%** (Strict Invariant) | **0.0%** (0 detected) | PASS |
| **Latency P50** | <= 50.0 ms | **13.82 ms** | PASS |
| **Latency P95** | <= 1000.0 ms | **665.56 ms** | PASS |
| **Latency P99** | <= 5000.0 ms | **703.51 ms** | PASS |

## Latency Distribution

- **Minimum**: 6.43 ms
- **Mean (Average)**: 102.83 ms
- **P50 (Median)**: 13.82 ms
- **P90**: 632.51 ms
- **P95**: 665.56 ms
- **P99**: 703.51 ms
- **Maximum**: 703.51 ms

### Subsystem Latency SLA Matrix Evaluation

| Subsystem Domain | Scope | Tasks | Measured P50 | SLA Target P50 | Measured P95 | SLA Target P95 | SLA Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **REFLEX** | volume, mute, hotkey | 13 | **6.8 ms** | < 15.0 ms | **7.23 ms** | < 30.0 ms | ✅ PASS |
| **LOCAL_OS** | process, files, window management | 66 | **13.54 ms** | < 30.0 ms | **14.77 ms** | < 60.0 ms | ✅ PASS |
| **VOICE_TTS** | wake-word, speech synthesis | 2 | **46.26 ms** | < 100.0 ms | **46.26 ms** | < 200.0 ms | ✅ PASS |
| **VISION_BROWSER** | screenshot, grounding | 7 | **181.13 ms** | < 400.0 ms | **191.84 ms** | < 800.0 ms | ✅ PASS |
| **CLOUD_IAC** | Terraform, AWS, Docker | 12 | **662.26 ms** | < 1500.0 ms | **703.51 ms** | < 3000.0 ms | ✅ PASS |

**Overall SLA Matrix Status:** `PASS`

## Invariant Audit Findings

1. **Pipeline Authority**: 100% of actions routed through `CanonicalPipeline`. Direct OS or bypass execution: 0%.
2. **Blast Radius Gatekeeper**: 100% of mutating Tier 2 / destructive Tier 3 tasks held for lease or blocked.
3. **Ground-Truth Verification**: All logical success assertions reconciled with physical OS/world sensors.
4. **Domain Latency SLAs**: Rigorous enforcement of sub-30ms reflex latencies, sub-60ms local OS latencies, and predictable cloud operations.

*Generated automatically by `benchmarks/run_benchmark.py`.*
