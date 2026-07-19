# Mechatronics Engine — Design Spec

**Date:** 2026-07-18  
**Status:** IMPLEMENTED — `make verify-mechatronics-paths` 8/8 + golden PASS (2026-07-18)  
**Scope:** Push A + B + C (money-path mechatronics bar, closed golden loop, splice-ui surface)  
**Doctrine:** Intent-first junk→intent DIY; offline-first; honesty over theater; invites stay paused

## Problem

Electronics money paths are **8/8** at Enabot honesty/compile. Mechanical (`mecha-splicer`, `3d-splicer`) and firmware (`firmware_scaffold`) already exist as **parallel stacks**, plus authority ledgers (`mechanical_authority`, `mechatronics_authority`). They are not one product loop: salvage → carrier + mounts/enclosure + pin-true firmware under one offline bar.

## Goal

Make Hardware-Splicer a **mechatronics engine**: one intake yields three synchronized artifacts with honest claim boundaries:

1. **Electrical** — resolved modules, topology, DRC-clean carrier (existing money-path bar)
2. **Mechanical** — mechanism pack (OpenSCAD / optional STL) derived from build roles + PCB envelope
3. **Software** — pin-mapped firmware sketch from bring-up / graph, not generic heartbeat theater

Success = `make verify-mechatronics-paths` **8/8** + closed pan-tilt golden PASS + UI stage showing the triple pack.

## Non-goals (this phase)

- Full FEA / production mold tooling
- Flashing boards or OTA fleets
- Partner invites / marketing (still paused)
- Replacing KiCad with a new EDA
- Inventing a second catalog parallel to existing build_ids

## Architecture

```text
intake JSON
    │
    ▼
salvage_bridge / splice_and_build_from_intake
    │
    ├─► electrical package (resolved_modules, bringup, carrier)     [exists]
    │
    ├─► mechanism_bridge  ──► mecha-splicer ProjectSpec ──► bundle  [NEW glue]
    │         ▲                    (runner.run, offline SCAD)
    │         └── roles, pcb bbox, mounts, ports from salvage/compile
    │
    └─► firmware_scaffold (extended sketches) ──► .ino / .py         [EXTEND]
              ▲
              └── gpio_assignments + graph pin map

artifacts/ + MECHATRONICS_PACK.json
    │
    ▼
verify_mechatronics_paths.py  (extends money bar)
    │
    ▼
splice-ui Mechatronics panel (read artifacts; no second compile path)
```

### Key seam: `mechanism_bridge`

New module `src/hardware_splicer/mechanism_bridge.py`:

- Input: salvage package + optional compile PCB envelope (`pcb_w_mm`, `pcb_h_mm`, mounts, ports)
- Output: `mecha_splicer` `ProjectSpec` dict + call into `mecha_splicer.runner.run` (in-process or subprocess with `PYTHONPATH=apps/mecha-splicer/src`)
- Mechanism selection from roles/build_id (deterministic table, not LLM):

| Signal | Mechanism |
|--------|-----------|
| `svo`×2 or pan_tilt / inspection_motion | `pan_tilt` |
| dual `mot` + drive / robot_drive | `drive_base` + enclosure |
| `load` pump / plant / fume | enclosure (+ fan bracket if fume) |
| relay / smart_relay | enclosure (DIN-ish box, cutouts) |
| sensor_logger | enclosure (sensor port cutouts) |
| plotter / steppers | `linear_axis` (starter) + enclosure |
| unknown | enclosure-only from PCB envelope; claim boundary notes limited mech |

- Always emit `MECH_CHECK.md`, `PARTS.json`, SCAD sources when mecha-splicer succeeds
- On mecha failure: **honest skip** with `mechanism.status=degraded` and reason — electrical path must not regress
- Optional `3d-splicer` STL only when CadQuery env available; never hard-fail offline bar on missing CadQuery

### Firmware extension

Extend `firmware_scaffold.py` with real bring-up pin sketches for:

- `smart_relay_box` / relay GPIO
- `usb_fume_extractor` / MOSFET or PWM fan
- `inspection_motion_fixture` / dual SG90 (ESP32Servo or LEDC PWM)
- Strengthen generic path: if bring-up has named purposes (`relay`, `servo`, `fan`), emit those pins even without catalog build_id

Verifier checks:

- `firmware_scaffold.source` non-empty
- `pins` non-empty when actuators/sensors present (path-specific)
- Sketch references extracted pin numbers (string contains), not only defaults

