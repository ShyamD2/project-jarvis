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

### 🔹 Day 5 — September 13, 2026: 20 Advanced Capability Domains & Hardened 4-Tier Security Matrix
* **3-Pillar Triad Construction:**
  - **Computer Subsystem (`agents/computer/`):** Full power/sleep/lock/display controls, master volume & device switching, multi-monitor display management, sub-pixel mouse/keyboard control, safe Recycle Bin deletion, and Wi-Fi/network diagnostics.
  - **Cloud Subsystem (`agents/cloud/`):** Boto3 AWS STS/S3/EC2/Lambda/Cost Explorer, Git VCS staging & push/pull, Docker container lifecycle, Kubernetes pod & rollout restarts, Terraform IaC synthesis, and SOC security Defender/Firewall auditing.
  - **Intelligence Subsystem (`agents/intelligence/`):** Strict 4-tier blast radius (`safety_guard.py`) with zero-bypass confirmation, sub-millisecond Emergency STOP (`emergency_stop.py`) with global `Ctrl+Shift+J` hotkey, and structured audit trail (`audit_logger.py`).
* **Detailed Report:** See [reports/DAY_5_REPORT_2026-09-13.md](reports/DAY_5_REPORT_2026-09-13.md).

### 🔹 Day 6 — September 14, 2026: Master Real-Time Conversational Voice Upgrade & 3D Arc Reactor
* **Full Voice Pipeline (`services/voice/`):**
  - Continuous wake-word spotting (*"Jarvis"*, *"Hey Jarvis"*) with 8s conversational hold window for follow-up dialogue.
  - VAD dynamic endpointing (1.4s nominal, 2.0s for trailing conjunctions) and sub-5ms vocal barge-in detection ($\text{RMS} > 0.035$).
  - Groq Whisper Large v3 integration with multilingual & Indian English / Tanglish normalizer (*"Chrome open pannu"*, *"volume konjam kammi pannu"*, *"Enakku CPU usage sollu"*, *"Terraform plan run pannu"*).
  - Streaming British neural voice (`en-GB-RyanNeural`, `pitch: -2Hz`, `rate: -2%`) with sentence buffer streaming and authentic MCU soundboard clips.
  - 7 explicit voice session states (`IDLE`, `LISTENING`, `THINKING`, `EXECUTING`, `SPEAKING`, `SUCCESS`, `ERROR`) broadcasting live over `/ws`.
* **Conversational Brain Layer (`services/brain/`):**
  - Bounded multi-turn context (last 15 turns) with reference resolution for pronouns (*"close it"*), telemetry follow-ups (*"And RAM?"*), and search ordinals (*"open the first result"*).
  - Authentic J.A.R.V.I.S. personality generator eliminating robotic boilerplate (*"Operation completed successfully"*).
  - Compound command decomposition and safety confirmation tickets for Tier 3 destructive operations.
* **3D WebGL Holographic Arc Reactor & Observability HUD:**
  - 7-layer procedural 3D Arc Reactor with real-time audio reactivity and state synchronization.
  - Progressive partial transcription display beneath the reactor.
  - Developer Observability Drawer (`Ctrl+D`) displaying real-time STT, LLM, Tool, and TTS latencies.
* **Bug Fixes:** Echo eliminated via single-channel HTML5 player; Opera GX "MENU" dropdown eliminated via Win32 thread attachment; universal Web/System application discovery.
* **Verification:** 100% pass rate (37/37 tests passing in `scratch/test_master_voice_upgrade.py`).
* **Detailed Report:** See [reports/DAY_6_REPORT_2026-09-14.md](reports/DAY_6_REPORT_2026-09-14.md).

### 🔹 Day 7 — September 15, 2026: Remote Touchpad Engine & Sub-millisecond WebSocket Pipeline
* **Remote Touchpad Architecture (`services/gateway/remote_trackpad_server.py`):**
  - Sub-millisecond full-duplex WebSocket server (`/ws/trackpad`) for real-time mobile mouse manipulation.
  - Interactive Desktop Thread Attachment: Resolved Win32 desktop security boundaries (`OpenDesktopW`, `SetThreadDesktop`) ensuring background daemon can inject mouse/keyboard events seamlessly.
  - Real-time video frame generator with dynamic JPEG quality compression and MJPEG live stream.
* **Telegram Mobile Command Center:**
  - Added remote keyboard typing bar, volume controls, system status diagnostics, and remote writing mode.

### 🔹 Day 8 — September 16, 2026: Worldwide HTTPS Tunnel, Tap-To-Click & 2-Finger Gliding
* **Global Access & Cloudflare Tunneling:**
  - Integrated zero-configuration Cloudflare secure public HTTPS tunnel (`*.trycloudflare.com`) enabling worldwide mobile access from cellular networks.
  - Tap-To-Click Vision: Mapped touch coordinates on phone screen directly to Windows desktop pixel coordinates for instantaneous tap-to-click.
  - Gliding Two-Finger Scroll: Implemented multi-touch momentum scrolling for web pages and documents.
