# Memory Lifecycle & World Model Confidence

## Overview
Project J.A.R.V.I.S. implements a multi-tier memory and digital twin architecture capable of short-term conversational context, episodic retrieval, long-term factual persistence, and a real-time **World Model** tracking the physical workstation state.

---

## 🌍 World Model & Temporal Confidence Decay

The World Model (`services/memory/world_model.py`) maintains a digital twin of system state: active applications, running processes, audio volume levels, display topology, and connected peripherals.

### 1. Entity State Provenance
Every state entity in the World Model is tracked with rich metadata:
- `name`: Entity identifier (e.g., `app_chrome`, `audio_master_volume`)
- `status`: Entity status string
- `observed_at`: Epoch timestamp of last observation
- `source`: Observing authority (`process_manager`, `audio_agent`, etc.)
- `pid`: Process identifier if applicable
- `confidence`: Floating-point confidence score ($0.0 \le c \le 1.0$)
- `metadata`: Arbitrary contextual attributes

### 2. Temporal Confidence Decay
Perception becomes stale over time. The World Model calculates real-time confidence using half-life linear decay:
$$c(t) = \max\left(0.0, c_0 - \frac{t - t_0}{\tau}\right)$$
where $\tau = 300\text{ seconds}$ by default.

### 3. Stale Observation Pruning
Observations whose confidence drops below a threshold (default $c < 0.20$) are automatically pruned by `prune_stale_entities()`, ensuring that stale assumptions do not mislead the agent planner.

---

## 🧠 7-Stage Memory Lifecycle

Long-term memories follow a formalized 7-stage lifecycle (`services/memory/memory_lifecycle.py`):

```
[1. CAPTURE] ──> [2. EXTRACT] ──> [3. STORE] ──> [4. RECALL] ──> [5. UPDATE] ──> [6. DECAY] ──> [7. DELETE]
```

| Stage | Operation | Invariant / Validation |
| :--- | :--- | :--- |
| **`CAPTURE`** | Raw conversation turn or tool observation ingested. | Strips PII and sensitive API keys. |
| **`EXTRACT`** | Structured fact extraction (`ExtractionEngine`). | Assigns semantic tags and sensitivity classification. |
| **`STORE`** | Persists into SQLite FTS5 database. | Generates immutable `memory_id` and records `source` provenance. |
| **`RECALL`** | Semantic and lexical retrieval. | Filters by temporal decay and sensitivity scope. |
| **`UPDATE`** | Fact contradiction resolution. | Updates `updated_at` timestamp and increments confidence. |
| **`DECAY`** | Unaccessed facts decay gracefully over time. | Exponential/linear half-life decay. |
| **`DELETE`** | Explicit or policy-driven removal. | Atomic removal with GDPR cryptographic audit confirmation. |

---

## 🔒 Memory Provenance & GDPR Privacy

Every stored memory item includes complete provenance fields:
```json
{
  "memory_id": "mem_a83f120e",
  "fact": "Operator prefers dark theme across all editors",
  "source": "conversation",
  "confidence": 0.95,
  "sensitivity": "LOW",
  "created_at": "2026-09-24T16:00:00Z",
  "updated_at": "2026-09-24T16:00:00Z",
  "expiration": null,
  "user_confirmed": true
}
```

- **GDPR Compliance:** Users can request a complete transparency report (`GET /api/v1/memory/transparency`) or trigger atomic memory deletion (`DELETE /api/v1/memory/{id}`).
