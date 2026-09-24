# J.A.R.V.I.S. Empirical Benchmark Suite

This directory contains the public, reproducible benchmark suite for Project J.A.R.V.I.S., validating system reliability, canonical pipeline execution latencies, blast-radius risk gating, and the **0% false-success invariant** across Computer, Cloud, and Physical worlds.

## Quick Start

Run the full benchmark locally:

```bash
python benchmarks/run_benchmark.py --profile local
```

Custom output and report paths:

```bash
python benchmarks/run_benchmark.py \
  --profile local \
  --tasks benchmarks/benchmark_tasks.yaml \
  --output benchmarks/results/latest.json \
  --report benchmarks/report.md
```

## Structure

- **`run_benchmark.py`**: CLI benchmark runner measuring execution latencies (P50, P90, P95, P99), zero-trust verification accuracy, and policy compliance.
- **`benchmark_tasks.yaml`**: Declarative definition of 100 benchmark tasks across 4 blast-radius tiers (`TIER_0_READ_ONLY`, `TIER_1_REVERSIBLE`, `TIER_2_MUTATING`, `TIER_3_DESTRUCTIVE`).
- **`results/latest.json`**: Machine-readable JSON output of the most recent benchmark run.
- **`report.md`**: Human-readable Markdown summary with latency distribution and invariant compliance audit.

## Evaluated Invariants

1. **Canonical Pipeline Authority**:
   All 100 actions must traverse the single canonical pipeline:
   `INPUT -> NORMALIZER -> CONVERSATION -> PLANNER -> RISK -> PERMISSION -> TOOL -> EXECUTION -> VERIFICATION -> MEMORY -> AUDIT`
   Direct execution bypasses are strictly prevented.

2. **0.0% False-Success Invariant**:
   If a tool claims logical `success: true` but physical/OS verification fails (e.g. process died, file missing, container exited), the pipeline asserts `final_status: "FAILED"`. False-success count must be strictly 0.

3. **Blast-Radius Policy Enforcement**:
   - **Tier 0 (Read-Only)**: Zero confirmation required. Latency P50 < 50ms.
   - **Tier 1 (Soft Mutating)**: Soft confirmation / quick verification.
   - **Tier 2 (Mutating / Disruptive)**: Mandatory operator lease token or explicit approval.
   - **Tier 3 (Destructive)**: Mandatory multi-factor / cryptographic confirmation; cannot execute autonomously.

4. **Deterministic Reproducibility**:
   The suite runs deterministically on standard developer workstations without requiring external cloud accounts or paid third-party APIs.