* **Intelligent Media & Tab Manager:**
  - Autonomous background music dispatcher (YouTube, Spotify, Amazon Music).
  - Clean browser tab lifecycle management (`Ctrl+T`, `Ctrl+W`, next/prev tab) without closing parent browser windows.

### 🔹 Day 9 — September 17, 2026: High-Security PIN Gate, Native Lock, Cursor Visibility & Hardware Mic Fix
* **High-Security Master PIN Gate (`/remote`):**
  - Protected mobile touchpad and screen streaming behind an un-bypassable Cyber PIN Access Gate with a touch numeric keypad.
  - Unified Master Security PIN shared seamlessly across both Web Touchpad and Cyber Security Barrier.
  - Strict endpoint authorization: all control and video endpoints reject unauthorized requests with `403 Forbidden`.
  - Secure PIN change verification via Telegram: `/setpin <current_pin> <new_pin>` strictly validates current PIN before saving updates; messages auto-deleted for privacy.
* **Native Windows Lock (`Win+L`):**
  - Re-mapped `/lock` and the `🔒 Lock PC` Telegram button directly to Windows native workstation lock (`power_agent.lock_workstation()`).
* **High-Contrast Mouse Pointer Overlay:**
  - Implemented `_draw_cursor_on_image()` rendering a 28px neon cyan mouse cursor with dark outline and precision red hotspot dot on every live stream frame.
* **Physical Hardware Microphone Resolution & DroidCam Bypass:**
  - Diagnosed silent microphone bug: PyAudio had bound to `Microphone (DroidCam Virtual Audio)` streaming `0.48 RMS` (pure silence).
  - Built `get_best_hardware_microphone_index()` algorithm prioritizing physical hardware (`Microphone Array (Intel® Smart Sound Technology for Digital Microphones)`) with `+23` score and penalizing virtual devices (`-50`).
  - Added ambient noise room calibration and resilient phrase timeouts for seamless spoken interaction.

### 🔹 Day 10 — September 18, 2026: Live Stream Master PIN Security, DPI Cursor Alignment, CyberLock & Sub-Second Floating HUD
* **Live Video Stream & Touchpad Master PIN Protection:**
  - Extended Master PIN protection to the live desktop video stream (`/live`).
  - Removed URL authentication token auto-bypasses from Telegram links (`/live`, `/remote`), enforcing Master PIN entry via touch keypad for all mobile sessions.
  - Hardened backend endpoints (`/stream`, `/api/screen/snapshot`, `/ws/trackpad`) to strictly return `403 Forbidden` for unauthenticated requests.
* **Pixel-Perfect Cursor Alignment & DPI Scaling:**
  - Resolved 125% Windows DPI scaling discrepancy (logical `1536×864` vs physical `1920×1080` screen frame).
  - Dynamically scaled pointer coordinates (`scale_x = phys_w / sys_w`, `scale_y = phys_h / sys_h`) to match the exact mouse cursor tip.
  - Rendered a high-contrast 28px neon cyan pointer with 3px black stroke and precision red hotspot dot on live frames.
* **Telegram CyberLock Integration:**
  - Added `🛡️ Cyber Lock` one-tap button to Telegram `MAIN_KEYBOARD`.
  - Registered `/cyberlock` in Telegram's native command list via `setMyCommands` and added full syntax guide in `/help`.
  - Enables zero-blackout physical screen barrier locking while maintaining 100% active live video feed and touch control on mobile.
* **Floating HUD Voice Hearing & Sub-Second Latency (<405ms):**
  - Resolved voice hearing issue on Intel Smart Sound Technology Digital Microphones: Implemented active RMS chunk probing and clamped ambient noise threshold between 180 and 400, preventing fan noise spikes from inflating the threshold to 3190+ and deafening the recognizer.
  - Sub-second latency: Integrated Groq LPU (`qwen/qwen3.8-27b`) with Groq Whisper STT (~120ms) and non-blocking asynchronous speech synthesis, reducing warm command execution latency from >6.5s to **0.405 seconds**!

