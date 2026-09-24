# Ground-Truth Verification & Reliability Engineering

## Overview
A critical vulnerability in autonomous AI agent systems is **false-success reporting**: when an agent claims a task succeeded because an LLM or tool returned a `200 OK` or `{"status": "ok"}`, while in physical reality the application crashed, the process never started, the file was not created, or the light remained off.

Project J.A.R.V.I.S. implements an independent **`VerificationEngine`** that reconciles logical returns against OS process tables, filesystem inodes, and hardware sensors.

---

## 🔍 Dual-Channel Corroboration Principle

An action is declared successful if and only if **both** channels agree:

$$\text{ActionStatus} = \text{LogicalStatus} \land \text{SensoryReality}$$

```
                ┌───────────────────────────────────┐
                │       Action Execution           │
                └───────────────┬───────────────────┘
                                │
               ┌────────────────┴────────────────┐
               ▼                                 ▼
      [Channel 1: Logical]              [Channel 2: Sensory]
     Tool Return Value Check           OS / Physical Reality
     • JSON status: success            • Process Table (psutil PID)
     • Exception handled               • Filesystem SHA-256 hash
     • API return code: 200            • Port listener active
               │                       • Hardware lux / sensor
               ▼                                 ▼
         Logical OK?                       Sensory OK?
               │                                 │
               └────────────────┬────────────────┘
                                │
                                ▼
                   ┌─────────────────────────┐
                   │    Reconciliation       │
                   └────────────┬────────────┘
                                │
         ┌──────────────────────┴──────────────────────┐
         ▼                                             ▼
   Both TRUE ➔ [VERIFIED]                     Discrepancy ➔ [FAILED]
   Proceed with Pipeline                      Trigger Self-Healing / Rollback
```

---

## 🛠 Verification Mechanisms by Domain

### 1. Process Lifecycle Verification
- **Application Launch (`open_app`):** Inspects the OS process table using `psutil.pid_exists(pid)`. Checks that the process remained alive beyond a stabilization window (minimum 0.3s) and matches the expected binary name.
- **Application Termination (`close_app`):** Probes the process table to confirm that the PID is terminated and gone from the process tree.
- **Window State (`focus_window`):** Calls Win32 `GetForegroundWindow()` to ensure the target window is in the foreground.

### 2. Filesystem & Configuration Verification
- **File Writes (`file_manager.write`):** Computes pre-action and post-action SHA-256 checksums to verify that bytes were written to the target path without truncation.
- **File Deletions (`file_manager.delete`):** Verifies that the path no longer exists on disk or has been safely quarantined in the Recycle Bin.

### 3. Container & Infrastructure Verification
- **Docker Services (`docker.restart`, `docker.start`):** Queries Docker daemon inspect endpoint (`docker inspect -f {{.State.Running}} <container>`) to confirm container is active and in healthy running state.
- **Kubernetes Pods & Nodes:** Queries Kubernetes API or returns graceful offline status when disconnected.

### 4. Audio & Physical Hardware Verification
- **Volume Adjustments (`audio_media.set_volume`):** Directly queries the Windows CoreAudio endpoint (`IAudioEndpointVolume`) to ensure the measured volume level matches target percentage within $\pm 2\%$.
- **Ambient Lighting (`iot_agent`):** Queries physical lux sensor telemetry before and after lamp switching to confirm physical lux level change.

---

## 0% False-Success Invariant

In the J.A.R.V.I.S. 100-task empirical benchmark suite:
- A **False Success** is defined as any execution where the tool claims `success: true` or `returncode == 0`, but the independent `VerificationEngine` detects that the desired state was not achieved.
- **Invariant:** The false-success rate must remain strictly **0.00%**. If a discrepancy occurs, the execution is marked as `FAILED` and quarantined for self-healing.

---

## ⏪ Transactional Rollback (`SystemUndo`)

When a multi-step task or mutating operation fails verification:
1. **Pre-Execution Snapshot:** `SystemUndo` captures atomic file diffs and configuration states before execution.
2. **Inverse DAG Execution:** On verification failure, the pipeline generates an inverse DAG sequence reversing all prior mutating actions.
3. **Recovery Verification:** The system verifies that the workstation has returned to its clean baseline state before informing the user.
