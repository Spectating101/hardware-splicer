# Manufacturing and power-on hold — HS functional mount pilot

**DO NOT FABRICATE, ASSEMBLE, INSTALL OR POWER THE MODIFIED PCB OR THE FIXTURE BASED ONLY ON THIS PACKAGE.**

This is a third-party-source-derived *digital prototype* for the 50 x 50 mm
four-layer Protolux Trellis Core board (pinned original source in
`source/SOURCE.json`, licensed CERN-OHL-P-2.0 in `source/LICENSE`).

The original M2.5 / 2.7 mm four mounting bores have been edited to nominal
M3 / 3.2 mm clearance. This meets a bounded digital study with 0 error-level
KiCad DRC findings and 0 unconnected pads, but introduces **four additional
footprint-library mismatch warnings**. The revised board remains attached
to the original M2.5 footprint library identity, which is NOT a validated
M3 manufacturing definition. Do not upload supplied native PCB as a fab order.

The companion `cad/` folder contains *actual* source-coordinate-driven
CadQuery/OpenCascade STEP solids for a carrier, inspection guide, bare-board
reference and deliberately exploded non-assembly. These are geometrically
audited **source-derived modeling candidates**. No physical board, printing,
fixture fit, strength, actual standoff, screw head/washer diameter, PCB stack
thickness, connector keepout, torque, ESD safety or electrical measurement has
been checked.

To lift HOLD, obtain the actual specimen and complete an engineering
review of footprint/library consistency, hole edge breakout, mounting hardware
envelope, PCB stackup and component/body keepouts, then rerun independent
native KiCad and 3D audits. Only a separate supervised physical trial using
appropriate instruments and safety procedures can establish physical fit.

**Status: EDITABLE_DESIGN_REVIEW_ONLY. Physical evidence: none.**