### 🔹 Day 11 — September 19, 2026: The 11 Frontier Pillars of AgentOS, ChatGPT Creative Depth Overhaul, Sub-200ms Latency & Deep Learning Neural Memory Graph
* **The 11 Frontier Pillars of Project J.A.R.V.I.S. (AgentOS)**:
  - **Pillar 1: Self-Synthesizing Skill Engine (`Demo-to-Code`)**: Observes user instructions or task failures, writes certified Python tool code, AST validates it, and registers it into active runtime with zero restarts (`skill_synthesizer.py`).
  - **Pillar 2: Autonomous Workstation SRE & Self-Healer**: Proactive OS watchdog diagnosing dead ports (8000, 8085), hunting zombie processes, resolving memory/CPU leaks, and executing self-healing recovery runbooks (`workstation_sre.py`).
  - **Pillar 3: Dual-Channel Neuro-Symbolic Computer Use**: Unites visual UI recognition with the native Windows Accessibility Tree (UIAutomation) for zero-latency, pixel-accurate element clicks (`neuro_symbolic_agent.py`).
  - **Pillar 4: Long-Horizon Asynchronous Ghost Worker**: Headless background delegation engine running multi-phase DAG missions asynchronously with real-time executive briefings (`ghost_worker.py`).
  - **Pillar 5: Time-Travel System Undo Engine (`SystemUndo`)**: Maintains transactional snapshots before file mutations or destructive actions; supports sub-4-second inverse DAG rollbacks (`system_undo.py`).
  - **Pillar 6: Predictive Cognitive Shadow**: Anticipates user needs by shadowing developer context and staging speculative unit tests and exception triage (`cognitive_shadow.py`).
  - **Pillar 7: DevSecOps Immune System & AST Sandbox**: Pre-execution security analyzer intercepting destructive commands and credential exfiltration before they execute (`immune_sandbox.py`).
  - **Pillar 8: Cross-Device State Teleporter**: Serializes active desktop state (open tabs, terminal buffers, editor cursors, notes) into an encrypted capsule for instant cross-device hydration (`device_teleporter.py`).
  - **Pillar 9: Speculative Pre-Computation Engine (0ms Experience)**: Pre-computes git commit messages and error triage in the background, delivering answers from cache in **0.022 ms** (`speculative_engine.py`).
  - **Pillar 10: Darwinian Self-Optimizing Agent**: Profiles internal tool latency and error rates, evolves tool implementations using sandbox AST rewriting, and auto-hot-swaps faster versions (`darwinian_optimizer.py`).
  - **Pillar 11: Deep Learning Neural Memory Graph**: Passively extracts facts, technical stacks, and project preferences across sessions; achieves sub-5ms semantic recall (**0.090 ms**) and contextual LLM prompt injection (`neural_memory.py`).
* **ChatGPT Plus-Level Creative Intelligence & Depth**:
  - Removed the restrictive 30-word limit in `agent_runtime.py`, enabling comprehensive explanations, structured comparative markdown tables, and multi-step reasoning.
  - Preserved syntax-highlighted code blocks, tables, and headers across Telegram, desktop, and mobile dashboards (`response_generator.py`).
* **Whole-Ecosystem Sub-200ms Latency Acceleration**:
  - Implemented persistent HTTP/2 connection pooling with `h2` and keep-alive headers in `groq_provider.py`, slashing 150–250ms of network handshake overhead.
  - Built zero-token tool pruning for conversational and conceptual queries, cutting TTFT to **<140 ms**.
  - Eco-Mode verified: Offloaded heavy cognitive reasoning to cloud LPUs, maintaining workstation CPU load **<2%** on low-end hardware.
* **Floating HUD Voice Sensory & Hardware Bridge**:
  - Embedded local Secure Context HTTP server (`HUD_PORT = 8088`), enabling full Web Audio AEC, AGC, and 16kHz WAV streaming.
  - Implemented synchronous Groq Whisper speech transcription (`transcribe_sync`) with hallucination and punctuation noise filtering in `stt_engine.py` (<480ms speech execution).
* **Comprehensive Test Suite**:
  - Built automated test suites (`tests/test_8_pillars.py` + `tests/test_chatgpt_latency_memory.py`) with 100% clean passes (13/13 passing in 7.82s).

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
| **9** | Voice + Wake Word | `READY` | Real-time voice pipeline & 8s wake-word hold |
| **10** | Clap / Sound Engine | `READY` | Waveform energy double-clap reflex (<30ms) |
| **11** | JARVIS Voice Response | `READY` | Streaming British Neural TTS + <5ms Barge-In |
| **12** | Windows Local Agent | `READY` | CPU, RAM, active window, meeting presence |
| **13** | Windows App Control | `READY` | Window focus, minimize, maximize, launch |
| **14** | File/System Automation | `READY` | Search, preview, audio volume, lock screen |
| **15** | Browser/Web Agent | `READY` | Web search and page text extraction |
| **16** | Screen Vision + UI Agent | `READY` | Desktop screenshot capture and vision QA |
| **17** | AWS Cloud Agent | `READY` | Cloud health & LocalStack integration |
| **18** | Terraform Agent | `READY` | Terraform validate and plan automation |
| **19** | Docker Agent | `READY` | Container inspection and restart |
| **20** | Kubernetes Agent | `READY` | Cluster connectivity, pods, rollouts & services |
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
| **32** | JARVIS Hologram Dashboard | `READY` | 7-Layer Procedural 3D WebGL Arc Reactor + Observability HUD |
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

