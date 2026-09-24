# PROJECT J.A.R.V.I.S. (1.0)
> **Just A Rather Very Intelligent System**  
> An autonomous, cyber-physical operating system uniting the **Physical** (IoT/Sensors/Relays), **Computer** (Windows OS/Desktop/Accessibility/Browser), and **Digital** (AWS Cloud/IaC/DevOps) operational domains.

---

## 📑 Core Documentation Index

Comprehensive technical specifications, security models, and verification reports are documented in modular guides:

| Document | Focus & Coverage |
| :--- | :--- |
| 🏛 **[Architecture & Authorities](docs/ARCHITECTURE.md)** | System topology, the 5 Single Authorities, 6-stage canonical pipeline lifecycle, and event mesh. |
| 🛡 **[Security & Blast Radius](docs/SECURITY.md)** | 4-tier blast radius, universal `ActionLease`, HMAC ticket tampering defense, and PowerShell defenses. |
| 🔍 **[Verification & Reliability](docs/VERIFICATION.md)** | Dual-channel ground-truth verification engine, sensory reality checking, and 0% false-success invariant. |
| 🔬 **[Benchmark Suite & Telemetry](docs/BENCHMARKS.md)** | 100-task empirical benchmark methodology, hardware telemetry recording, and latency distributions. |
| 📡 **[Node Mesh & Device Protocol](docs/DEVICE_PROTOCOL.md)** | Multi-node discovery, capability negotiation, and 4-tier geolocation privacy controls. |
| 🧠 **[Memory & World Model](docs/MEMORY.md)** | 7-stage memory lifecycle, world model temporal confidence decay, and GDPR provenance metadata. |
| 💾 **[Disaster Recovery & Migrations](docs/DISASTER_RECOVERY.md)** | Idempotent database schema migrations (`migrations/`), backup creation, and SHA-256 verification. |
| 📅 **[Development History](docs/DEVELOPMENT_LOG.md)** | Chronological engineering log documenting daily milestones from Day 1 to Day 16. |

---

## 🏛 Master Architecture

```
                         ┌──────────────────────┐
                         │         YOU          │
                         │ Voice / Phone / Web  │
                         │ Audio / Hotkey       │
                         └──────────┬───────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────┐
                    │     JARVIS EXPERIENCE       │
                    │ Voice • Text • Dashboard    │
                    │ Mobile Remote • Telegram    │
                    └─────────────┬───────────────┘
                                  │
══════════════════════════════════╪══════════════════════════════════
                                  ▼
                 ┌────────────────────────────────┐
                 │       JARVIS SENSORY LAYER     │
                 │ 🎤 Local Neural Wake Word      │
                 │ ⚡ Sub-10ms Interrupt Service  │
                 │ 👏 Double-Clap Audio Reflex    │
                 │ 🖥 Screen & UI Accessibility   │
                 └───────────────┬────────────────┘
                                 ▼
                 ┌────────────────────────────────┐
                 │      REAL-TIME EVENT FABRIC    │
                 │ Local Fast-Path & In-Memory    │
                 └───────────────┬────────────────┘
                                 ▼
              ┌──────────────────────────────────────┐
              │             JARVIS BRAIN             │
              │ Tiered Multi-Model (Gemini / Groq)   │
              │ Intent Routing & Agent Runtime       │
              └────────────────┬─────────────────────┘
                               │
             ┌─────────────────┼──────────────────┐
             ▼                 ▼                  ▼
      ┌──────────────┐ ┌──────────────┐ ┌────────────────┐
      │ WORLD MODEL  │ │   MEMORY     │ │ KNOWLEDGE/RAG  │
      │ Digital Twin │ │ Short/Long   │ │ Runbooks       │
      └──────┬───────┘ └──────┬───────┘ └───────┬────────┘
             └─────────────────┼─────────────────┘
                               ▼
                 ┌─────────────────────────────┐
                 │    SECURITY / AUTH ENGINE   │
                 │ 4-Tier Blast Radius Matrix  │
                 │ Universal Action Leases     │
                 └──────────────┬──────────────┘
                                ▼
                  ╔═══════════════════════════╗
                  ║   CANONICAL PIPELINE      ║
                  ╚══════════════╤════════════╝
                                 │
       ┌─────────────────────────┼──────────────────────────┐
       ▼                         ▼                          ▼
┌───────────────┐       ┌──────────────────┐       ┌─────────────────┐
│ DIGITAL WORLD │       │ COMPUTER WORLD   │       │ PHYSICAL WORLD  │
│ AWS Cloud     │       │ Windows OS       │       │ ESP32 Nodes     │
│ Terraform IaC │       │ Apps & Terminal  │       │ Relays & Lamps  │
│ Docker / K8s  │       │ Browser & Screen │       │ Ambient Lux     │
└───────┬───────┘       └────────┬─────────┘       └────────┬────────┘
        │                        │                          │
        └────────────────────────┼──────────────────────────┘
                                 ▼
                  ┌──────────────────────────┐
                  │   VERIFICATION ENGINE    │
                  │ Dual-Channel Real State  │
                  └────────────┬─────────────┘
                               ▼
                        JARVIS RESPONSE
```

