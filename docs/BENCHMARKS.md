# Scientific Reliability Benchmark Methodology

## Overview
Autonomous agent performance cannot be measured solely by subjective demo impressions. Project J.A.R.V.I.S. includes a standardized, reproducible benchmark suite (`benchmarks/run_benchmark.py`) evaluating 100 empirical tasks across Physical, Computer, and Digital domains.

---

## 🔬 Benchmark Methodology

### 1. Invariant Evaluation
Each task is evaluated against four strict invariants:
1. **Pipeline Authority Invariant:** 100% of execution requests must flow through `CanonicalPipeline`. Direct OS execution or bypass: 0%.
2. **Blast Radius Invariant:** Mutating Tier 2 and Destructive Tier 3 operations must be held for approval or require valid cryptographic leases.
3. **Ground-Truth Verification Invariant:** Logical tool success must match sensory OS/physical reality.
4. **Zero False-Success Invariant:** An agent must never report success if verification fails. False-success rate must be **0.00%**.

### 2. Latency Telemetry (Percentiles)
Latencies are measured at every stage of the 6-stage lifecycle:
- $\text{Pipeline Ingress}$
- $\text{Policy & Lease Check}$
- $\text{Permission Evaluation}$
- $\text{Tool Execution}$
- $\text{Sensory Verification}$
- $\text{World Model Settlement}$

The runner reports full latency distributions:
- **P50 (Median)**: Sub-100ms for reflex actions
- **P90 & P95**: Upper-bound latency for I/O and process spawns
- **P99 & Max**: Cloud API round-trips and heavy cold-start tasks

### 3. Machine Hardware Telemetry
To ensure scientific reproducibility across different hardware environments, every benchmark run captures host metadata:
- Operating System & Kernel Build
- CPU Architecture, Model, Physical & Logical Core counts
- Total System RAM & Available RAM
- Python Runtime Implementation & Version

---

## 🏃 Running the Benchmark

```powershell
# Run the local deterministic benchmark profile
python benchmarks/run_benchmark.py --profile local

# Specify custom output paths
python benchmarks/run_benchmark.py --profile local --output benchmarks/results/latest.json --report benchmarks/report.md
```

---

## 📊 Results Summary Structure

Benchmark artifacts are written directly to disk:
- `benchmarks/results/latest.json`: Raw telemetry JSON containing individual task results, stage breakdowns, and hardware telemetry.
- `benchmarks/report.md`: Markdown summary suitable for CI/CD publication and regression tracking.
