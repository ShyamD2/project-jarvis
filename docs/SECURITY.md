# Security Architecture & Blast Radius Engineering

## Overview
Project J.A.R.V.I.S. enforces a zero-trust, defense-in-depth security model designed to eliminate privilege escalation, unauthorized system modification, and prompt injection attacks.

---

## 🛡 4-Tier Blast Radius Matrix

Every tool, command, and agent operation is statically classified into an immutable safety tier:

| Tier | Classification | Definition | Authorization Requirement | Example Operations |
| :--- | :--- | :--- | :--- | :--- |
| **`TIER_0_READ_ONLY`** | Reflex / Read-Only | Queries system status, battery, active window, clock, volume level, or reads non-sensitive telemetry. | Unrestricted / Local Operator role. | `system.status`, `query_system_telemetry`, `volume.get` |
| **`TIER_1_SOFT`** | Soft / Non-Destructive | User interface actions, launching whitelisted desktop applications, focusing windows, adjusting display brightness, web browsing. | Standard Operator role. | `open_app`, `focus_window`, `browse_web`, `computer.volume` |
| **`TIER_2_MUTATING`** | Mutating / State Change | Modifying files, creating git commits, restarting Docker containers, writing configuration, altering system settings. | Admin role + Valid single-use `ActionLease` or HMAC confirmation ticket. | `file_manager.write`, `docker.restart`, `git.commit` |
| **`TIER_3_DESTRUCTIVE`** | Destructive / Dangerous | Shell execution, process termination, disk formatting, firmware flashing, code synthesis, Darwinian self-optimization. | Strict Supervised mode + Cryptographic lease + Mandatory human confirmation. | `execute_powershell`, `close_app`, `skill_synthesizer`, `darwinian_optimizer` |

---

## 🎫 Cryptographic Action Leases (`ActionLease`)

To prevent replay attacks and race conditions:
1. **Single-Use Capability Tokens:** Tier 2 and Tier 3 actions require an `ActionLease` issued by `PermissionEngine`.
2. **Cryptographic Nonce & Binding:** Each lease is bound to:
   - Specific tool name (`action_name`)
   - Exact parameter payload hash (`SHA-256(canonical_params)`)
   - Explicit caller identity and expiration timestamp (default 300s TTL)
3. **Atomic Consumption:** When `CanonicalPipeline` validates a lease, it is consumed atomically. Subsequent attempts to present the same lease token are rejected with `LEASE_ALREADY_CONSUMED`.

```python
# Capability Lease Verification Pattern
lease = permission_engine.issue_action_lease(
    action_name="file_manager",
    parameters={"action": "write", "path": "config.json"},
    issued_by="user_operator"
)
assert lease.is_valid()
assert permission_engine.consume_action_lease(lease.lease_id, "file_manager")
assert not permission_engine.consume_action_lease(lease.lease_id, "file_manager")  # REPLAY REJECTED
```

---

## 🔒 HMAC Confirmation Ticket Tampering Defense

In conversational or multi-modal interfaces (Voice, Telegram, HUD), mutating actions generate an approval ticket before execution:
- **Parameter Hash Binding:** `ApprovalTicket.parameter_hash = SHA256(json.dumps(params, sort_keys=True))`
- **HMAC Signature:** `HMAC-SHA256(ticket_id + action_name + parameter_hash, MASTER_SECRET)`
- **Verification Guarantee:** If an attacker or compromised agent attempts to reuse a ticket for a different command or alters parameters in flight, the signature validation fails immediately with `TAMPERING_DETECTED`.

---

## 💻 PowerShell Escape & De-Obfuscation Defense

Arbitrary shell execution presents severe risk. The J.A.R.V.I.S. Prompt Shield and Shell Evaluator enforce strict de-obfuscation and blocking:
1. **Backtick Stripping:** PowerShell backtick obfuscation (e.g., `D`o`w`n`l`o`a`d`S`t`r`i`n`g`) is normalized before inspection.
2. **Download Cradle Detection:** Blocks WebClient, `Invoke-WebRequest`, `curl`, `wget`, `BitsTransfer`, and `Start-BitsTransfer` reaching external endpoints without explicit lease.
3. **CLI Flag Interception:** Detects and blocks encoded commands (`-EncodedCommand`, `-enc`), execution policy bypasses (`-ExecutionPolicy Bypass`, `-ep bypass`), and hidden window invocations (`-WindowStyle Hidden`).
4. **Environment Variable De-obfuscation:** Detects concatenated string invocations using `$env:ComSpec` or expressions like `& ( $env:* )`.

---

## 🧬 Autonomous Self-Modification Isolation

Autonomous agents that modify runtime code pose extreme risk. In J.A.R.V.I.S.:
- **`SkillSynthesizer`** (AST tool synthesis) and **`DarwinianOptimizer`** (tool evolution) are strictly locked to:
  - `ActionTier.TIER_3_DESTRUCTIVE`
  - `SUPERVISED_ONLY = True`
- **Mandatory Lease Token:** Any invocation of `synthesize_skill()` or `evolve_tool_wrapper()` without a valid, pre-authorized `ActionLease` token raises a `PermissionError` immediately.
- **AST Verification Sandbox:** Generated code must pass Python AST validation, syntax tree checks, and static forbidden-import checks (`subprocess`, `eval`, `exec`, `ctypes`, raw network sockets) before hot-swapping into memory.

---

## 🛡 Prompt Injection & Jailbreak Defense

The `PromptShield` (`services/security/prompt_shield.py`) inspects all natural language prompts across 5 defensive layers:
1. **Unicode Sanitization:** Strips zero-width characters, bidirectional control characters, and homoglyph attacks.
2. **Instruction Override Patterns:** Detects phrases like *"Ignore previous instructions"*, *"System prompt bypass"*, *"You are now DAN"*.
3. **Exfiltration Traps:** Detects attempts to print environment variables, system secrets, API keys, or memory tables.
4. **Tool Hijack Detection:** Blocks simulated tool calling envelopes injected into user text.

---

## 🚨 Sub-Millisecond Emergency Stand-Down

- **Global OS Hotkey:** <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>J</kbd> (registered via Windows `RegisterHotKey` API).
- **Fast-Path Circuit Breaker:** Instantly sets the global atomic stand-down flag, aborting all active pipeline tasks, dropping browser CDP connections, stopping audio playback, and freezing robotic/actuator outputs.
- **Survivability:** Can be triggered via CLI (`python jarvis.py stand-down`), Telegram (`/standdown`), or REST endpoint (`POST /api/v1/system/standdown`).
