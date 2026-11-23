# Engineering experiment work-order feasibility (planning only)

This adapter consumes a source-bound `hardware_splicer.experiment_work_order.v1` produced by Policy Lab's experimental investigation adapter and checks which observations the **unbuilt J2 DC station design** could hypothetically support. It is not a device controller, a universal CAD compiler, or a physical-readiness assessor.

## Interface

Run with an actual station design JSON from `python -m hardware_splicer.dc_measurement_cli design --out NEW_DIR` and a separate Policy Lab work order:

```sh
PYTHONPATH=src python -m hardware_splicer.experiment_feasibility \
  --order /path/to/hs-work-order.json \
  --station-design /path/to/station-design.json \
  --out /path/to/new-feasibility.json
```

Exit code `0` means all required **measurement points are in the candidate design**, not that hardware exists. Exit code `2` means the station lacks at least one requested observation. Exit code `1` means a malformed or source-mismatched order, or another execution error.

The only currently designed points are load-side `J2_LOAD/VOLTAGE_V`, `J2_LOAD/CURRENT_A`, and mathematically integrated `J2_LOAD/ENERGY_WH`. The work order may also request `CONVERTER_INPUT/*`, `J2_REFERENCE/CALIBRATION_RECORD` or `CLOCK_REFERENCE/UTC_TIMEBASE_CHECK`, which are recognized but **not** claimed as present in this unbuilt station. The converter efficiency case requires input-side energy and must not be computed from two J2 references.

The order is required to carry the exact SHA-256 of the station-design JSON, an intake evidence-root SHA-256, the original kind `TEST_FIXTURE` or `DECLARED_BENCH_CAPTURE`, and `execution_authorized:false`. The evaluator verifies the design bytes, rejects unknown points and forged readiness labels, and returns a machine-readable instrument-gap report with required follow-up engineering actions.

## Reality boundary

Even if the result says `DESIGN_COVERS_POINTS_UNBUILT_OR_UNVERIFIED`, it **never** authorizes energization, sourcing, soldering, or an engineering revision. The station still needs exact part selection, source/host grounding and isolation review, overcurrent protection, safe mechanical mounting, a genuine independent reference instrument, calibrated uncertainty and separately checked timebases. Source hashes do not authenticate physical origin. An arbitrary number or JSON label cannot override these conditions.

## Verification

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_experiment_feasibility.py -v
```

The companion Policy Lab feature uses this checker in a four-case deterministic replay and a synthetic before/after comparison. See its `docs/equipment-infrastructure/ENGINEERING_INVESTIGATION_V0.md`. That replay is a program-design proof, not an instrument test.

## First real PCB candidate, strictly low power

A separate, [5 V / 0.5 A KiCad witness-fixture design](../hardware/reference_designs/low_voltage_witness_fixture_v0/README.md) now has an editable schematic and PCB, native zero-violation ERC/DRC with schematic parity, a DC SPICE model, actual HS register-decoder fixture replay, and an unchanged PLRS-6 offline intake receipt. It is **UNBUILT_UNVERIFIED**; fabrication and energization are on hold for identified procurement, fuse, isolation, reference-measurement and metrological blockers. It is deliberately **not** a 24 V / 120 W design.