### Authority

After mech + firmware attach:

- Call existing `build_mechanical_authority` / `build_mechatronics_authority` on the package
- Persist `MECHATRONICS_AUTHORITY.json` in out_dir
- Money/mechatronics verify: require `current_authority_level` ≥ `mechanical_robotics_authority` **or** documented `electrical_only` exception for paths with no motion (sensor_logger may be packaging_authority)

Honest levels beat fake production_authorized.

## Track A — Offline mechatronics bar (8 paths)

**Manifest:** extend `examples/money_paths/manifest.json` with per-path:

```json
{
  "require_firmware": true,
  "require_mechanism": true,
  "mechanism_kinds_any": ["pan_tilt", "enclosure", "drive_base"],
  "min_firmware_pins": 1,
  "min_authority_level": "mechanical_robotics_authority"
}
```

**Script:** `scripts/verify_mechatronics_paths.py`  
- Reuse money-path electrical checks  
- Plus firmware + mechanism + authority checks  
- Offline env identical to `verify_money_paths`

**Make:** `verify-mechatronics-paths`  
**Target:** 8/8 PASS offline without Qwen/CadQuery requirement (SCAD + FW sufficient)

## Track B — Closed golden loop

Promote `examples/scenarios/closed_pan_tilt_mechatronics_project.json` into the same salvage→pack path used by money `pan_tilt`:

1. Run money pan_tilt intake through new bridge (not only compile_casefile demo)
2. Assert mecha bundle has pan_tilt primitives (`pt_*.scad` or parts list)
3. Assert dual-servo firmware pins match bring-up
4. Assert `MECHATRONICS_AUTHORITY.json` present
5. Keep existing closed demo as regression if still used by `compile_casefile`

**Script:** `scripts/verify_mechatronics_golden.py` (or flag on mechatronics verify `--golden pan_tilt`)  
**Make:** `verify-mechatronics-golden`

## Track C — Splice-UI surface

Do **not** invent a parallel compile. Surface artifacts from salvage/build package:

1. New workspace stage or Verify subsection: **Mechatronics**
2. Panels:
   - Firmware: filename, pin table, download `.ino`
   - Mechanism: kind, PARTS summary, links to SCAD / MECH_CHECK
   - Authority: level + claim_boundary (read-only)
3. Gate: available when `sessionHasPackage` and package contains `firmware_scaffold` or `mechanism_pack`
4. Tests: stage availability + panel renders fixture package

Keep invites paused; UI copy must not claim production release unless authority says so.

## Implementation order

1. `mechanism_bridge` + wire into `salvage_bridge` / splice package emission  
2. Firmware sketches for relay / fume / pan-tilt + pin extraction  
3. `verify_mechatronics_paths` + Makefile; drive to 8/8  
4. Golden pan-tilt closed-loop verify  
5. UI Mechatronics panel + tests  
6. Update `PROGRESSION_STATUS.md` scoreboard  

## Acceptance criteria

| # | Criterion |
|---|-----------|
| 1 | `make verify-money-paths` still 8/8 (no electrical regression) |
| 2 | `make verify-mechatronics-paths` 8/8 offline |
| 3 | Each path out_dir has `firmware_scaffold` artifact + mechanism pack or honest degraded reason |
| 4 | Pan-tilt golden: dual servo FW pins + pan_tilt mech primitives |
| 5 | Splice-UI shows Mechatronics panel from package fixtures (unit/integration tests green) |
| 6 | Progression doc lists mechatronics scoreboard; invites remain paused |

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| mecha-splicer heavy / flaky | Prefer in-process starter fidelity; cache template SCAD; degrade honestly |
| CadQuery missing | Never require STL for offline bar |
| Catalog parity (TS plan-to-graph) | New build_ids avoided; bridge uses existing roles |
| Authority theater | Cap claims; forbid production_authorized without real sim/bench evidence |
| UI scope creep | Read-only artifact panel; no new job type |

## Open decisions (defaults if approved as-is)

1. Mechanism run **in-process** via mecha-splicer Python path (not HTTP API) for offline verify  
2. sensor_logger / smart_relay: enclosure-only is enough for `require_mechanism`  
3. STL / CadQuery is **bonus**, not bar  
4. Commit design after founder ack; implement in one branch without partner messaging  

## Approval

Reply **go** (or edit this file) to proceed to implementation plan + execution of tracks A→B→C.