---

## 🔬 Empirical Reliability Benchmark (Verified Run)

The system is evaluated using an automated 100-task empirical test suite executing live across the Canonical Pipeline.

### Host Machine Hardware & Execution Telemetry
- **Timestamp**: `2026-09-24T17:00:01Z`
- **Host OS**: Windows 11 (Build 10.0.26200)
- **CPU**: AMD64 Intel64 Family 6 Model 140 (2 Physical / 4 Logical Cores)
- **Host RAM**: 7.79 GB Total (1.01 GB Available)
- **Runtime**: Python 3.13.0 (CPython)

### Measured Results

| Metric | Benchmark Target | Measured Result | Status |
| :--- | :--- | :--- | :--- |
| **Total Test Tasks** | 100 | **100** | PASS |
| **Pass Rate** | $\ge 95\%$ | **100.0%** (100/100) | PASS |
| **False-Success Rate** | **0.0%** (Strict Invariant) | **0.00%** (0 detected) | PASS |
| **Latency P50** | $\le 150\text{ ms}$ | **103.71 ms** | PASS |
| **Latency P90** | $\le 1500\text{ ms}$ | **1314.59 ms** | PASS |
| **Latency P95** | $\le 2500\text{ ms}$ | **1775.89 ms** | PASS |
| **Latency P99** | $\le 8000\text{ ms}$ | **7731.88 ms** | PASS |

*Full results and individual task breakdowns are stored in [`benchmarks/results/latest.json`](benchmarks/results/latest.json) and [`benchmarks/report.md`](benchmarks/report.md).*

---

## 🏷️ 7-Tier Subsystem Maturity Matrix

Rather than asserting unqualified status across heterogeneous components, Project J.A.R.V.I.S. reports maturity against an empirical 7-tier scale:
1. `PRODUCTION-READY` — Validated on live OS, active process tables, filesystems, and continuous integration.
2. `REAL-HARDWARE-VERIFIED` — Validated against physical microphones, speakers, audio mixers, or displays.
3. `INTEGRATION-VERIFIED` — Validated with live integration harnesses or cloud APIs.
4. `UNIT-VERIFIED` — Validated with automated test suites and deterministic mocks.
5. `LAB-VERIFIED` — Validated against local virtual harnesses (e.g. LocalStack, Virtual ESP32).
6. `SIMULATED` — Operational against digital twins or simulated offline fallback layers.
7. `EXPERIMENTAL` — Active research prototypes subject to architectural change.

### 35-Phase Maturity Status

