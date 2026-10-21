# Hardware Splicer product acceptance - observed 21 October 2026

The **backend / original-source / AI / software-CAD workflow works** in the
controlled Optiplex Linux test. **A completed, functioning physical cyberdeck
has not been established**, and the first published STEP carrier fails one
real original-component intersection. This report deliberately separates
backend operation from geometry, partial populated fit and real hardware.

## Release decision matrix

| Scope | Outcome | Reproduced observation |
| --- | --- | --- |
| Integration CI for `8d9b8ad5` | **PASS** | 36/36 GitHub checks successful; draft PR #182, CLEAN, unmerged |
| Clean checkout product/API regression | **PASS** | 43 passing tests, four nonfatal framework warnings |
| Canonical application API | **PASS** | `/health`, tool schema, package schema and OpenAPI all return 200; 264 documented paths |
| Real engineering workflow | **PASS** | Original three KiCad source files ingested; AI proposed and human approved the board-carrier and edge-retention preview actions; both executed successfully at project revision 10 |
| Published CAD STEP/STL sanity | **PASS (bounded)** | Three board/base/lid solid overlaps zero, pad/trace projected keepouts zero; STL meshes are closed by edge-incidence check |
| Exact published CAD against seven available original component models | **FAIL** | SW1 intersects lid by **1.584 mm³**; six other available original model occurrences clear |
| Separate improved local CAD candidate | **PASS only within partial 3D scope** | 7/7 available original component models clear; geometry and STL checks pass; **not integrated/published** |
| Original PCB KiCad ERC/DRC | **WARNINGS** | ERC 0 errors / 43 warnings; DRC 16 warnings / 0 unconnected pads; mostly locally unresolved libraries / mismatch |
| Complete device operation | **NOT VERIFIED** | No physical assembly, powered operation, tolerance, mechanical retention or thermal acceptance test |

The source `.kicad_pcb` SHA-256 is
`ddf94ad6fdaee46a52022b20da8678cebd34cec4f4db817d090cd0e45119f042`.

## Important correction to earlier audit evidence

The earlier seven-model clearance report was generated against a *newer case
revision* than the STEP files stored at
[`projects/cyberdeck_edge_retention_20261021`](../cyberdeck_edge_retention_20261021).
A fresh reimport of the **exact checked-in base/lid SHA-256s** yielded the
SW1 collision. The newer candidate has STEP hashes beginning
`3c2f82a6` (base) and `61fca49f` (lid), and passed its independent model
recheck, but its changes are uncommitted in the concurrent component-model
work and are *not* release evidence for the published CAD.

The corrected version-bound result is
[`INDEPENDENT_COMPONENT_AUDIT.json`](../cyberdeck_edge_retention_20261021/INDEPENDENT_COMPONENT_AUDIT.json).
The `scripts/recheck_hs_cyberdeck_published_models.py` diagnostic recomputes
original component-vs-case interference and returns **exit code 2 on collision**;
that nonzero return is an intended *rejection*, not a CI harness bug.

## KiCad findings

KiCad ERC scanned the original schematic and returned **43 warnings / zero
errors**. DRC scanned its board and returned **16 warnings**, zero unconnected
pads and zero reported footprint errors. Warnings included an unavailable
`Connector_Wire` footprint, unconfigured `Connector` and `Switch` schematic
libraries and a TO-247 footprint library mismatch. These should not be silently
ignored, and no board was electrically tested.

## Remaining gaps before finished-product confirmation

There are **26 PCB footprints**, seven original 3D models successfully
retrieved/placed, four missing referenced model identities, and fifteen source
footprints that declare no model. Connector/cable mating, fastener mechanics,
actual component heights, material tolerances, creepage/insulation, thermal
performance, fabrication and first-article bench testing remain incomplete.

The immediate technical priority is integrating the newer collision-free
source-model-aware CAD revision **together with matching exported assets and
recorded hashes**, then completing missing envelopes. Do **not** claim a
usable/powered/saleable cyberdeck before a physical assembly and bench test.

**Evidence:** GitHub PR #182 status at tested SHA; clean-worktree product
regression (43 passed); native TestClient API smoke; real registered-KiCad
model-proposed/approved/executed CAD session; KiCad ERC/DRC; independent
CAD/mesh reimports and original-component STEP checks. All tested on authorized
Optiplex, no physical-device verification.
