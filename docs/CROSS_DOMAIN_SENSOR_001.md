# Cross-domain proof 001 — ESP32 + BME280 + printable enclosure proposal

**Goal:** stop testing each HS subsystem in isolation. Test whether one identical input specification can drive an electrical wiring plan, a firmware application source bundle, and a mechanical enclosure CAD model, and preserve a checkable dependency/provenance receipt.

## Actual flow

```text
Existing source-of-truth device spec (ESP32 DevKitC V4 + BME280 on I2C)
  ├─ hardware_splicer.device_plan.build_device_plan → DEVICE_PLAN.json
  ├─ hardware_splicer.device_application.build_device_application
  │     → FIRMWARE_SOURCE.zip (main.cpp, Arduino/PlatformIO manifest, host harness)
  └─ Mecha Splicer EnclosureSpec + generate_enclosure_scad
        → ENCLOSURE_INPUT.json + enclosure.scad
  └─ SHA256 receipts for all outputs + zero physical authority
```

This runs **real existing HS and Mecha Splicer Python generators**, not static placeholder output, and generates new source files for every invocation. The model is an **existing catalog ESP32 board and breakout**, not a new electronics PCB, and the design remains a proposal.

The bridge reuses the existing device planner's case dimensions with explicit coordinate conversion: HS device axes `x` longitudinal, `z` lateral, `y` vertical → Mecha CAD `x` width, `y` depth, `z` height. USB cutout is transferred only if it fits the declared case envelope; if not, all CAD output is refused. Display is omitted for v0 because the existing Mecha enclosure generator lacks a matching parametric lid window.

## Run

```bash
pip install -e '.[dev]'
python scripts/generate_cross_domain_sensor_001.py --output /tmp/hs-sensor-001
pytest -q tests/test_cross_domain_sensor_001.py
```

Review `DEVICE_SPEC.json`, `DEVICE_PLAN.json`, `FIRMWARE_SOURCE.zip`, `ENCLOSURE_INPUT.json`, `enclosure.scad`, `VENTILATION_PLAN.json`, and `CROSS_DOMAIN_RECEIPT.json`.

The generator resolves the local `apps/mecha-splicer/src` monorepo package directly; it does not require an external agent, printer, CAD license, network call or model API. For optional independent mesh rendering, use installed OpenSCAD manually and keep its success separate from geometric/manufacturing verification.

## Current acceptance thresholds

- All three outputs must be derived from a single exact JSON device specification.
- Firmware ZIP internal `DEVICE_SPEC.json` and `DEVICE_PLAN.json` must match the source spec and freshly generated plan.
- Revisions to the spec must yield fresh digests for dependent outputs.
- Unsupported wiring and out-of-bounds USB cutouts must fail rather than produce an authoritative looking assembly.
- Software-only output must never authorize a print, firmware flash, electrical power-on or claimed working device.

## Expected hard blockers after v0

- **Mechanical:** a four-slot sensor-facing lid ventilation pattern is now derived from the sourced BME280 module placement. It is checked against catalog module footprints and can be independently tested for material removal in the OpenSCAD mesh. Airflow effectiveness remains unmeasured. No measured purchased-module envelope, structural retention, verified mounting holes, antenna keepout validation, actual STL slicing, or physical fit test. SCAD and STL remain design proposals.
- **Electrical:** uses catalog ESP32 plus BME280 jumper wires, not a newly authored KiCad schematic/PCB. Sensor electrical compatibility and supply not physically tested.
- **Firmware:** host-testable *source proposal*, not an executed compiler/test or flashed board. Hardware bus timing, real sensor behavior and pinouts are not physically verified.
- **Physical:** no printer or real circuit contacted, no bench data or evidence of a finished device.

Even if CI passes, this milestone is **cross-domain source artifact cohesion**, not autonomous hardware manufacturing.

## Next test, only after basic CI

1. Compile generated firmware using pinned PlatformIO + host harness and capture the exact job logs.
2. Render the generated enclosure through OpenSCAD; run independent manifold, dimensions and USB-access validation.
3. Stress test source changes: swap GPIO pins, PCB dimension overrides, sensor module revisions and casing clearance; detect and fail on inconsistent revision/manufacturing profile.
4. Compare generated geometry against another real CAD backend (text-to-cad, FreeCAD or build123d) on the exact same input/output acceptance rules.
5. Only then integrate further EDA CAD authoring or a device HIL, with physical operator approval.

## Revision: sensor-facing lid ventilation and component envelope consistency

`VENTILATION_PLAN.json` now carries the same-spec board envelope projection into the physical case coordinate frame (x = board length, y = board width, z = vertical height). The builder requires non-overlapping declared PCB footprints and enclosure bounds. It locates **four 8 × 1.2 mm lid slots**, all within the declared BME280 breakout footprint and away from other declared board footprints.

The OpenSCAD source retains the original Mecha-generated base and lid, wraps the lid in a subtractive ventilation model, and renders `vented_lid()` rather than the blank slab. CI computes the base and lid STL meshes using actual OpenSCAD and compares the vented lid volume against a separately rendered unvented lid. The nominal removed vent volume at 2 mm lid thickness is **76.8 mm³**; this must be confirmed by the current CI output rather than presumed.

The derived envelopes are based on the parts catalog (and any explicit user overrides), **not** caliper measurements. Existing GPIO wiring and firmware status do not become physically proven by this change. The ventilation slots cannot be used to claim measured BME280 ambient response or thermal isolation. Mechanical retention and support are still absent, so do **not** treat the lid as snap-fitted or mechanically secured.

A selected real printer/material profile, prototype measurement and physical airflow/temperature-humidity response testing remain explicit acceptance gates.
