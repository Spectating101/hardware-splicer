# Drone cross-design splice trial: evidence and compatibility

This trial tests a different capability from assembling an X500 reference kit: can HS **replace one design's part with another project's part** while preserving engineering constraints? Source data combines Holybro X500 reference roles, an actual cloned `DroneSkeleton` S500 geometry repo, and the cloned `DroneControllerUsing-STM32` PCB/firmware project. Salvaged ESC and anonymous propeller fixtures demonstrate how missing donor evidence is handled.

## Results

| Proposed donor | Assessment | Why | What physical design work is still necessary |
| --- | --- | --- | --- |
| [DroneSkeleton S500 frame](https://github.com/colgecen/DroneSkeleton) | Redesign required; not a drop-in X500 V2 frame | Different frame family; motor hole spacing, flight-controller mounting, propeller clearance and mass envelope not measured or checked | Extract dimensions from source CAD, design FC/power-module brackets, run interference/stress/mass checks |
| [Custom STM32 flight controller](https://github.com/IoT-App-Development-Company/DroneControllerUsing-STM32) | Redesign required; not a drop-in Pixhawk 6C | Different MCU/controller platform and unresolved firmware, signal, voltage, GPS and mounting interfaces | Verify KiCad schematic/ERC/DRC, pinouts, firmware and flight-control ecosystem; redesign harness and revalidate configuration |
| Unknown salvaged ESC | Adaptation or evidence gathering required | No certified current/voltage/protocol/connector/thermal data | Identify precise part; obtain datasheet or characterize under separately authorized conditions; validate four-channel compatibility |
| Unidentified nominal 1045 propeller | Adaptation or evidence gathering required | Nominal size alone doesn't establish shaft, rotation direction, rpm rating or thrust curves | Identify and verify full propeller specs and motor/prop coupling |

The findings establish *why a swap is not yet acceptable*, not that it cannot eventually work. A source mismatch with the reference configuration means **redesign, not categorical physical impossibility**. The existing rule engine compares only declared fields; it does not yet parse actual CAD dimensions or netlist semantics, automatically design a mechanical adapter, choose concrete donor wiring, or perform flight simulation. None of these candidates is approved for physical installation.

## Run

```bash
PYTHONPATH=src .venv/bin/python scripts/run_drone_splicing.py
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_drone_splicing.py
```

`alternates.json` has explicit donor identities, claims, evidence locators and unresolved mating-interface attributes; `splice_assessment.json` is the generated comparison. The next **real splicing milestone** is dimension-driven S500-to-Pixhawk adapter CAD output, accompanied by geometry checks and a component-specific pinout/wiring map. A successful reference-kit assembler does not satisfy this requirement.
