# HS unified engineering — mechanics + practical chemistry + printable casing

**Executed 2026-10-21 on authorized Optiplex; independent isolated integration branch.**

Goal: converge independently built agent contributions without changing their
worktrees, connect them to the existing source-backed AI project execution and
retry three real-device assignments. No automatic manufacturing, sourcing,
repair or physical authority is granted.

## Revisions integrated

- Initial trial branch `test/source-evidence-handoff-20261020` at `445a8945`:
  canonical source ingestion, KiCad/STEP/STL/HTML inspection, model-project
  actions, real cyberdeck STEP/STL PCB carrier.
- Mechanical rollup `feature/hs-mechanical-core-integrated-20261020` at
  `f0833278`: STEP → Gmsh mesh → curved/P2 FEM/contact screening, independent
  numerical validation, Mecha mechanism outputs and authority gates.
- Practical chemistry `agent/chemical-engineering-v0` at `9f698661`:
  practical chemical tasks, supplier-scoped catalogs, API/MCP, project/review
  records, and fail-closed physical/release gating.
- Printed enclosure `e91faac9` (selected upstream change only): existing
  SolidCraft + PartCAD two-part, editable parametric concept and native CAD
  evidence. Replaced an unresolved old `device_case` dependency in its mesh
  verifier with a standalone preservation of the independent mesh audit.

The existing approved release conditions were **not** weakened to make a test
pass. Two historical production-ready plant-watering fixture tests were changed
to assert correctly blocked release when structural contact remains unrun.
Those fixtures still compile; they lack physical validation and assembly
closure, and therefore cannot claim `production_ready=true`.

## Native AI agent-to-tool engineering executions

All trials use the same HS ProjectStore and API. The evaluator selected known
real public reference files and explicitly declared application-specific
engineering requests. The **model did not discover vendor files or create
physical observations**. GitHub Copilot supplied the actual proposed actions;
software-only actions were individually approved through the canonical
session/decision/execute-preview routes. Raw manufacturer source bytes are
kept in the isolated Optiplex ProjectStore, not committed here.

| Project | Actual input | Accepted AI-proposed engineering operations | Result / remaining blocker |
| --- | --- | --- | --- |
| **Cyberdeck** | `sector07-dev/RPI_DEV` KiCad project and STL; `therebelrobot/dinodeck-2026` public alternative BOM | `inspect_registered_sources`, `run_erc`, `run_drc`, `review_mechanical_layer`, `review_practical_chemistry`, `prepare_printed_enclosure_concept` | 26 electrical parts/47 nets; 43 ERC and 16 DRC; 30 SolidCraft concept commands; physical enclosure mate and thermal/material properties **not** validated |
| **Drone** | Holybro X500 V2 manufacturer STEP and `colgecen/DroneSkeleton` donor OpenSCAD geometry | `inspect_registered_sources`, `review_mechanical_layer` | 244 real imported STEP solids, 56,896 donor arm points; whole hybrid assembly outside validated contact FEM topology; no validated arm/fastener interface |
| **PSP-300x** | iFixit UMD-drive replacement guide original HTML | `inspect_registered_sources`, `review_mechanical_layer`, `review_practical_chemistry` | 42 real guide steps indexed; mechanical assembly unsupported by two-pin contact FEM; unknown electrical/battery/material state triggers **`stop_and_escalate`** chemistry decision; no actual console diagnosed |

The chemistry action runs the **real** `assess_practical_chemistry` function
on a request already saved in the pinned project snapshot; model inputs may
not invent substrate, battery measurements, supplier quotes or paths. Caller
`material_identity=verified` is conservatively downgraded to `claimed` until
an independent qualification path exists. The AI action produces a **non-
authorizing review artifact**, not a new accepted chemistry/material clearance.
Canonical MachineProject reviews and the existing enforced chemistry release
gates remain available separately; this first operator integration does **not**
automatically approve or append a chemistry assessment to an accepted component
review.

Mechanics uses source-provenance geometry for scope reporting and a project-
pinned mechanical job for analysis. An unsupported assembly returns that
result explicitly instead of forcing a two-bore model onto a drone or UMD
mechanism. This is correctness, not a solved adapter.

### Real numerical structural-control run

Separately, the **actual HS accepted-action executor** ran the installed Gmsh,
scikit-fem and Mecha structural workbench on its supported **60 × 20 × 4 mm
illustrative two-hole plate**. Assumptions: Ø3.2 mm holes, 40 mm spacing,
0.020 mm driven pin and 0.005 mm radial clearance, linear isotropic elastic
material, no measured donor fixture. Result:

