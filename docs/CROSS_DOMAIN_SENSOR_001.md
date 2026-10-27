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

Review `DEVICE_SPEC.json`, `DEVICE_PLAN.json`, `FIRMWARE_SOURCE.zip`, `ENCLOSURE_INPUT.json`, `enclosure.scad`, and `CROSS_DOMAIN_RECEIPT.json`.

The generator resolves the local `apps/mecha-splicer/src` monorepo package directly; it does not require an external agent, printer, CAD license, network call or model API. For optional independent mesh rendering, use installed OpenSCAD manually and keep its success separate from geometric/manufacturing verification.

## Current acceptance thresholds

- All three outputs must be derived from a single exact JSON device specification.
- Firmware ZIP internal `DEVICE_SPEC.json` and `DEVICE_PLAN.json` must match the source spec and freshly generated plan.
- Revisions to the spec must yield fresh digests for dependent outputs.
- Unsupported wiring and out-of-bounds USB cutouts must fail rather than produce an authoritative looking assembly.
- Software-only output must never authorize a print, firmware flash, electrical power-on or claimed working device.

## Expected hard blockers after v0

- **Mechanical:** no measured purchased-module envelope, sensor ventilation geometry, structural retention, verified mounting holes, antenna keepout validation, real STL slicing, manifold or physical fit test. SCAD base and lid are design proposals only.
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
