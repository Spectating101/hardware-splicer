# Hardware Splicer + SolidCraft + PartCAD: actual parametric printed casing

Executed on authorized Linux Optiplex, October 20, 2026.

**Scope:** working conceptual CAD and geometry-to-assembly interoperability.
NO recovered donor dimensions, successful print, actual component fit, measured
load, verified thermal performance, slicing, G-code or hardware release.

## Why mechanical casing matters

Salvage splicing requires more than working circuit blocks: parts need
compatible physical mounts, toleranced enclosures, port relief, cooling,
service access and a printable bill of materials. Existing HS device_case.py
already produces binary STL/OpenSCAD two-part cases and closed mesh audit,
but admits it has no bosses, standoffs, vents or strain relief.

The new workbench reuses its independent mesh_report integrity checker and
moves editable parametric mechanical geometry to the real SolidCraft GUI.

## Real SolidCraft native result

Declared SOFTWARE TEST case: external dimensions 100 x 75 x 35 mm,
2.4 mm walls and floor, 2.4 mm separate lid, 1.8 mm locating skirt,
1.2 mm skirt radial thickness and 0.35 mm per-side nominal lip clearance.
Four 8-mm screw bosses with provisional 2.7-mm pilots, four 6-mm
sample PCB standoffs, one 14 x 7-mm cable port, six 4.4-mm lid vents and
four 3.2-mm lid clearance holes.

Native SolidCraft actually executed the shell, eight bosses,
lid skirt extrusion, side wall cable cut and ten holes.
Results are fully editable in CASE_PRINT_LAYOUT.solidcraft and
CASE_ASSEMBLED.solidcraft. Both native solid bodies can be exported
individually as STEP or printable binary STL. A two-part millimetre-unit
3MF print layout, assembled and layout STEP, CAD previews and a genuine
SolidCraft GUI screenshot were generated.

The screenshot shows the actual GUI browser, sketch tree and feature
timeline, not an image mockup.

## Independent mesh and geometry results

The runner read each actual SolidCraft STL triangle back and invoked
the existing HS directed-edge mesh integrity audit. Both are closed
manifolds. Measured CAD/kernel vs independently triangulated volumes:

| Body | Native CAD volume (mm3) | STL volume (mm3) | Closed |
| --- | ---: | ---: | --- |
| Base | 50244.99 | 50226.49 | yes |
| Lid | 29464.15 | 29466.86 | yes |

Small differences are tessellation/coordinate rounding. 3MF was opened
and checked for exactly 2 mesh objects and millimetre units.

The real installed PartCAD 0.8.220 tool imported both native STEP
components and produced a two-item BOM: one base, one lid; no vendor,
no acquired stock. It also exported an actual ASSEMBLED STEP with both
bodies moved to the correct overall casing frame. Native SolidCraft
reopened the PartCAD assembly and its two solids matched geometry and
placement within specified tolerances. STEP re-export loses parametric
feature history and may rename solid bodies; keep HS and PartCAD IDs
and the editable SolidCraft design as the source of truth.

## Agent and reproducible CLI

The HS SDK adds prepare_printed_casing(casing_spec=...); the MCP tool
hs_prepare_printed_casing is accessible to agents. It returns native
SolidCraft commands and dimensional/authority records without touching
a printer or invoking a slicer.

For full mechanical tooling, use the isolated installed binaries:

    PYTHONPATH=src python -m scripts.run_printed_enclosure_workbench \
      --spec examples/printed_casing/conceptual_salvage_controller.json \
      --out /tmp/my-hardware-splicer-casing \
      --solidcraft-cli /path/to/solidcraft-cli \
      --partcad-cli /path/to/pc

The full run uses actual SolidCraft native CLI, real SolidCraft STL and
3MF exporters, independent manifold/volume checker, actual PartCAD
two-part BOM and assembled STEP exporter, and independently checks the
PartCAD exported volumes/bounding boxes by reopening them in SolidCraft.
The script supports plan-only mode without installed external binaries.

Machine readable real evidence:
docs/evaluations/NATIVE_PRINTED_CASING_PARTCAD_TRIAL_2026-10-20.json
Actual CAD, models, 3MF, STL and GUI screenshot:
examples/printed_casing/native_trial/

## Print preparation and real-world blocking requirements

The output STL and 3MF are candidate SLICER INPUTS, not qualified
printer-specific G-code. No slicer software was confirmed on the Optiplex,
and no printer was identified or powered.

Preliminary FDM guidelines only:
- Example nominal 0.4-mm nozzle and 0.2-mm layers (NOT verified).
- Nominal 2.4-mm walls correspond to six 0.4-mm paths before process
  compensation; slicer extrusion width is printer/material dependent.
- Base stands on its floor, open top up. Lid rests on its plate,
  locating skirt up. Combined print layout width 212 mm by depth 75 mm,
  excluding brims/skirts/travel clearance. Print pieces separately if
  the verified printer bed cannot support the combined layout.
- 1.8-mm skirt is nine nominal 0.2-mm layers; 2.4-mm lid plate is
  twelve such layers. Verify actual slicer toolpaths.
- The 14-mm connector aperture may require bridge/support review.
- Six lid vents are present but no thermal/airflow model exists.

Before first real print, record a REAL donor specimen and measured
size, connector socket, PCB thickness, mounting holes and fit/cooling
constraints. Rebuild the case from those measured values with
source/instrument provenance. Verify actual printer model, material
(PLA/PETG etc.), nozzle, extrusion, support, bed and temperature
profiles. Slice with real printer-specific profiles; inspect actual
G-code/toolpath preview. Print a small tolerance coupon first.
Measure shrinkage, screw holes and lid clearance; then print the
first unpowered prototype and physically test fit. Assess screw
engagement, boss fracture, cabling strain relief, insulation,
EMI, heat/ventilation, ingress and serviceability.

Existing HS printer_operator.py already separates G-code staging,
authority and start/cancel controls. This work never stages or starts
a print: NONE of the physical authorization gates are satisfied.

## Next mechanical priorities

1. Keep SolidCraft as HS's primary mechanical CAD UI; stop duplicating
   custom 3D-editing software.
2. PartCAD manages part/assembly BOM and references; HS manages
   provenance, confirmed donor identities and verification authority.
3. Add donor-measured mechanical inputs to the parametric casing spec:
   PCB envelopes, actual mounting centres, connector faces, motor
   brackets, cable exits, heat/ventilation zones, wheel clearances and
   access lids. Distinguish unverified proposals from measurements.
4. Add a real slicer adapter and printer-profile authority checks.
   Do not print without separately reviewing gcode and hardware.
5. Present HS evidence beside SolidCraft view via a companion panel;
   the fully unified graphical interface has NOT been completed.

Verdict: native, printable 2-part geometry and actual assembly interchange
demonstrated. Full spliced functional physical hardware UNPROVEN.
