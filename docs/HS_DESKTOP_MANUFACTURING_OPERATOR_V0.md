# HS Desktop Manufacturing Operator — v0

**Implementation:** `src/hardware_splicer/manufacturing_operator/octoprint.py` + `scripts/hs_octoprint_operator.py`.

This is the first machine-facing HS adapter, not a claim that a device has been operated, or that HS can manufacture a working object. The adapter has been coded against OctoPrint's documented REST API and supplied with offline mock-transport tests. Actual device execution still needs an operator and a connected printer.

## Purpose

A desktop HS application should orchestrate different *independent* engineering and machine subsystems:

1. Intent and component selection: existing `apps/circuit-ai` and core HS synthesis, plus independent datasheet checks.
2. Mechanical design: existing `apps/3d-splicer` and `apps/mecha-splicer`; external CadQuery/OpenSCAD/FreeCAD as applicable.
3. Model verification: explicit CAD validity, dimensional constraints, mesh integrity and print orientation.
4. Slicing: a locally installed slicer with **selected printer/material profile**; machine-specific generated G-code is the submission artifact, not a generic STL.
5. Manufacturing Operator: local printer adapter (OctoPrint implemented here, Moonraker/PrusaLink later), capability discovery, status, upload approval, job monitoring.
6. Physical evidence: machine telemetry, optional optical inspection, human post-processing inspection, dimensional and mechanical checks, hardware repair feedback.

The AI agent can propose plans and request operations; local host policy, printer firmware, interlocks and operator approval decide what can actually execute.

## Supported v0 operations

- `printer_status()`: GET `/api/printer` and fail on malformed responses.
- `current_job()`: GET `/api/job` to monitor.
- `stage_gcode(path)`: POST `/api/files/local` using explicit `select=false`, `print=false`, **only after** the local operator enables upload and confirms auto-start plugins are disabled. Rejects busy/error/paused printers, non-G-code files, invalid size, and missing staging permission. Returns a SHA-256 and status receipt.

No functions perform start, resume, heater adjustment, head movement, raw G-code submission, machine emergency-stop override or firmware changes. Stage does not certify G-code safety: dangerous macros and invalid machine settings remain possible until separately checked. OctoPrint supports extensions that auto-start on upload; even `print=false` cannot universally prevent a plugin from doing so. Never assume an arbitrary printer is safe for unattended uploads.

## Desktop CLI (installed editable, no web service required)

```bash
pip install -e '.[dev]'
export HS_OCTOPRINT_URL=http://192.168.1.50:5000
export HS_OCTOPRINT_API_KEY='local-printer-user-specific-key'

python scripts/hs_octoprint_operator.py --status
python scripts/hs_octoprint_operator.py --job
# In a trusted LOCAL interactive terminal only, with auto-start plugins reviewed:
python scripts/hs_octoprint_operator.py --stage ./approved-slicer-output.gcode

pytest -q tests/test_manufacturing_octoprint_operator.py
```

`HS_OCTOPRINT_API_KEY` must come from the local credential store; never pass it to prompts or commit it. The script only allows `localhost` or a private literal IP on HTTP. Reverse proxy, remote WAN, mDNS and external device services are not part of v0. The interactive TTY text is a *procedural* confirmation, not secure proof of a human if a remote agent controls the terminal. Do not expose `stage_gcode` to an agent tool without an isolated local approval service.

## Planned v1: actually execute a print

The manufacturing operator needs a **different local authority context** from the LLM's tool calls:
- Generate and validate candidate files, using source hashes, slicer identity, printer/material profile, bounding box, time, material estimate and permitted-temperature bounds.
- Present a locally rendered, tamper-evident review of the exact G-code to the machine operator.
- Operator grants one-time authorization bound to the file hash, printer ID and expiry; the agent cannot mint or alter it.
- Recheck machine identity, limits, sensors, enclosure, bed clearance and firmware interlocks immediately before start.
- Send approved OctoPrint/Moonraker print-start command; monitor state/temperatures/filament/camera and notify/pause/cancel when warranted. Keep manual emergency-stop and physical power isolation accessible.
- Record progress, faults, completion and measured output. Never equate "job complete" with "part passed quality control".
- Remain explicit about unattended operation hazards (hot nozzle/bed, electrical fault, fumes, motion/collision, adhesives and print detachment).

The first real-world benchmark should be a **non-load-bearing mechanical bracket or hinge**, not a structural safety-critical item, electrical mains part, battery container or medical component. Operator supervises the first run.

## Provider roadmap

- **OctoPrint:** implemented for read/monitor/stage; actual device test and start authorization not implemented.
- **Moonraker/Klipper:** documented HTTP/WebSocket interfaces; add adapter after OctoPrint tests.
- **PrusaLink:** local Prusa printer interface; needs model-by-model integration.
- **CNC / pick-and-place / laser:** adapter contract and risk-specific policies; do not generalize printer G-code blindly to other machines.
- **PCB fab:** output manufacturing package for a board house is usually the primary path; 3D printers handle housings, fixtures and some mechanical parts, *not* typical commercial PCB fabrication.

No proprietary Blueprint implementation or private API is incorporated or represented as available.
