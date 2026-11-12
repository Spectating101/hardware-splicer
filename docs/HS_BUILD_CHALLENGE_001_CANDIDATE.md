# HS Build Challenge 001 — First generated candidate (2026-10-26)

Run `python scripts/generate_hs_build_candidate_001.py --out /tmp/hs-candidate-001` to create an **actual machine-readable net topology proposal**, `design_candidate.json`, from the requested 24 V nominal input / 5 V, 0.5 A output goal.

**Component baseline:** TI LM2596 fixed 5 V family and the **published fixed-output example topology** (original design basis: https://www.ti.com/lit/ds/symlink/lm2596.pdf). The design explicitly marks this reference-topology reuse. It does not claim independent circuit invention or validate every datasheet component recommendation for a 24 V input.

The proposal defines VIN, SW, VOUT and GND nodes, the LM2596 pin assignments, catch diode, output inductor, input/output capacitors, connectors, and which identities/datasheet calculations remain unresolved. U1 shutdown pin 5 is grounded for enabled operation on the selected device. Manufacturer identities for passives, diode and connectors intentionally remain null rather than inventing procurement-valid SKUs.

**Current actual build gate:** FAIL / NOT SUBMITTED. The generator does not yet produce `design.kicad_sch`, `design.kicad_pcb`, `simulation.cir`, or an approved `bom.csv`. The HS build challenge intentionally does not treat a JSON-only wiring sketch or the TI example as a built device.

## Required development next

1. Select actual rated diode/inductor and input/output capacitors using the official datasheet design procedure and explicitly documented design margins. Confirm the chosen exact IC/package and footprints.
2. Implement a native KiCad 9 schematic authoring backend that translates this *actual candidate net graph* into symbols, pin instances and electrical connections; verify by an independent `kicad-cli sch export netlist` comparison.
3. Produce a model-aware SPICE representation: actual regulator manufacturer model if compatible, or explicitly labeled approximate model with quantitative limitations. Verify startup, steady state, load sweep and stresses rather than trusting simulator exit code.
4. Develop and check PCB footprint geometry, placement and routing. Compare PCB physical nets with the independently exported source schematic, ERC/DRC, manufacturability and thermals.
5. Only then investigate fabrication, controlled bench testing and commercial claims.

This candidate isolates the precise HS bottleneck: the path from a connectivity proposal to native KiCad, physically manufacturable files is still missing. Do not accept future "finished hardware" claims until those exports and measurement evidence exist.
