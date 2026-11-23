# HS external product-engineering tools — executable integration 001

**Date:** 2026-11-01. **Product:** ClearBench S1 non-potable sediment-filter R&D digital demonstrator. **Branch:** stacked on complete digital product PR #240; no physical product has been assembled or tested.

## What this change actually executes

Rather than duplicating existing engineering and interactive-rendering engines, HS converts an **identical SHA-256-bound digital product revision** into two genuine external native tool inputs and checks them with actual upstream installations:

1. **blueprint-3d-sheet**, MIT, upstream Git SHA `421c659ccbc0cad8e2343c0238e7a78e0422e46a`: exports a native `AssemblySpec` into `BLUEPRINT_ASSEMBLY_SPEC.json` from the product's housing dimensions, service volume, 3D positions, dry stand, pressure gauge locations, cup, symbolic flow path, functional roles, annotations and safe labels. The actual `b2d validate` and `b2d build` commands run in CI, generating one offline `interactive/index.html` with exploded assembly and multiple views. Source axes are transformed from HS's `(x,y,z vertical)` to the viewer's `(x,y vertical,z)`. All real-world pressure and water-quality claims are explicitly absent.
2. **DeCAD**, Apache-2.0, upstream Git SHA `0c748e5b73810c18cee5ac187a9fb63feb16235c`: exports the real 11-role product BOM as a native OD-BOM 0.1.0 source. Runs `decad validate` and `decad summary` against the generated document. **No real fastening map, interferences or disassembly order have been measured**, so those graphs and execution steps are intentionally empty. A schema-valid concept is **not** a mechanically verified service manual.

`EXTERNAL_TOOL_EXECUTION_EVIDENCE.json` is emitted only once both native executables run. It records exact tool versions, source-commit pins, generated artifact SHA-256 and every physical readiness flag false. User-facing HTML is a **schematic digital concept**, not a sensor simulator or treatment model.

### Reproduce in CI

The sixth job in `.github/workflows/function-first-system-contract.yml` starts only after all five existing product jobs succeed and independently downloads the fifth job's product render, source, STL and receipt files. It rejects missing/modified source artifact content, unexpected health claims, changed product identity and non-self-contained HTML. Then it runs pinned external native programs.

```sh
python scripts/export_product_ecosystem_001.py \
  --product-package .cache/clearbench-s1-product-sample \
  --out .cache/hs-product-ecosystem

# CI installs pinned upstream blueprint-3d-sheet and DeCAD versions.
node .cache/blueprint3d-upstream/bin/b2d.mjs validate .cache/hs-product-ecosystem/BLUEPRINT_ASSEMBLY_SPEC.json
node .cache/blueprint3d-upstream/bin/b2d.mjs build .cache/hs-product-ecosystem/BLUEPRINT_ASSEMBLY_SPEC.json --out .cache/hs-product-ecosystem/interactive
decad validate .cache/hs-product-ecosystem/DECAD_CONCEPT_ODBOM.json
decad summary .cache/hs-product-ecosystem/DECAD_CONCEPT_ODBOM.json
```

CI does not copy or modify source code from upstream repositories. Required external dependency licenses remain in their own respective repositories and linked documentation; all installed package dependencies carry their own obligations.

## Other examined backends — scoped to actual inputs

| Tool | Intended contribution | Actual status in this PR | Next acceptance |
|---|---|---|---|
| [CADCLAW](https://github.com/sunnyday-technologies/CADCLAW) | Constraint-based assembly of native authored STEP parts; collisions, gaps, BOM/STEP parity | **BLOCKED**: ClearBench currently has OpenSCAD conceptual envelopes, not manufacturer STEP parts, exact connector frames or verified bracket dimensions | First author/vendor STEP + named datums and physically grounded joints, then execute `cadclaw assemble validate-spec` and real OCCT checks |
| [MARB](https://github.com/sunnyday-technologies/MARB) | Blind assembly benchmark scored by independent CADCLAW gates | **BLOCKED**: no independently adjudicated reference CAD/placement, equivalent kit or separate competitor solution | Produce independent problem fixture and scoring truth; do not score our own hand-authored solution as independent performance |
| [Teardown](https://github.com/elvarofficial/teardown) | Interactive machine operation, instrumentation, scripted animations | **BLOCKED**: product has no validated kinematics or dynamic fluid model; the blueprint viewer supplies only an interactive assembly **view**, not Teardown's operational simulation | Add a real mechanism with measured/validated kinematic variables and run native Teardown build and film review |
| [SolidCraft](https://github.com/tangency-labs/solidcraft) | Parametric feature-history CAD, constraints and native STEP outputs | **BLOCKED**: no source-verified, qualified bracket/port dimensions; must not invent pressure housings | Run pinned `solidcraft-cli` against dry tray/panel with vendor-independent dimensions; verify STEP export and parametric edits |
| [FieldCraft](https://github.com/tangency-labs/fieldcraft) | FEA/CFD/thermal simulations | **BLOCKED**: real materials, load paths, hydraulic coefficients, safety boundary conditions missing | Use a benchmark with validated mechanical/material boundary conditions; do not simulate water treatment as a pressure-curve guess |
| [re:trace](https://github.com/ericrihm/retrace) | Reverse electronics analysis of actual PCB photographs | **NOT APPLICABLE to this passive filter** without real PCB imagery | Conditional integration for later electrical product with original board photos, inferred connections independently verified |

No claim of eight passing tools is made. Two tools are actual executable integrations here; six are explicitly gated potential backends. This protects the engineering truth bar against treating GitHub discoveries as verified HS capabilities.

## Why it matters

A customer can start with **one product specification** and obtain a complete assembled digital model, an interactive offline explorable engineering sheet, source-linked product/role BOM, and a standards-formatted partial disassembly knowledge record, instead of manually moving models between three separate systems. It is a **digital product explanation/engineering handoff**, not yet an independently validated manufacture or operation.

### Next objective

Do not broaden the app catalog just to inflate integrations. Next use **real source-authored or manufacturer-provided STEP parts**, pins/datums and mounting sizes to run CADCLAW and independent MARB gates. Combine with an actual physical integration check of the operator-facing device. Only after that attempt native SolidCraft, FieldCraft or Teardown operation when genuine requirements justify them.