| Phase | Subsystem | Maturity Tier | Ground-Truth Verification Proof |
| :---: | :--- | :--- | :--- |
| **1** | AWS/IaC Foundation | `INTEGRATION-VERIFIED` | Boto3 STS credentials, S3/EC2 describe, Terraform configuration validation. |
| **2** | JARVIS Core API | `PRODUCTION-READY` | FastAPI REST & WebSocket streaming server, OpenAPI v1 contracts, Pydantic schemas. |
| **3** | AI Brain + Agent Runtime | `PRODUCTION-READY` | Multi-model routing (Gemini + Groq + reflex), ReAct loop, 100/100 benchmark. |
| **4** | Real-Time Event Fabric | `INTEGRATION-VERIFIED` | In-memory fast-path pub/sub with wildcard routing, resilient offline MQTT spooling. |
| **5** | Memory + World Model | `PRODUCTION-READY` | SQLite FTS5 persistence, provenance tracking, half-life temporal confidence decay. |
| **6** | Master Planner | `INTEGRATION-VERIFIED` | DAG multi-step execution, topological sorting, dependency tracking. |
| **7** | Security & Permissions | `PRODUCTION-READY` | 4-Tier blast radius, single-use `ActionLease`, HMAC ticket parameter binding. |
| **8** | Tool/Action Registry | `PRODUCTION-READY` | 31 certified domain tools, schema validation, canonical alias resolution. |
| **9** | Voice + Wake Word | `REAL-HARDWARE-VERIFIED` | Local CPU `openWakeWord` ONNX inference, physical Intel microphone array binding. |
| **10** | Clap / Sound Engine | `REAL-HARDWARE-VERIFIED` | Real-time PyAudio waveform double-clap detection (<30ms reflex). |
| **11** | Voice Synthesizer | `REAL-HARDWARE-VERIFIED` | British neural TTS, clause streaming, sub-10ms vocal and hotkey interrupt service. |
| **12** | Windows Local Agent | `REAL-HARDWARE-VERIFIED` | Real OS process inspection via `psutil`, active window detection via Win32. |
| **13** | Windows App Control | `REAL-HARDWARE-VERIFIED` | App Paths registry resolution, window minimize/maximize/focus. |
| **14** | File & System Automation | `REAL-HARDWARE-VERIFIED` | Safe Recycle Bin deletion, CoreAudio master volume synchronization. |
| **15** | Browser / Web Agent | `INTEGRATION-VERIFIED` | CDP auto-attach, Chrome/Edge process spawning, HTTP content extraction. |
| **16** | Screen Vision Agent | `REAL-HARDWARE-VERIFIED` | Real desktop screenshot capture, multi-modal coordinate normalization. |
| **17** | AWS Cloud Agent | `INTEGRATION-VERIFIED` | Boto3 STS caller identity, S3 bucket enumeration, EC2 instance telemetry. |
| **18** | Terraform Agent | `INTEGRATION-VERIFIED` | Automated `terraform validate` and `terraform plan` execution in dev environment. |
| **19** | Docker Agent | `INTEGRATION-VERIFIED` | Container inspection, start/stop/restart lifecycle, log tailing via CLI. |
| **20** | Kubernetes Agent | `SIMULATED` | Graceful offline topology queries when cluster offline; `kubectl` JSON parsing when connected. |
| **21** | Git / CI/CD Agent | `PRODUCTION-READY` | Git repository staging, atomic commit creation, log inspection, clean status checks. |
| **22** | Cloud Operations Agent | `INTEGRATION-VERIFIED` | SQS queue polling and cloud health status diagnostics. |
| **23** | Cloud Security / SOC | `UNIT-VERIFIED` | Static IAM least-privilege wildcard policy auditing and finding generation. |
| **24** | Autonomous Remediation | `INTEGRATION-VERIFIED` | Closed-loop self-healing on container alarms with rollback verification. |
| **25** | AWS IoT Core | `INTEGRATION-VERIFIED` | Device Shadow synchronizer schema and MQTT publish/subscribe hooks. |
| **26** | ESP32 Physical Agent | `LAB-VERIFIED` | Arduino/C++ firmware validated against virtual ESP32 hardware simulator. |
| **27** | Raspberry Pi Gateway | `INTEGRATION-VERIFIED` | Edge node discovery, MQTT bridge forwarding, offline local survivability. |
| **28** | Sensors + Lights + Relays | `LAB-VERIFIED` | Dual-relay actuation and ambient lux sensor verification via simulator. |
| **29** | Unified Multi-World Routing | `PRODUCTION-READY` | Cross-domain single instruction routing dispatched via `CanonicalPipeline`. |
| **30** | Multi-Agent Coordination | `INTEGRATION-VERIFIED` | Persona swarm coordination with task delegation and execution tracking. |
| **31** | Verification & Recovery | `PRODUCTION-READY` | Dual-channel ground-truth verification engine, 0% false-success rate invariant. |
| **32** | Holographic HUD Dashboard | `REAL-HARDWARE-VERIFIED` | 3D WebGL Arc Reactor, 32-bar audio visualizer, developer telemetry drawer. |
| **33** | Mobile Remote Interface | `PRODUCTION-READY` | Cloudflare tunnel remote trackpad with PIN gate, Telegram bot gateway. |
| **34** | FinOps Cost Guard | `PRODUCTION-READY` | Hard daily/monthly USD limits, rate limiting, and auto-degrade to local reflex. |
| **35** | Final Master Integration | `PRODUCTION-READY` | Unified CLI `jarvis.py` controlling daemon, query, tests, and disaster recovery. |

