# HS Build Challenge 001 — genuine hardware design, not source-import verification

**Status: benchmark specified; no HS-designed device has passed.**

## Device brief (first target)

Build a **24 V nominal → regulated 5 V, 0.5 A output DC–DC module** from an isolated, current-limited bench supply. No AC mains, batteries, grid connection or human-contact/medical loads. This is a **design brief**, not a validated circuit. Input range, max current, efficiency, thermal and noise criteria must be negotiated from part datasheets before fabrication.

HS must create a new candidate from requirements, not submit the existing SPI-flash adapter or a copied manufacturer board as its own design. Published reference schematics are allowed for engineering comparison with explicit attribution, but source provenance must remain traceable.

## First automated submission gate

Required submission directory:

```text
design.kicad_sch
design.kicad_pcb
simulation.cir
bom.csv
design_origin.json
```

`bom.csv` must include `reference,manufacturer_part_number,quantity`.
`design_origin.json` must provide `{"origin":"hs_generated","reference_design_reused":false,"generator_run_id":"<actual run identifier>"}`. These declared labels are **not independently authenticated**; signed/traceable generator receipts are a later gate.

Run:

```bash
python scripts/run_hardware_build_challenge.py /path/to/candidate --out /path/to/receipt.json
pytest -q tests/test_hardware_build_challenge.py
```

Runner hashes candidate files, calls real `kicad-cli sch erc` and `kicad-cli pcb drc`, calls `ngspice -b`, and checks basic BOM identity fields. Missing executable, artifact, or part number fails closed.

**Important:** This first gate does not yet validate simulation output voltages/load sweeps, input range, reference-grounded model accuracy, schematic↔PCB net parity, copper heat dissipation, fabrication exports or physical outcomes. All these fields remain explicitly false even if tools exit successfully.

## Engineering gates that follow

1. **Schematic and technical selection:** real datasheet-backed regulator IC, current/voltage margins, input filtering, protection, compensation where required, and passive ratings. BOM identity tied to stock/orderable parts, reference schematic comparison documented.
2. **Performance simulations:** source-backed model with voltage/output load sweeps, startup and load step, switching ripple, component stresses and worst-case tolerances. A DC operating-point pass alone is not acceptable.
3. **Manufacturing engineering:** KiCad netlist↔PCB consistency, independently reviewed placement/routing, thermal paths, controlled loop geometry, real footprints, ERC/DRC, actual Gerber/drill/BOM/placement exports and assembly validation.
4. **Bench demonstration:** current-limited supply + independent DMM and scope (or suitable calibrated instruments), controlled dummy load, record output regulation, ripple, efficiency, steady-state temperature, shorts/overload behavior. A responsible operator must review safe setup before power-on.

These gates should be based on HS-generated output rather than rerunning a prebuilt fixture. No artifact in this PR establishes HS can produce a functional converter or authorizes fabrication.

## Stop rule

If HS cannot originate an ERC-clean and DRC-clean KiCad candidate with a defensible BOM and simulation model, do not spend further cycles on converter UUID work for this milestone. Fix the authoring/engineering chain first, or scope the product explicitly to **design review and repair assistance**, not autonomous hardware design.
