# Mechatronics Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the salvage loop so each money path emits electrical + mechanical pack + pin-true firmware under one offline bar, with UI surfacing and a pan-tilt golden.

**Architecture:** New `mechanism_bridge` maps salvage roles/PCB envelope → mecha-splicer `ProjectSpec` and runs offline. Extend `firmware_scaffold` for relay/fume/pan-tilt. Wire both into salvage package emission. `verify_mechatronics_paths` extends the money bar. Splice-UI reads package artifacts.

**Tech Stack:** Python (hardware_splicer, mecha-splicer), Make, React/Vite splice-ui, pytest/vitest

**Spec:** [`../specs/2026-07-18-mechatronics-engine-design.md`](../specs/2026-07-18-mechatronics-engine-design.md)

---

## File map

| File | Responsibility |
|------|----------------|
| `src/hardware_splicer/mechanism_bridge.py` | Role→mechanism ProjectSpec + run mecha-splicer offline |
| `src/hardware_splicer/salvage_bridge.py` | Attach mechanism_pack + authority to package |
| `src/hardware_splicer/firmware_scaffold.py` | Relay/fume/pan-tilt sketches + pin extract |
| `scripts/verify_mechatronics_paths.py` | Offline 8-path elec+mech+fw bar |
| `scripts/verify_mechatronics_golden.py` | Pan-tilt closed golden |
| `examples/money_paths/manifest.json` | Per-path mechatronics requirements |
| `Makefile` | `verify-mechatronics-paths`, `verify-mechatronics-golden` |
| `apps/splice-ui/...` | Mechatronics panel + stage gating |
| `tests/test_mechanism_bridge.py` | Unit tests |
| `docs/PROGRESSION_STATUS.md` | Scoreboard |

---

### Task 1: mechanism_bridge (core)

**Files:**
- Create: `src/hardware_splicer/mechanism_bridge.py`
- Create: `tests/test_mechanism_bridge.py`

- [ ] **Step 1:** Unit test: pan_tilt roles → ProjectSpec with `pan_tilt` key; enclosure-only for sensor_logger
- [ ] **Step 2:** Implement `select_mechanism_kind`, `build_mecha_project_spec`, `run_mechanism_pack` (in-process mecha runner; degrade on ImportError)
- [ ] **Step 3:** pytest green

### Task 2: Wire into salvage_bridge

**Files:**
- Modify: `src/hardware_splicer/salvage_bridge.py`

- [ ] **Step 1:** After firmware_scaffold, call `run_mechanism_pack` and `build_mechatronics_authority`
- [ ] **Step 2:** Persist `mechanism_pack`, write `MECHATRONICS_PACK.json` / authority JSON into out_dir when available
- [ ] **Step 3:** Ensure money-path verify still 8/8

### Task 3: Firmware sketches

**Files:**
- Modify: `src/hardware_splicer/firmware_scaffold.py`
- Modify: `tests/test_firmware_scaffold.py`

- [ ] **Step 1:** Tests for relay, fume, dual-servo pin emission
- [ ] **Step 2:** Implement sketches + bring-up pin keys (`relay`, `fan`, `servo_pan`, `servo_tilt`)
- [ ] **Step 3:** pytest green

### Task 4: Mechatronics path verifier

**Files:**
- Create: `scripts/verify_mechatronics_paths.py`
- Modify: `examples/money_paths/manifest.json`
- Modify: `Makefile`

- [ ] **Step 1:** Extend manifest with require_firmware / require_mechanism / mechanism_kinds_any
- [ ] **Step 2:** Verifier reuses money checks + FW/mech/authority
- [ ] **Step 3:** Drive to 8/8 offline; `make verify-mechatronics-paths`

### Task 5: Golden pan-tilt

**Files:**
- Create: `scripts/verify_mechatronics_golden.py`
- Modify: `Makefile`

- [ ] **Step 1:** Run pan_tilt money intake; assert dual servo FW + pan_tilt mech + authority file
- [ ] **Step 2:** `make verify-mechatronics-golden` PASS

### Task 6: Splice-UI Mechatronics panel

**Files:**
- Modify: `apps/splice-ui/src/projectSession/projectSession.js` (optional stage or verify subsection)
- Create: `apps/splice-ui/src/components/MechatronicsPanel.jsx`
- Modify: `ProjectWorkspace.jsx` / package handoff
- Tests: panel + availability

- [ ] **Step 1:** Panel renders firmware + mechanism + authority from package fixture
- [ ] **Step 2:** Wire into Verify or Package stage
- [ ] **Step 3:** vitest green

### Task 7: Progression status

**Files:**
- Modify: `docs/PROGRESSION_STATUS.md`
- Modify: spec status → APPROVED/IMPLEMENTED

- [ ] **Step 1:** Scoreboard for mechatronics 8/8 + golden + UI
- [ ] **Step 2:** Next actions updated

---

## Verification commands

```bash
cd Hardware-Splicer
PYTHONPATH=src pytest tests/test_mechanism_bridge.py tests/test_firmware_scaffold.py -q
make verify-money-paths
make verify-mechatronics-paths
make verify-mechatronics-golden
cd apps/splice-ui && npm test -- --run
```
