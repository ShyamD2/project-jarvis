# Contributing to Project J.A.R.V.I.S. 🚀

Thank you for your interest in contributing to **Project J.A.R.V.I.S.** — the Cyber-Physical Autonomous AgentOS!

We welcome contributions from developers, AI researchers, systems engineers, and hardware tinkerers around the world. Whether you're fixing a bug, adding support for a new hardware sensor, improving the neural wake-word engine, or optimizing latency SLAs, your help makes J.A.R.V.I.S. better for everyone.

---

## 📜 Table of Contents
1. [Code of Conduct](#code-of-conduct)
2. [Architectural Invariants & Ground Rules](#architectural-invariants--ground-rules)
3. [Local Development Setup](#local-development-setup)
4. [Running Verification & Tests](#running-verification--tests)
5. [How to Add a New Domain Tool](#how-to-add-a-new-domain-tool)
6. [Submitting a Pull Request](#submitting-a-pull-request)
7. [Reporting Security Vulnerabilities](#reporting-security-vulnerabilities)

---

## 🤝 Code of Conduct
This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## 🏛 Architectural Invariants & Ground Rules

All contributions must strictly respect the **5 Single Authorities** and the **0% False-Success Invariant**:

1. **Permission Authority (`PermissionEngine`)**: Tools must never bypass or evaluate their own permissions. Every action must be routed through the 4-tier blast radius and acquire a valid single-use `ActionLease`.
2. **Routing Authority (`IntentRouter`)**: Natural language classification, model tier routing, and ambiguity checks belong strictly in the routing layer.
3. **Execution Authority (`ActionDispatcher`)**: Actions are dispatched centrally to ensure pre- and post-state snapshots and cryptographic receipt generation.
4. **Ground-Truth Authority (`VerificationEngine`)**: Tools can never self-certify success! A tool reports raw results; the `VerificationEngine` independently checks logical state (Channel 1) and physical/sensory reality (Channel 2).
5. **Memory Authority (`HierarchicalMemory`)**: Working, episodic, semantic, and procedural state must be accessed through the canonical memory tiers.

---

## 💻 Local Development Setup

### 1. Fork & Clone
```bash
git clone https://github.com/<your-username>/project-jarvis.git
cd project-jarvis
```

### 2. Set Up Virtual Environment (Python 3.10+)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies in Editable Mode
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### 4. Configure Environment
Copy `.env.example` to `.env` and set your local test secrets:
```env
JARVIS_MASTER_SECRET=dev_secret_key_32_characters_minimum
JARVIS_ENV=development
```

---

## 🧪 Running Verification & Tests

Before submitting any Pull Request, ensure that all quality gates and regression suites pass locally:

```powershell
# 1. Run full 285-test regression suite
pytest tests/ -v

# 2. Run security invariant regressions
pytest tests/security/ -v

# 3. Run ground-truth verification invariants
pytest tests/verification/ -v

# 4. Check code style with Ruff (Zero errors allowed)
ruff check services/ shared/ devices/ benchmarks/ --select E,F --ignore E501,E402,F401,F841,F541

# 5. Run static AST security scan with Bandit (Zero Medium/High issues allowed)
bandit -r services/ shared/ -ll -ii -x "tests/,scratch/"

# 6. Execute 100-task empirical benchmark runner
python benchmarks/run_benchmark.py --profile unit
```

---

## 🛠 How to Add a New Domain Tool

New capabilities in J.A.R.V.I.S. should be registered as certified tools in `services/brain/tools/registry.py`:

1. Define a Pydantic schema for tool arguments with strict type hints and docstrings.
2. Implement the tool execution logic in the corresponding agent (`agents/computer/`, `agents/physical/`, or `agents/digital/`).
3. Define the appropriate **Blast Radius Safety Tier** (`TIER_0_REFLEX`, `TIER_1_SOFT`, `TIER_2_MUTATING`, or `TIER_3_DESTRUCTIVE`).
4. Define a **Verification Contract** (`LOGICAL_ONLY`, `PROCESS_STATE`, `FILE_STATE`, `UI_STATE`, `SENSOR_STATE`, `CLOUD_STATE`).
5. Add unit and verification tests in `tests/unit/` and `tests/verification/` proving that:
   - Successful executions transition state and pass verification.
   - Failed or spoofed executions fail closed and cannot declare false success.

---

## 📥 Submitting a Pull Request

1. Create a feature branch with a descriptive name:
   ```bash
   git checkout -b feat/add-philips-hue-support
   ```
2. Commit your changes following [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat(...)`: A new feature or tool capability
   - `fix(...)`: A bug fix or invariant remediation
   - `docs(...)`: Documentation updates
   - `perf(...)`: Latency optimization or SLA improvement
   - `test(...)`: Additional tests or verification cases
3. Push to your fork and submit a PR against `main`.
4. Ensure all GitHub Actions workflows pass (100% Green required for merge).

---

## 🔒 Reporting Security Vulnerabilities

Please do **NOT** open public GitHub issues for security vulnerabilities. Review our [Security Policy](docs/SECURITY.md) for responsible disclosure procedures.