---

## 🚀 Quick Start Guide

### Prerequisites
- Windows 10/11 (64-bit)
- Python 3.10+ (tested on Python 3.13)
- Optional: Google Gemini API key or Groq Cloud API key

### 1. Installation
```powershell
# Clone the repository
git clone https://github.com/ShyamD2/project-jarvis.git
cd "project-jarvis"

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install package and dependencies
pip install -e .
```

### 2. Configure Environment Secrets
Create a `.env` file in the project root:
```env
JARVIS_MASTER_SECRET=generate_a_secure_random_string_here
GEMINI_API_KEY=your_gemini_api_key_optional
GROQ_API_KEY=your_groq_api_key_optional
```

### 3. Run Database Migrations
```powershell
python migrations/migrate.py
```

### 4. Launch JARVIS Command Center
```powershell
python jarvis.py start
```
*Launches the REST API, WebSocket event mesh, and opens the holographic dashboard at `http://localhost:8000`.*

### 5. Execute Commands via CLI
```powershell
# Read-only system inspection (Reflex)
python jarvis.py run "JARVIS, report system vitals"

# Mutating operation (requires operator confirmation / lease)
python jarvis.py run "JARVIS, set master volume to 50%"

# Emergency stand-down
python jarvis.py stand-down
```

---

## 🧪 Comprehensive Verification & Test Suites

The repository contains extensive automated test suites covering unit, integration, security regressions, disaster recovery, and benchmark invariants:

```powershell
# 1. Run Security Regression Suite (39 passing tests)
pytest tests/security/ -v

# 2. Run Offline Survivability Test
pytest tests/integration/test_offline_survivability.py -v

# 3. Run Disaster Recovery & Migration Tests
pytest tests/unit/test_disaster_recovery.py -v

# 4. Run FinOps Hard Budget Limits Test
pytest tests/unit/test_finops_hard_limits.py -v

# 5. Run Node Mesh Protocol & Geolocation Privacy Tests
pytest tests/unit/test_node_mesh_protocol.py -v

# 6. Run World Model Confidence & Provenance Tests
pytest tests/unit/test_world_model_provenance.py -v

# 7. Run 100-Task Empirical Benchmark Suite
python benchmarks/run_benchmark.py --profile local
```

---

## 💾 Disaster Recovery & Backups

Create and verify cryptographic backups of all system databases and configuration states:

```powershell
# Create SHA-256 verified archive
python scripts/backup.py backup --output backups/jarvis_backup.tar.gz

# Verify archive integrity
python scripts/backup.py verify backups/jarvis_backup.tar.gz

# Restore to target directory
python scripts/backup.py restore backups/jarvis_backup.tar.gz --target-dir data/
```

---

## 🔒 Security Policy
Please review [`docs/SECURITY.md`](docs/SECURITY.md) for details on the blast radius safety matrix, capability leases, and responsible vulnerability disclosure.
