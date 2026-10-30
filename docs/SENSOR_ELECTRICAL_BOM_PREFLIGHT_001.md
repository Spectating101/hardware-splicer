# ESP32 Sensor 001 — electrical interface and BOM qualification preflight

**Purpose:** close the *symbolic* electrical/interface and component-provenance gap in the existing first HS acceptance benchmark, without claiming native PCB design or a physical pass.

## Inputs and source authority

- `DEVICE_SPEC.json` and `DEVICE_PLAN.json`, from the existing HS module planner.
- Actual `FIRMWARE_SOURCE.zip` with source `src/main.cpp`, `FIRMWARE_PROPOSAL.json`, and `PART_DESCRIPTOR.json`.
- Exact generated source/plan digest in `CROSS_DOMAIN_RECEIPT.json`.
- Existing versioned HS `device_modules.json` catalog with linked Espressif, Adafruit and Bosch sources.

## Independent new checks

`sensor_electrical_preflight.py` independently rebuilds the device plan from the source spec; confirms exactly four known wires and their pin identity; verifies the sensor Vin is attached to ESP32 3V3 (never 5V), sensor GND to controller ground, and SCK/SDI to GPIO22/21. It resolves the I2C bus using the existing HS graph logic. It then inspects the **generated C++ main.cpp** and ZIP-embedded firmware proposal, confirming the numeric pins in actual source agree with the electrical plan, and confirms the exact sensor part descriptor and ZIP source digest.

Adversarial tests corrupt firmware GPIO constants, firmware proposal pin metadata, catalog identity and supply wiring. Altered ZIP/receipt fields do not silently override expected source facts.

The deterministic `BOM_PROVENANCE.json` records the two catalog module names, source URLs and quantity, plus jumper wires and USB cable. Every item remains **UNQUALIFIED**. There is no invented supplier price, stock count, complete purchase order, actual voltage-level assessment, measured current, or fake proof of the exact board revision. ESP32 board sources and Adafruit BME280 product references are traceable in the existing catalog, but sourcing status is not a pass.

## Native CI and combined acceptance

The OpenSCAD geometry CI job now runs `pytest -q tests/test_sensor_electrical_preflight.py` plus the independent preflight CLI on the exact package it generated, and retains `ELECTRICAL_PREFLIGHT.json` and `BOM_PROVENANCE.json`. The downstream same-run acceptance job checks their source/firmware link and refusal flags alongside actual STL, OpenSCAD, ELF, BIN, and platform build logs; the Atlas capability manifest now reports `catalog_traced_unqualified` rather than silently implying parts are qualified.

```bash
python scripts/generate_cross_domain_sensor_001.py --output /tmp/hs-sensor-001
python scripts/verify_sensor_electrical_preflight_001.py --project /tmp/hs-sensor-001
pytest -q tests/test_sensor_electrical_preflight.py tests/test_engineering_acceptance_sensor.py
```

## Limits and forward gate

The pass state is *symbolic-catalog wiring and generated firmware pin coherence*. It is **not** native KiCad ERC/DRC, a schematic, PCB, measured BME280 Vin/SCL/SDA logic-level integrity, verified pull-up topology, power delivery, physical installation, a sourced qualified BOM, or manufacture approval.

Native electronics should be the **next separate engineering challenge**: use version-pinned KiCad/atopile/tscircuit to author a new, explicitly specified real schematic/board and require real ERC/DRC/BOM/footprint checks. Do not retrofit this four-jumper assembly to masquerade as a manufactured PCB.

## Out-of-scope unrelated CI

Some runs on the predecessor PR #232 have a red `Device Plan Deliverables` browser workflow because Playwright 1.55.0 does not support Chromium installation on `ubuntu26.04-x64`, while the native engineering acceptance workflow passes. This should be repaired as a **separate CI infrastructure change**, not weakened or misrepresented as an engineering failure.
