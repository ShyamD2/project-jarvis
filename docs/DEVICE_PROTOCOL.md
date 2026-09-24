# Node Mesh Protocol & Geolocation Privacy

## Overview
Project J.A.R.V.I.S. coordinates a multi-node mesh uniting desktop workstations, mobile phones (Telegram / Web Trackpad), Raspberry Pi edge hubs, and ESP32 microcontroller endpoints.

The communication fabric is implemented in `devices/node_mesh.py` and provides zero-configuration discovery, capability negotiation, and strict privacy controls.

---

## 📡 Node Mesh Architecture

```
                    ┌─────────────────────────┐
                    │      MASTER NODE        │
                    │   (Desktop Workstation) │
                    └───────────┬─────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MOBILE NODE   │    │    EDGE HUB     │    │   MICRO NODES   │
│ iOS / Android   │    │ Raspberry Pi 4  │    │ ESP32 IoT Nodes │
│ Telegram/Remote │    │ Zigbee/Thread   │    │ Relays & Sensors│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 1. Device Capabilities
Each node advertises a set of capability flags upon registration:
- `AUDIO_INPUT` / `AUDIO_OUTPUT`: Microphones, speakers, soundboard sinks.
- `DISPLAY` / `VISION`: Screen capture, camera streams.
- `INPUT_EMULATION`: Keyboard, mouse, touch injection.
- `ACTUATOR`: Relays, smart plugs, physical switches.
- `TELEMETRY`: Battery vitals, Wi-Fi signal, system load.

### 2. Heartbeat & Liveness Monitoring
Nodes exchange keep-alive heartbeats every 15 seconds. If a node fails to report within a 60-second window, it is marked as `OFFLINE` and its capabilities are routed to local fallbacks.

---

## 📍 Geolocation Privacy Controls

Mobile devices and edge nodes frequently have access to GPS and location sensors. To prevent unsolicited surveillance and protect operator privacy, J.A.R.V.I.S. enforces strict location privacy policies:

### 1. Location Precision Enums
```python
class LocationPrecision(str, Enum):
    NEVER = "never"               # Coordinates are permanently zeroed/stripped
    WHILE_ACTIVE = "while_active" # Location only shared while user actively interacts
    APPROXIMATE = "approximate"   # Coarsened to ~11km (0.1 degree resolution)
    PRECISE = "precise"           # Full GPS resolution (requires explicit opt-in)
```

### 2. Privacy Guarantees
- **Opt-In Default:** `location_enabled = False` is the immutable system default.
- **Sanitization Pipeline:** When telemetry is broadcast or stored, `node_mesh.sanitize_location()` scrubs or coarsens coordinates according to the node's configured precision policy.
- **Approximate Coarsening:** Under `APPROXIMATE` mode, latitude and longitude coordinates are rounded to 1 decimal place (~11 km radius), preventing pinpoint tracking.
- **Command Dispatch Privacy:** Node actions querying location verify that the target node has granted permission before relaying coordinate payloads.
