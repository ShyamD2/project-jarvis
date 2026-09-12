# PROJECT J.A.R.V.I.S. (1.0)
> **Just A Rather Very Intelligent System**  
> A distributed, cyber-physical, autonomous operating system uniting the **Physical**, **Computer**, and **Digital (Cloud)** worlds.

---

## 🏛 Master Architecture

```
                         ┌──────────────────────┐
                         │         YOU          │
                         │ Voice / Phone / Web  │
                         │ Clap / Gesture       │
                         └──────────┬───────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────┐
                    │     JARVIS EXPERIENCE       │
                    │ Voice • Text • Dashboard    │
                    │ Mobile • Notifications      │
                    └─────────────┬───────────────┘
                                  │
══════════════════════════════════╪══════════════════════════════════
                                  ▼
                 ┌────────────────────────────────┐
                 │       JARVIS SENSORY LAYER      │
                 │ 🎤 Voice / Wake Word           │
                 │ 👏 Sound / Clap Detection      │
                 │ 📷 Camera / Vision             │
                 │ 🖥 Screen / UI Understanding  │
                 └───────────────┬────────────────┘
                                 ▼
                 ┌────────────────────────────────┐
                 │      REAL-TIME EVENT FABRIC    │
                 │ Local Fast-Path (<30ms) & AWS  │
                 └───────────────┬────────────────┘
                                 ▼
              ┌──────────────────────────────────────┐
              │             JARVIS BRAIN             │
              │ Tiered Multi-Model (Fast / Deep)     │
              │ Intent Understanding & Agent Runtime │
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
                 │   MASTER ORCHESTRATOR       │
                 │ Task DAG Parallel Engine    │
                 └──────────────┬──────────────┘
                                ▼
                 ┌─────────────────────────────┐
                 │    SECURITY / AUTH ENGINE   │
                 │ 4-Tier Blast Radius Matrix  │
                 │ Emergency Stand-Down Breaker│
                 └──────────────┬──────────────┘
                                ▼
                  ╔═══════════════════════════╗
                  ║       ACTION FABRIC       ║
                  ╚══════════════╤════════════╝
                                 │
       ┌─────────────────────────┼──────────────────────────┐
       ▼                         ▼                          ▼
┌───────────────┐       ┌──────────────────┐       ┌─────────────────┐
│ DIGITAL WORLD │       │ COMPUTER WORLD   │       │ PHYSICAL WORLD  │
│ AWS Cloud     │       │ Windows OS       │       │ ESP32 Nodes     │
│ Terraform IaC │       │ Apps & Terminal  │       │ Relays & Lamps  │
│ LocalStack    │       │ Browser & Screen │       │ Ambient Lux     │
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

## 📅 Chronological Development Log (Day-by-Day)

### 🔹 Day 1 — September 9, 2026: Soundscape & System Genesis
* **Workspace Architecture:** Scaffolded the cyber-physical project structure separating `agents/`, `services/`, `devices/`, `infrastructure/`, and `shared/`.
* **Authentic Movie Soundboard:** Acquired and mapped 5 cinematic audio assets (`welcome_back_jarvis.mp3`, `jarvis_on.mp3`, `Voicy_Creating A Flight Plan.mp3`, `Voicy_I Have Run Simulation .mp3`, `jarvis_alarm.mp3`).
* **Roadmap Definition:** Formulated the architectural blueprint uniting Physical (ESP32), Computer (Windows), and Digital (AWS) worlds.

### 🔹 Day 2 — September 10, 2026: Cyber-Physical Operating Architecture (77 Files Built)
* **Master Schemas & Verification Contracts:** Built `ActionEnvelope` with 4 Blast-Radius safety tiers (`TIER_0_REFLEX`, `TIER_1_SOFT`, `TIER_2_MUTATING`, `TIER_3_DESTRUCTIVE`), `JarvisEvent` CloudEvent envelopes, and dual-channel `VerificationContract`.
* **Zero-Trust Permission Engine:** Implemented dynamic risk classification, least-privilege boundary policies, cryptographic approval tokens (`JARVIS_MASTER_SECRET`), and emergency stand-down circuit breaker.
* **Hybrid Event Mesh:** Integrated local sub-millisecond MQTT broker with AWS EventBridge cloud pub/sub.
* **Local Windows Agent:** Implemented executable path resolution via Windows App Paths registry and system PATH, subprocess spawning, and `psutil` process monitoring.
* **Physical IoT & Microcontroller Firmware:** Created Arduino/C++ firmware for ESP32 microcontrollers controlling dual relays and ambient lux sensors; developed `VirtualESP32` simulation harness.
* **AWS Cloud & IaC Fabric:** Built real Boto3 AWS Agent for IAM STS identity, EC2 describe, S3 management, and local Terraform CLI runner.
* **Sensory Hub:** Integrated neural British TTS (`edge-tts` `en-GB-RyanNeural`), acoustic wake-word listener with room noise calibration, and acoustic clap detection.
* **Cognitive Brain Runtime:** Built sub-millisecond `IntentRouter`, ReAct autonomous loop, and 7-tier Hierarchical Memory (`hierarchical_memory.py`).

### 🔹 Day 3 — September 11, 2026: Autonomous Swarm, Mission DAG & Holographic HUD (27 Files Built)
* **12-Persona Agent Swarm:** Built persona swarm framework (Architect, SRE, Security Sentinel, Cloud Ops, FinOps, etc.) with inter-agent task delegation.
* **Autonomous Mission Engine:** Implemented 8-phase DAG lifecycle (`Analyze` → `Plan` → `Authorize` → `Execute` → `Monitor` → `Verify` → `Fix` → `Report`).
* **Futuristic Command Center HUD:** Built 1,748 lines of frontend UI (`services/jarvis-core/static/index.html`) featuring animated 6-facet Arc Reactor canvas, 32-bar audio spectrum visualizer, central ReAct terminal, and 17 domain consoles.
* **Full Codebase Audit:** Produced comprehensive gap analysis (`AUDIT_REPORT.md`).

### 🔹 Day 4 — September 12, 2026: Full Repair Pass & Real Execution Hardening (53 Files Upgraded)
* **Phase A (Security & Config):** Enforced required master secrets, eliminated hardcoded bypasses, unified AWS region to `us-east-1`, reconciled dependency manifests.
* **Phase B (Process Verification):** Upgraded `windows_agent.py` to capture actual operating system process PIDs with `psutil` validation.
* **Phase C (Audio & Screen):** Synchronized audio on `pygame.mixer` to eliminate colliding audio processes; connected real screen vision grab.
* **Phase D (Cognitive Wiring):** Connected Ollama local LLM cascade with zero-dependency cognitive reflex fallback; wired multi-turn dialogue context into short-term memory.
* **Phase E (IoT Loop):** Wired `DeviceShadowSync` to real MQTT broker on port 1883 with physical lux feedback.
* **Phase F (Rollback & Missions):** Completed 8-phase Mission DAG engine and automated self-healing git commit rollback test.
* **Phase G (FinOps & Diagnostics):** Real Boto3 AWS cost estimation, eliminated swallowed exceptions across all routes, integrated `PCDaemon` into FastAPI lifespan, **achieved 100% test pass rate (12 out of 12 test suites passing)**.
* **Real Execution Audit:** Produced `JARVIS_REAL_EXECUTION_AUDIT.md` mapping end-to-end computer control.

---

## ⚡ 35-Phase Build Matrix

| Phase | System | Status | Verification Point |
| :---: | :--- | :---: | :--- |
| **1** | AWS/IaC Foundation | `READY` | Terraform dev environment validated |
| **2** | JARVIS Core API | `READY` | FastAPI REST & WebSocket streaming server |
| **3** | AI Brain + Agent Runtime | `READY` | ReAct loop with multi-model routing |
| **4** | Real-time Event Fabric | `READY` | Pub/Sub with wildcard routing & DLQ |
| **5** | Memory + World Model | `READY` | Digital Twin, short-term turns, RAG knowledge |
| **6** | Master Planner + Orchestrator | `READY` | Task DAG parallel dependency execution |
| **7** | Security + Permission Engine | `READY` | 4-Tier blast radius & Stand Down breaker |
| **8** | Tool/Action Framework | `READY` | Multi-world action dispatching |
| **9** | Voice + Wake Word | `READY` | Wake-word detection engine |
| **10** | Clap / Sound Engine | `READY` | Waveform energy double-clap reflex (<30ms) |
| **11** | JARVIS Voice Response | `READY` | Neural British TTS with Barge-In interruption |
| **12** | Windows Local Agent | `READY` | CPU, RAM, active window, meeting presence |
| **13** | Windows App Control | `READY` | Window focus, minimize, maximize, launch |
| **14** | File/System Automation | `READY` | Search, preview, audio volume, lock screen |
| **15** | Browser/Web Agent | `READY` | Web search and page text extraction |
| **16** | Screen Vision + UI Agent | `READY` | Desktop screenshot capture and vision QA |
| **17** | AWS Cloud Agent | `READY` | Cloud health & LocalStack integration |
| **18** | Terraform Agent | `READY` | Terraform validate and plan automation |
| **19** | Docker Agent | `READY` | Container inspection and restart |
| **20** | Kubernetes Agent | `PLANNED` | Scoped out for future cloud cluster expansion (not implemented) |
| **21** | Git / CI/CD Agent | `READY` | Git repository staging and commit tracking |
| **22** | Cloud Operations Agent | `READY` | SQS queue and telemetry checks |
| **23** | Cloud Security / SOC Agent | `READY` | IAM least-privilege wildcard policy auditing |
| **24** | Autonomous Remediation | `READY` | Closed-loop self-healing on container alarms |
| **25** | AWS IoT Core | `READY` | Device Shadow synchronizer |
| **26** | ESP32 Physical Agent | `READY` | C++ / Arduino firmware with 4-channel relays |
| **27** | Raspberry Pi Gateway | `READY` | Edge gateway with offline survivability |
| **28** | Sensors + Lights + Relays | `READY` | Virtual ESP32 simulator with Lux & Relays |
| **29** | Unified Physical/Digital World | `READY` | Cross-domain single instruction routing |
| **30** | Multi-Agent Autonomous JARVIS | `READY` | Master agent coordination loop |
| **31** | Verification + Recovery | `READY` | Dual-channel logical + sensory check |
| **32** | JARVIS Hologram Dashboard | `READY` | Arc-Reactor cybernetic web HUD |
| **33** | Mobile / Remote Interface | `READY` | Responsive mobile dashboard over WebSocket |
| **34** | FinOps & Resource Optimization| `READY` | Token budget tracking & frugal mode |
| **35** | Final JARVIS 1.0 Integration | `READY` | Master CLI `jarvis.py` |

---

## 🚀 Quick Start Guide

### 1. Launch the Holographic Arc-Reactor HUD
```powershell
python jarvis.py start
```
*Automatically launches the futuristic dashboard at `http://localhost:8000` in your default browser.*

