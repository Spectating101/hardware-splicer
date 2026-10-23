# Repair Challenge 04 — Source-bound electrical observations from KiCad netlists

**Status:** executed digital integration trial; **not** physical measurements, repair success, safe power-on, manufacturer/ERC signoff, or a competitor victory. Date: 2026-10-24.

## Why this matters

Previously, HS's **existing KiCad sexpr netlist importer** appeared to accept `examples/main_ctrl_esp32_servo.net` and produce PCB placement. But it stringified nested `(name ...)`, `(ref ...)`, and `(pin ...)` arrays, so electrical nets carried **zero real pin memberships**. The ensuing "clean" router result tested a mostly empty electrical problem—not the exported circuit. This was a critical failure of external engineering-tool reuse.

The corrected `src/hardware_splicer/netlist/import_kicad.py` reads actual nested KiCad S-expressions. On the **unchanged repository netlist example** the parsed result is:

| Source property | Former parser | Corrected parser |
| --- | ---: | ---: |
| Components | 9 | 9 |
| Net documents | 14 | 14 |
| Real `REF.PIN` memberships | **0** | **40** |
| `J1.1` maps to VBUS; `U3.1` to GND | No | **Yes** |
| PCB router fed original wire connectivity | No | **Yes** |
| Hard copper shorts in resulting in-repo route | Hidden by missing wiring | **2 exposed** |
| Can assert complete board/fabrication readiness | **No**, previous fixture incorrectly treated it as success | **No — DRC blocked** |

Example detected violations from the actual compile: crossing `Net-2` with `Net-11` on F.Cu and crossing `Net-2` with `Net-1` on B.Cu. One separate copper-clearance warning also appears. Internal model quality now records `build_graph_compiled=true`, `wire_count=26`, `electrical_safety_pass=true`, `drc_pass=false`, `fabrication_ready=false`. There is *not* an automatic router repair in this PR. Other originally routing-green fixtures continue to be checked independently.

## Source-bound measurement ingestion

New `src/hardware_splicer/repair_electrical_evidence.py` consumes an exported KiCad netlist **and** CSV with explicit operator/instrument/probe metadata. It checks:

- exact `component_ref` and pin membership against exported source connectivity; rejects unknown pins/components and pins assigned to multiple nets,
- supported units `dc_voltage/V`, `resistance/ohm`, `continuity/boolean`,
- numerical finiteness, nonnegative resistance and Boolean continuity, unique observation IDs, timezone-aware timestamps and required declared instrument/operator/condition,
- bounded source and CSV sizes and number of rows,
- different reported observations **at the same physical pin with the same named instrument** under different conditions, calculating *only* the numerical delta and never inferring failure of a part.

The source and CSV SHA-256 hashes are recorded. **Named operator and instrument IDs are user claims, not authenticated provenance**. Shared power or ground net membership must never be automatically interpreted as a functional failure path.

### Working software demonstration (entirely synthetic readings)

Example CSV: `examples/repair_electrical_evidence/SYNTHETIC_ONLY_measurements.csv`. The words **SYNTHETIC** are deliberate: no one measured these readings. The actual CLI output was:

- matched `J1.1` twice to source `VBUS`, `U3.1` to source `GND`,
- total 3 claims and one **synthetic** condition comparison with delta **-0.3 V**,
- `physical_repair_verified=false`, `failed_component_identified=false`, `power_on_authorized=false`, `instrument_authenticated=false`.

```bash
pip install -e '.[dev]'
python -m hardware_splicer.repair_electrical_evidence \
  --netlist examples/main_ctrl_esp32_servo.net \
  --csv examples/repair_electrical_evidence/SYNTHETIC_ONLY_measurements.csv \
  --out /tmp/hs_evidence_demo
```

Outputs `REPAIR_ELECTRICAL_EVIDENCE.json` and `REPAIR_ELECTRICAL_EVIDENCE.md`.

### Integrated repair-triage path

The actual existing `repair_triage_cli.py` supports optional `--netlist` and `--measurements-csv` together:

```bash
python -m hardware_splicer.repair_triage_cli \
  example_repair_intake.json ./repair_report \
  --netlist examples/main_ctrl_esp32_servo.net \
  --measurements-csv examples/repair_electrical_evidence/SYNTHETIC_ONLY_measurements.csv
```

One run produces original `REPAIR_TRIAGE.json`, `REPAIR_TRIAGE.md` **plus** the two electrical evidence artifacts. The reports stay separate: **measurements never become verified fault labels or automatic high-confidence diagnoses**. Missing one of the two source inputs aborts rather than silently degrading.

## Getting a real electrical source file

KiCad's documented CLI supports netlist export from a genuine owned schematic:

```bash
kicad-cli sch export netlist \
  --format kicadsexpr \
  --output device.net device.kicad_sch
```

Official KiCad command reference: https://docs.kicad.org/master/en/cli/cli.html .

This trial parses a **repository fixture**, not a new independent KiCad CLI export from the sandbox; `kicad-cli` was not installed in the isolated environment. The fixture demonstrates actual S-expression semantics but is not proof of arbitrary KiCad input compatibility or manufacturer-netlist provenance.

## Acceptance and remaining work

**91 focused regression tests passed** covering corrected netlist import, explicit pass/fail of routing verification, operator CSV input validation, demo condition deltas, original repair workflow, fault-isolation cases, and prior package boundaries. The originally false-green KiCad compiler fixtures were updated to require a **DRC block on the actual copper shorts**, not silently to remove routing checks.

Future engineering requirements:

1. Repair the actual routing shorts using a proper router / KiCad checks, and confirm identical named nets and `REF.PIN` counts before/after.
2. Validate against a fresh `kicad-cli` export of a third-party authorized schematic plus independent netlist assertions.
3. Connect authenticated instrument captures or independent professional measurement reviews, rather than treating operator CSV values as self-proving measurements.
4. Only when the physical path and context have independently corroborated evidence, propose diagnostically discriminating measurements and score them against prospective repair outcomes.
5. Run the same artifacts in a genuine competing tool; no competitor was executed in this PR.

**Bottom line:** Source connectivity preservation and transparent measurement attribution are material repair/manufacturing prerequisites; they are not themselves evidence that HS has repaired a device or beaten an EDA competitor.
