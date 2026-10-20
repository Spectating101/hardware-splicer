# External-source engineering pilot (2026-10-20)

This pilot is **not** a physical hardware validation or an AI generalization
claim. Three newly authored scenarios draw limited, documented facts from
public vendor guidance while leaving controller identity, measured motor
current, and actual belt tension unknown.

## Cases and official references

- `public_bme280_sensor_unknown_bus.json`: [SparkFun BME280 Qwiic guide](https://learn.sparkfun.com/tutorials/qwiic-atmospheric-sensor-bme280-hookup-guide/all)
- `public_drv8833_donor_motion_repair.json`: [Adafruit DRV8833 guide](https://learn.adafruit.com/adafruit-drv8833-dc-stepper-motor-driver-breakout-board?view=all)
- `public_prusa_belt_shift_diagnosis.json`: [Prusa belt tension guidance](https://help.prusa3d.com/glossary/belt-tension_1597)

Public vendor URLs are citation leads, not a full snapshot with license,
revision, extraction checksum or a validated answer key. The scenarios are
newly constructed engineering questions and are not vendor-certified cases.

## Reproduce

From the repository root, using project dependencies:

```bash
.venv/bin/python scripts/run_source_agnostic_pilot.py /tmp/hardware_splicer_pilot_results.json
```

The runner pins offline salvage, disables live vision, fixes Python hash seed,
records scenario SHA256 hashes, and writes complete dimension-level results.
Outputs go to a temporary file, not a checked-in score. The manifest records
the Git HEAD at runtime; uncommitted changes require separate inspection.

## Initial benchmark at development branch

| Case | Score | Verdict |
| --- | ---: | --- |
| BME280 unknown bus | 48 | reference_and_gap_triage |
| DRV8833 salvage | 70 | structured_project_assistant |
| Prusa belt shift | 70 | structured_project_assistant |

All three pass their external source objects into planner intake, but the
returned plans do not retain source identity/provenance. The benchmark does
not award credit simply for echoes of source data on intake. It also does
not test live document ingestion, hidden ground truth, measured performance,
or actual hardware safety.

## Next benchmark improvements

1. Give the planner a reviewed, typed source register with claim-level
   provenance and conflict dispositions, preserving source authority ceilings.
2. Require stable component/interface identity through revisions.
3. Build a larger held-out set with real source snapshots and separately
   reviewed expected engineering invariants, not model-authored solutions.
4. Score correctness of specific electrical/mechanical recommendations and
   safe abstention, not merely presence of structural JSON keys.