### 2. Run Autonomous Commands via CLI
```powershell
# Prepare Windows developer workspace (turns on desk lamp, opens VS Code & Terminal)
python jarvis.py run "JARVIS, prepare my workspace"

# Control physical world appliances
python jarvis.py run "JARVIS, turn on the desk lamp"

# Trigger emergency circuit breaker
python jarvis.py stand-down
```

### 3. Run the Full Diagnostic Suite
```powershell
python jarvis.py test
```

### 4. Check Digital Twin World State
```powershell
python jarvis.py status
```

---

## 🧠 Multi-AI Provider Architecture (Gemini + Groq)

Project J.A.R.V.I.S. features an enterprise-grade `AIManager` coordinating multiple cloud and local cognitive engines with automatic fallback, zero data leakage, and offline reflex survivability.

```
       User Voice / Text Request
                   │
                   ▼
       ┌───────────────────────┐
       │   AIManager Engine    │
       └───────────┬───────────┘
                   │
         ┌─────────┴─────────┐
         │ 1. Primary        ▼
         │             ┌───────────────┐
         │             │ Google Gemini │ (gemini-2.5-flash / gemini-1.5-flash)
         │             └───────┬───────┘
         │  Success?           │
         ├───────────── Yes ───┘
         │
         │  Rate Limit / Error / No Key
         ▼
    ┌───────────────┐
    │ 2. Fallback   │
    │  Groq Cloud   │ (llama-3.3-70b-versatile / llama-3.1-8b-instant)
    └───────┬───────┘
            │
            ├────────── Success?
            │
            │ Rate Limit / Error / No Key
            ▼
    ┌───────────────────────┐
    │ 3. Offline Reflex     │ (Regex fast-path intent classifier & local reflex)
    └───────────────────────┘
```

