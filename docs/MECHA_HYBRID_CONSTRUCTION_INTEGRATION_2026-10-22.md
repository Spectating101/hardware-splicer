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


## Verified upstream file identifiers: Clip-Os (2026-10-22 source check)

Upstream Git commit: `348bad8ba0553be79f24d5ac12a7d4081d7759c8`

* `fab/clip-o_90_moreflexy.stl`: Git blob SHA-1
  `eda0c9041d229c050296a313af5e4bd1a07892ea`
* `fab/clip-o_180_moreflexy.stl`: Git blob SHA-1
  `fab8122d82c96237fa819429a50dc2cbcc99291f`

These are verified **Git object identities** at a pinned upstream revision,
not downloaded STL files, independently computed SHA-256 hashes, sliced
meshes or tested printed parts. Fetch from
[the source revision](https://github.com/zakqwy/Clip-Os/tree/348bad8ba0553be79f24d5ac12a7d4081d7759c8/fab).
The author specifies nominal 1/16-inch (approximately 1.6 mm) sheet stock
and a mounting-hole center inset 1/2-inch (12.7 mm) from the edge; follow
the original instructions and verify the actual hole punch and part fit.
License is CC BY-SA 4.0; preserve attribution and applicable ShareAlike
conditions on distributions/adaptations.

ModuFrame is **still a linked 3 mm nominal source**, not a pinned/binary
verified downloaded model. HS therefore reports its source revision as
unverified and requires physical-fit validation before adoption.

## Three *different* construction variants — measured shop protocol

Use the blank, **not yet completed** worksheet:

`examples/mechanical/hybrid_three_way_trial_template.json`

The comparison is:
1. `full_print` — the existing Mecha-generated enclosure
2. `sheet_hybrid:cardboard_clip_os` — a real measured 1.6 mm stock/Clip-Os build
3. `sheet_hybrid:plywood_moduframe` — a real measured 3.0 mm stock/ModuFrame build

These three methods should satisfy the *same functional dimensions,
electrical interfaces, fastening requirements and usage scenario*.
Photograph/record source files, actual slice outputs, finished assembly,
materials used, sheet scrap, labor time, electrical and thermal checks.
Retain each observation using a distinct specimen ID and a
`record_uri` (the URI is **not authenticated** by the tool).

Copy completed rows under `construction.benchmark_trials` inside the
Mecha project spec. Fields include measured finished mass (g), print/cut/
assembly minutes, consumed material cost, purchased hardware cost,
energy cost, labor cost, recorded fit and attachment observations, and
thermal-check outcome. Use one **consistent currency** for every cost
entry, and do not mistake a zero cost for an unrecorded expense.

A three-way **reported cost order** is available only if all three
distinct alternatives are represented, all costs (including energy and
labor) have explicit values, all declared fit, attachment and thermal
checks are true, and every row is marked `operator_reported`.
Synthetic/missing/incomplete observations yield no such ranking.
Even a complete reported comparison is **not** externally
authenticated, does not demonstrate repeatability, and never selects
a manufacturing method automatically.

The comparison does not optimize panel nesting and **cannot certify
manufactured objects**. It remains a decision aide. Future empirical
validation needs actual trials, ideally replicates per method and
independent review for safety-critical use.


## Verified local external-file handoff (no automatic downloads)

The Mecha runner can now inspect **exact pinned upstream connector bytes**
staged manually under the current build output folder:

```text
my-build/
  SOURCE_ASSETS/
    clip-o_90_moreflexy.stl
    clip-o_180_moreflexy.stl
```

Select `construction.connector_family="clip_os"`; download the exact
files from the pinned upstream revision listed above into the
`SOURCE_ASSETS` directory, then generate the normal Mecha bundle.
The `external_asset_integrity` result inside
`CONSTRUCTION_ALTERNATIVES.json` records whether each local file matches
the **Git blob SHA-1 identity** at the pinned upstream revision.

This is a byte identity check. Wrong file bytes, absent files, local symlinks
and oversized data are refused or marked missing. Neither correct file
bytes nor the source author's reported fit guarantee manufacturable
geometry, print orientation, material strength, dimensional match,
safety or professional sign-off. The files remain in the operator's own
`SOURCE_ASSETS` folder and are not copied into HS's source tree.

The source code never accepts an arbitrary user-chosen file path or fetches
remote source URLs. Unpinned ModuFrame/BOSL2 sources remain reference-only
until their actual assets are registered and checked.


## Construction-method authority behavior

The comparison runs in `preference=auto` as **evidence only**. It leaves
the original `enclosure.scad` unchanged and does not revoke unrelated
release authority merely because it considered hybrid methods.

If a downstream user explicitly requests `preference=sheet_hybrid`
or `preference=off_the_shelf`, HS mechanical production authority is
blocked until a separate human-reviewed validation route exists. This
cannot be bypassed by editing a client-side `release_authorized=true`
flag. Whole-device mechatronics authority inherits the mechanical
release decision. This safety gate is intentionally conservative:
neither matching a supplier STL's Git checksum nor an operator-reported
cost comparison authenticates measured performance.