- Three meshes targeted at **8, 6, 5 mm**.
- Computed pin load scales **16.22356, 15.93177, 15.98946 N**.
- Status **`screened_inconclusive`**, numerical status
  `inconclusive_two_pin_contact_stress`: per-hole peaks and contact surface
  resolution remain nonconverged; no material yield-margin acceptance.
- Real generated [STEP bracket](./artifacts/structural_calibration/bracket.step),
  [numeric solver evidence](./artifacts/structural_calibration/evidence.json),
  [predicted load curve](./artifacts/structural_calibration/predicted_load_curve.csv)
  and [required next actions](./artifacts/structural_calibration/remaining_actions.txt).

This is a valid execution of the numerical tool, **not validation of an X500
structural mount**, fabricated printed part, or specimen strength.

## Test results and readiness

Focused integrated checks on the combined branch:

- Cross-device, AI-action, cyberdeck source, printed enclosure and project
  integration selected tests: **87 passed**.
- Chemistry suites on the combined branch: **214 passed, 3 skipped**.
- Mechanical focused suites with the optional `gmsh`, `skfem`, `scipy`, NumPy
  installed: **78 passed**, without those optional tests being skipped.

These are software regression counts, not build acceptance rates. The separate
mechanical draft PR #181 had **7 failing GitHub checks** before integration.
The main release/CI sweep and exploration harness require further verification;
positive scenarios that currently request unverified production authority must
remain blocked rather than counted as engineering success.

## Remaining practical engineering gaps

1. Cyberdeck: confirmed component heights, mounting centres, connector faces,
   enclosure fit and board power/temperature measurement. This newly generated
   concept is **not** a real native SolidCraft run for this device; the older
   SolidCraft trial has real two-part CAD but only fictional design inputs.
2. Drone: split/identify specific STEP solids, establish actual motor/propeller/
   ESC/battery assembly geometry and fastener stack, and choose a physically
   applicable structural load/contact model with measured properties.
3. PSP: confirm exact console revision and fault, battery isolation, true
   contamination/substrate, and part identity before cleaning or disassembly.
4. Chemistry: attach assessed component records to canonical accepted reviews
   with authenticated observations, then verify physical authorizations remain
   denied when data are absent.
5. Sourcing/economics: real seller quotations, shipping, known failure paths
   and physical outcomes remain unverified. No hardware was purchased.
6. Machine-level integration: cannot claim physical competence or unrestricted
   topology coverage from the ability to switch across three software tools.

**Verdict:** shared software engineering workflow demonstrated across three
real-source domains with separate source-bounded mechanical/chemical/CAD
capabilities. Real device assembly and multi-domain engineering validation are
**not yet passed**.

Full per-case numerical records are in [TRIAL_RESULTS.json](./TRIAL_RESULTS.json).
Original unredacted machine/project run evidence remains on Optiplex under
`/tmp/hs-unified-cross-domain-20261021/`.

### 2026-10-21: source-derived KiCad interface audit (next engineering milestone)

The upstream `sector07-dev/RPI_DEV` commit `ebdfcff` was restored directly from
its vendor-published `RPI DEV PCB Files.zip`. The **registered KiCad board bytes**
are processed with the OS KiCad/pcbnew backend in a bounded temporary process.
The analysis returns actual footprint reference/placement coordinates and
nonplated drill features; **it never reclassifies signal or package holes as
mechanical mounting features**.

- Board outline *axis-aligned bounding box*: **90.95 × 61.35 mm** (not exact outline).
- **26** actual footprint positions read from the PCB.
- **No explicitly identified `MountingHole` footprint** in this source board.
- One NPTH 3.6 mm feature, part of the `Q1` TO-247 transistor footprint, **not a confirmed enclosure fastener location**.
- The earlier envelope-only carrier therefore has **unresolved retention**;
  a visually plausible case cannot be accepted as a mating/retention design.

The [machine-readable interface evidence](./cyberdeck_board_interface_evidence.json)
contains the upstream file SHA256, all 26 source placements, and the mechanical
unknowns. A separate optional-source test exercises the original archived board
when available and remains explicitly skipped on hosts without `pcbnew`.
No original publisher board file is included in Git or claimed as an HS-designed PCB.