### 🔑 1. How to Configure Gemini (Primary)
1. Navigate to Google AI Studio: [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Sign in with your Google account.
3. Click **Create API Key** and select your project.
4. Copy your API key.
5. Open your local `.env` file in the project root and add:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

### ⚡ 2. How to Configure Groq (High-Speed Fallback)
1. Navigate to the Groq Console: [https://console.groq.com/keys](https://console.groq.com/keys)
2. Sign in or create a free account.
3. Click **Create API Key**, provide a label (e.g. `JARVIS`), and copy the key.
4. Open your local `.env` file in the project root and add:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```

### 🛡 3. Automatic Fallback Mechanism
- When a prompt or tool call is executed, `AIManager` first dispatches to **Google Gemini** for high-context multimodal reasoning.
- If Gemini encounters an API error, rate limit (HTTP 429), quota exhaustion, or if the Gemini key is omitted, `AIManager` instantly falls back to **Groq** (<300ms ultra-low latency).
- If neither provider is reachable or keys are absent, JARVIS switches seamlessly to the **Cognitive Reflex Engine**, ensuring the system never crashes or freezes.
- **Security Guarantee:** API keys are never exposed in logs, console output, or committed to Git (`.gitignore` strictly excludes `.env`). Tool calls are verified through the `PermissionEngine` before execution.

### 🚀 4. Starting JARVIS with AI Enabled
Launch the main daemon or run interactive queries:
```powershell
# Interactive Command Center HUD
python jarvis.py start

# CLI Direct Query
python jarvis.py run "Hello JARVIS, summarize my system status"
```
On boot, JARVIS automatically inspects the environment and prints the active AI status banner without logging sensitive tokens:
- Both configured: `JARVIS AI systems online.`
- Gemini only: `JARVIS online. Gemini is active.`
- Groq only: `JARVIS online. Groq is active.`
- Neither: `AI API keys are not configured. Please add your Gemini or Groq key.`

