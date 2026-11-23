# HS universal manufacturing interface — first implementation (2026-10-27)

## Product contract

**User-facing goal:** connect a desktop manufacturing workstation; HS determines
which controlled machines are available, what each can demonstrably do, and how
to prepare the right file/operation. The user does **not** have to choose a
printer manufacturer or learn API syntax.

**Engineering reality:** "any printer" cannot be achieved with one universal
transport. It requires interchangeable protocol drivers and strict refusal
when a specific machine, firmware, toolpath or action is unsupported. Device
onboarding is local/operator controlled. This implementation does not scan
untrusted networks or invent endpoints.

## Implementation

- `fleet.py`: common `MachineCapabilities`, `MachineObservation`,
  `ManufacturingRequest`, `ManufacturingPlan`, and `ManufacturingFleet`.
  Devices are locally enrolled by ID. The fleet reads machine status and routes
  an artifact to one *verified, idle, compatible* controller. Multiple matches
  require selection. No operations start a machine.
- `discovery.py`: read-only protocol detection against **operator-enrolled
  local IPs**, with fail-closed support for OctoPrint and Moonraker signatures.
  A protocol handshake proves which API is responding; it does **not**
  cryptographically authenticate physical printer make, serial or condition.
- `moonraker.py`: additional status driver for Klipper/Moonraker via
  `GET /server/info` and `GET /printer/objects/query?print_stats`, with
  conservative normalization to idle / printing / paused / error / offline /
  unknown. Read-only in this iteration.
- Existing `octoprint.py`: status, monitoring, locally confirmed G-code
  staging; no start-print API or general motion/heater controls.
- Existing `cad_pipeline.py`: OpenSCAD mesh generation and profile-based
  PrusaSlicer toolpath generation, without asserting slicer or G-code safety.

Provider behaviors differ even among supported controllers. In particular,
OctoPrint plugins can automate actions at upload time and machine control
must remain guarded by separate local approvals.

## Current compatibility matrix

| Controller / workflow | Status | Monitor | Stage file | Start print |
| --- | --- | --- | --- | --- |
| OctoPrint local REST | Coded | Coded | Locally gated in v0 | No |
| Moonraker/Klipper REST | Coded | Status normalization | No | No |
| PrusaLink local | Not yet implemented | Not yet | No | No |
| Bambu LAN modes | Not yet implemented | Not yet | No | No |
| Resin vendors, CNC, laser, robot | Not yet implemented | Not yet | No | No |

The CLI and low-level adapters from PR #225 are retained; these new classes
are an orchestration layer rather than a replacement.

## Example without knowing manufacturer

```python
from hardware_splicer.manufacturing_operator import (
    ManufacturingFleet, ManufacturingRequest, connect_enrolled_controller,
)

# This endpoint is entered or approved in a trusted local machine setup UI.
driver = connect_enrolled_controller(
    base_url="http://192.168.1.25:7125",
    api_key=None,  # obtain an API key locally when required
)
fleet = ManufacturingFleet()
fleet.enroll("workshop-machine-1", driver)
observation = fleet.inspect("workshop-machine-1")
plan = fleet.plan(ManufacturingRequest(
    machine_type="fdm", artifact_suffix=".gcode", need_monitoring=True))
assert not plan.start_authorized
# Close the driver when done: Moonraker uses driver.close();
# OctoPrint wraps an existing client, via driver.client.close().
```

This creates only a **candidate plan**. It does not upload or start a print.
Machine discovery from IP subnets, physical identity attestation, encrypted
local device enrollment, and unattended autonomous starting remain absent.

## 3D generation is a separate plug-in surface

The manufacturer-neutral controller must **not** decide which CAD engine to
use. Treat the front-end 3D stack as replaceable and improving independently:

- Parametric CAD inputs (e.g. CadQuery, OpenSCAD, FreeCAD): editable parts.
- Mesh/geometry processing (existing 3D Splicer): repair, decomposition,
  dimensional inspection and export; independent manifold validation needed.
- Mechanical and physical constraints (existing Mecha Splicer): joints,
  mounting, fits, strength/material/thermal constraints.
- Different process preparation: FDM slicing, resin preparation, machining
  CAM, robotic motion planning — **not interchangeable G-code**.
- Device capability negotiation: supported materials, build volume, toolhead,
  nozzle, firmware, thermals and maintenance state must be observed or
  operator-verified. Unknown dimensions and materials are not evidence of fit.
- Runtime control: prepare → validate → locally approve → execute →
  monitor → recover → independently inspect resulting part.

This separates fast-moving CAD/AI tools from machine drivers. Better text-to-3D
or parametric generation should be pluggable without rewriting print control.

## Verification and authority

Mocked tests challenge two distinct protocol handshakes, unknown endpoints,
unsupported formats, busy/offline machines, ambiguous fleet choices and
missing staging privileges. **These tests have been written but not confirmed
passing on a local device or CI in this change.**

No real printer or manufacturing equipment has been contacted from this task.
No fabricated part has been measured. No machine is authorized to print,
move, heat, machine, laser-cut, handle chemicals or operate unattended.

## Next required gates

1. Run tests, fix static/runtime issues and evaluate supported platform
   versions under realistic network/auth configurations.
2. Implement locally approved enrollment and discovery (e.g. mDNS for
   explicitly authorized LAN services) with identity binding, no blind scans.
3. Add device-specific materials, physical build volumes, profile mapping,
   printer state and slicer metadata with conservative capability predicates.
4. Implement a host-controlled one-time print authorization bound to exact
   toolpath hash, machine identity and expiry, with independent interlocks.
5. Demonstrate on an actual printer with operator supervision and a
   **non-load-bearing test part**; record status, failures and dimensional
   verification. Extend drivers based on observed demand, not guesses.

Documentation sources:
- https://docs.octoprint.org/en/main/api/
- https://moonraker.readthedocs.io/en/latest/external_api/
- https://help.prusa3d.com/article/prusa-connect-and-prusalink-explained_302608
- https://blog.bambulab.com/updates-and-third-party-integration-with-bambu-connect/
