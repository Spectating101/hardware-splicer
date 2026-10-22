# Hybrid construction in existing HS / Mecha-Splicer

This integration does **not** create a new CAD engine. It compares ways of
constructing a rectangular enclosure using the existing fully printed
OpenSCAD geometry, ordinary sheet panels with external connector designs,
or sourced finished assemblies. It **never auto-replaces CAD** based on
unverified data.

## Minimal run

The file `examples/mechanical/hybrid_enclosure_assumptions.json` contains
**deliberately invented illustrative figures** to demonstrate the interface.
They are NOT certified PETG/plywood material values, real measured connector
volumes, or supplier quotations. Replace every assumption with documented
local measurements, datasheets and quotations before using cost/mass estimates.

```python
from hardware_splicer.mechanism_bridge import _ensure_mecha_on_path
_ensure_mecha_on_path()
from mecha_splicer.runner import run
import json
with open("examples/mechanical/hybrid_enclosure_assumptions.json") as handle:
    project = json.load(handle)
bundle = run(project, out_dir="hybrid-evidence-01")
print(bundle["construction_alternatives"]["status"])
```

The ordinary Mecha build still outputs `enclosure.scad` with the original
printable walls and lid. When `construction` is supplied, two additional
files are created:

* `CONSTRUCTION_ALTERNATIVES.json` — input-derived geometry, optional
  masses/costs, chemical and temperature suitability, source links, blockers
* `CONSTRUCTION_PLAN.md` — a review checklist, approximate six-panel cut
  rectangles, licenses, and external connector sources

Also connected: `RISK_REGISTER.md`, `MECH_CHECK.md`,
`BUILD_RECIPE.md`, `DESIGN_DECISIONS.md`, `SIM_RESULTS.json`, the
normal Mecha bundle and the HS mechanism-pack capability catalog.

## Provenance and library reuse

Available references are **catalogue links only**, not downloaded libraries:

| Library | Intended use | Known nominal thickness | License/handling |
| --- | --- | --- | --- |
| [Clip-Os](https://github.com/zakqwy/Clip-Os) | Print existing sheet edge couplers | 1.6 mm | CC BY-SA 4.0; preserve obligations |
| [ModuFrame](https://www.printables.com/model/1834996-moduframe-modular-connectors-for-3mm-plywood-sheet) | Plywood connectors | 3.0 mm | Verify the particular model's license before reuse |
| [BOSL2](https://github.com/BelfrySCAD/BOSL2) | Parametric hinges and joinery | Parameter-dependent | BSD-2-Clause |
| [Modular Clip](https://github.com/jmylchreest/openscad-models) | Edge clips / dovetails | Parameter-dependent | Verify exact source revision |
| [Boxes.py](https://github.com/florianfesti/boxes) | External sheet-cutting tool | Parameter-dependent | GPL-3.0+; call externally rather than copying engine |

No source files are copied or assumed to be installed. None has been
validated on this specific box. Use physically **measured** sheet
thickness, not nominal advertised thickness, when selecting a joint.

## What is and isn't computed

The fully printed baseline uses the solid wall/floor/lid **CAD envelope**
and optional explicitly supplied material occupancy assumption, not real
sliced G-code. It excludes cutouts, standoffs, supports, failed-print
waste, printer energy and labor.

The hybrid estimate approximates six **uncut outer bounding rectangles**.
It multiplies total sheet area by panel thickness and an explicitly
supplied density, and adds `connector_count × measured/assumed connector
printed volume × filament density`. This does not handle nesting, panel
overlaps, kerf, slots, material kerf loss or fastener hardware mass.
If any needed property is absent, the related mass/cost is `null`.

Cost only includes sheet cost/m² and filament cost/kg **supplied by the
user**. It excludes shipping, rework, cutting and assembly labor, screws,
purchased hinges, adhesives and amortization. Comparisons are hypothetical
material-only estimates, not optimized COGS.

The thermal check **only compares a provided operating temperature to a
reported service temperature**. It does not calculate local component
temperature, heat flux, thermal resistance, cooling airflow, ignition,
flammability, electrical enclosure standards or fire risk.
Chemical checks read explicit exposure/compatibility declarations; an
unknown pair is not automatically safe. Mechanical stiffness, connector
pull-through, hinge fatigue, impact and load-bearing assembly safety
require proper models and physical trials.

A candidate with mismatched nominal connector thickness, incompatible
exposure, temperature beyond reported limits, missing material evidence,
or unverified source assets is blocked from being selected.
The evaluator does not create a fabricated-part rating and always returns
`selected_manufacturing_method=null` and
`fabrication_authorized=false`. It **does not** call the two-pin contact
FEM on sheet connectors, since that solver does not represent this
joint geometry.

## Practical next validation

Compare the same electronics box as: (a) existing fully printed shell;
(b) measured 1.6 mm card stock plus Clip-Os couplers; and (c) measured
3.0 mm plywood with ModuFrame couplers. Select published source files,
pin revision/hash and terms, print a coupon for each actual connector,
measure fit and pull-through, and benchmark real grams, assembly time,
service temperature and cost. Until those observations exist, the
planner is a sourced *proposal* engine, not a manufactured product.
