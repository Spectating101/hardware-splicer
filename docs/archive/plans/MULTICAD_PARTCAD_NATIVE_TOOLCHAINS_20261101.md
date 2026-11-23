# HS external toolchain reuse: independent CAD authoring and part package

2026-11-01 — draft stacked on CADCLAW PR #242 (which depends on #241/#240).

## Purpose

Continue native execution rather than adding a list of GitHub links. The new backend takes an **explicit generic part manifest** and original source-bound STEP files, and actually authors another set of real STEP parts through **build123d**. The new STEP files and original CadQuery-made STEP files are reimported with CadQuery and independently compared for dimensions, volume, solid count and digests. It then packages the authored parts as native `partcad.yaml` with STEP sources for **PartCAD**.

The first integration specimen happens to use the four simple conceptual ClearBench dry parts, but the manifest validator and native build123d/PartCAD interoperability are **not hard-coded to the ClearBench product ID**. Other products can supply their own independently verified part manifest.

## Evidence stages (never conflated)

1. `PARTS_MANIFEST.json`: source-bound native reference parts, dimension metadata, concept-only authority.
2. `MULTICAD_NATIVE_EVIDENCE.json`: generated STEP geometry with actual independent importer comparisons. This only appears after the native build123d runner returns successfully.
3. `partcad/partcad.yaml`: a PartCAD-native package mapping each authored STEP to a part. Creating the file alone does **not** claim PartCAD executed.
4. `PARTCAD_EXECUTION_RECEIPT.json`: only generated after the **actual** `pc` command returns zero; captures its transcript SHA256. If upstream CLI fails, this file does not exist, and the native PartCAD integration does **not** pass.

This adds one genuine native CAD authoring route and a package-management interface; it does not claim parametric freeform engineering design, equivalent toolchain correctness on arbitrarily complex parts, physical manufacturability, or vendor-qualified mating.

## Backends under review, not silently "integrated"

| Upstream | Status / next independently verifiable condition |
|---|---|
| SolidCraft (MIT OR Apache-2.0) | Its documented `solidcraft-cli run` JSON script engine can be tested against the generated STEP only after a pinned headless executable can be built/installed in CI. No current native execution here. |
| build123d-mcp (Apache-2.0) | The package provides an MCP agent interface to build123d. This PR executes **build123d directly**, not the MCP server; authoring through MCP needs its own acceptance and security harness. |
| CADCLAW (MIT) | Existing upstream native STEP assembly stage in #242, no production-qualified joints. |
| MARB (MIT) | Independent benchmark fixture and impartial scoring still absent. |
| FieldCraft (Apache-2.0) | Needs real material parameters, loads, constraints and independent simulation calibration. |
| atopile (MIT) / tscircuit (MIT) | Candidate code-to-PCB backend, must reconcile actual KiCad exports/net identities with HS native EDA before native integration claim. |
| InvenTree (MIT) | Could host source-bound component/stock identifiers; first use test instance and qualified part revisions, never infer inventory from a BOM. |
| libsigrok (GPL-3.0) | Real measurement import should require instrument identity, acquisition metadata and physical operator approval. |
| OrcaSlicer (AGPL-3.0) / OpenPnP (GPL-3.0) | Machine workflows need isolated licensed-tool processes, interlocks and authorized physical machines. |
| Teardown (MIT) | Operation simulation requires actual kinematics; do not pass illustrative visuals as measured dynamics. |
| OpenHarness | Research separately; not a substitute for HS engineering provenance and CI acceptance. |

Licenses as observed in upstream GitHub repository metadata on 2026-11-01. The GPL/AGPL backends need legal distribution/derivative review before packaging. This change vendors no external source code.

## Reproduce

```sh
python scripts/export_multicad_parts_001.py \
 --product .cache/clearbench-s1-product-sample \
 --cadclaw .cache/hs-cadclaw-dry-product \
 --out .cache/hs-multicad-parts
# Native execution of build123d and independent CadQuery verification inside the CLI above.
# PartCAD CLI is separately invoked on .cache/hs-multicad-parts/partcad.
```

Every source STEP and output STEP must be present and hash verified, with physical release false.
