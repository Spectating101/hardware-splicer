# f.60 revised cut: 58 original keys retained + 4 relocated (2026-11-16)

**Status: source-derived electrical and mechanical design preview. No physical keyboard, hardware cut, plate print, assembly, continuity or powered firmware validation. Fabrication blocked.**

Exact independent upstream source: [robertcalvert/f.60](https://github.com/robertcalvert/f.60), `hardware/keyboard.kicad_pcb`, SHA-256 `e0c605a421dec0e88264beb50f5c3ad58b37a0c20294703e6d8637c0f8613cd6`. Only derived reference models and generated original HS artifacts are committed here. Third-party original PCB and firmware are **not vendored**.

## What changed versus the earlier five-key solution

The previous optimizer used circular 8.5 mm switch keepouts; the actual nominal 14×14 mm Cherry MX plate cutout extends farther into the corners. Independently tracing the original KiCad Edge.Cuts polygon revealed the previous proposed route missed a **V key switch-plate clearance**, so that design cannot be considered geometrically solved.

The corrected solver uses 17×17 mm axis-aligned switch-aperture keepouts, compares 12 source-referenced stepped cut candidates and picks a route that does **not intersect live electrical pads, vias or critical source controller regions** in the model.

| Engineering criterion | New source-bound proposal |
|---|---:|
| Original source PCB Edge.Cuts contour | 56 actual KiCad arc-tessellated vertices |
| Original reference switch positions | 62 |
| Source switches retained on left / right PCB halves | **35 / 23** |
| Original keys requiring separate remount | **4 — I, J, N, 9** |
| Complete nominal MX switch cutouts modeled | 58 × 14 mm square |
| Minimum modeled original board/cut edge to retained-key hole clearance | **1.7784 mm** |
| Cut-created required copper groups remaining after restoration | **0** |
| Copper groups intentionally left floating / isolated | **5**, source terminal free |
| Original source ideal matrix patterns checked | **91,230; zero model mismatches** |
| Reconnection interposer | 18 source-net restoration edges (KiCad DRC clean) |
| Source-bound unified junction | 16 source-net groups, 34 unique donor contacts + 8 remount wires = **42 terminals**, KiCad DRC clean |
| Smaller IDC50 connector board | 42 contacts in use, 8 deliberately unused, native DRC clean |
| Original source KiCad design with exact original bytes DRC clean | **Not established** |
| Physical mounting, stabilizers, case, PCB edge clearance or printed fit | **Not tested** |

### Editable engineering artifacts

- `mechanical_plate/SOURCE_BOARD_OUTLINE.json`: native original KiCad 56-point Edge.Cuts contour (not a rectangle invented by HS).
- `mechanical_plate/left.scad` and `right.scad`: **OpenSCAD source** for the two nominal 1.6 mm-thick reference switch plates, each with all its retained switch holes. No prints or render verification.
- `mechanical_plate/board_half_switch_plate.svg`: actual source-coordinate 2D cut and hole diagram, not an assembly photograph.
- `mechanical_plate/PLATE_GEOMETRY_CHECK.json`: source/cut hash, aperture-to-edge clearances, completeness count and fabrication blockers.
- `key_remount/remount_keys.kicad_pcb`: source-derived four-MX-switch relocation board with 8 independent original pad contacts and zero native KiCad DRC violations.
- `interposer/reference_bridge_interposer.kicad_pcb`: 18-channel source electrical graph bridge preview; do not install with the unified harness as a parallel second bridge.
- `full_junction/keyboard_recovery_junction.kicad_pcb`: source-consolidated 42-terminal, 16-bus full KiCad junction preview.
- `compact_idc50/compact_idc50_junction.kicad_pcb`: optional compact 42×94 mm source-wiring board using 42 of 50 header positions; **alternative** to the full junction, not an additional parallel assembly.
- `MULTI_ROUTE.json`, `STEPPED_CUT.json`, `POSTCUT_ISLANDS.json`, `FULL_MATRIX_SOURCE_PROOF.json`, `MACHINE_PROJECT_HANDOFF.json`: exact source and proposed design provenance.

These files must **not** be used as a fabrication package without reviewing switch/stabilizer fit, donor board revision, structural plate fastening and assembly tolerances. No new holes are approved through the original PCB, and the switch holes are *only nominal* Cherry-MX axis-aligned cutouts.

### Simulated copper island quarantine

The revised route isolated a terminal-free R0 trace/via region. The repair operator now identifies source islands with **no surviving electrical component pad**, no filled-zone geometry and bounded total copper area (track-only <=7 mm², track+via <=25 mm² and <=4 via fragments). Only these can be left floating in the modeled source-net graph. This is not permission to skip physical insulation/short checks. Terminal-bearing copper, filled zones, larger or unbounded islands remain blockers.

### Reproducing the same workflow

Use the verified original PCB and SHA-pinned independent upstream firmware/schematic sources as in [the previous f.60 electrical reference](../f60_remount_round5/README.md).

    PYTHONPATH=src python scripts/hs_keyboard_splice_probe.py \
      --pcb /path/to/original/f60.kicad_pcb \
      --out /tmp/f60_round10/CUT_OVERVIEW.json \
      --optimize-stepped \
      --multi-route-json /tmp/f60_round10/MULTI_ROUTE.json \
      --stepped-path-json /tmp/f60_round10/STEPPED_CUT.json \
      --repair-mode auto \
      --repair-iterations-json /tmp/f60_round10/REPAIR_ITERATIONS.json \
      --postcut-islands-json /tmp/f60_round10/POSTCUT_ISLANDS.json \
      --postcut-edges-csv /tmp/f60_round10/BRIDGE_CANDIDATES.csv \
      --machine-project-json /tmp/f60_round10/MACHINE_PROJECT_HANDOFF.json \
      --interposer-out /tmp/f60_round10/interposer \
      --key-relocation-out /tmp/f60_round10/key_remount \
      --independent-source-dir /tmp/original_f60_upstream_files \
      --source-pin-manifest examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/f60_remount_round5/SOURCE_PIN_MANIFEST.json \
      --independent-source-audit-json /tmp/f60_round10/INDEPENDENT_SOURCE_AUDIT.json \
      --full-matrix-proof-json /tmp/f60_round10/FULL_MATRIX_SOURCE_PROOF.json \
      --full-junction-out /tmp/f60_round10/full_junction \
      --compact-junction-out /tmp/f60_round10/compact_idc50 \
      --mechanical-plate-out /tmp/f60_round10/mechanical_plate

Source-aware software tests deliberately reject the previous V-clipping cut, wrong/source-swapped PCB identities, missing/remapped keys, unverified floating copper and stale junction net inventories.

**Remaining physical milestone:** mounting/printing two plates, verifying switch/stabilizer fit and donor copper/isolation, exact connector/cable/strain relief, bench continuity, and original controller firmware operation. The HS MachineProject still denies `BUILD_READY`. The original eight-board arbitrary physical-junk benchmark remains **0/8 fully validated**.
