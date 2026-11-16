# HS product-facing native CAD explorer

## Scope

This branch upgrades the earlier Teardown engine adapter from an invisible/primitive viewer into a real product-facing, **assembled-first native CAD viewer** built with the actual upstream Teardown runtime. All rendered parts come from source-bound CADCLAW assembly STEP tessellation with native BRep identity checks, and an offline glTF bundle; the release authority remains **blocked**.

## Visual acceptance incident and correction

PR #247's first green Chromium CI had a real defect: the previous HS CSS set `#app { position:relative }`, overriding upstream Teardown's fixed full-viewport root. The HTML and WebGL buffer existed but the visible stage collapsed. The screenshot showed UI buttons with no 3D geometry. The old test only checked canvas buffer width and JS interaction state, so it passed falsely.

The current test explicitly checks that the CSS canvas is full-height, samples the **actual WebGL framebuffer** in its model region for hundreds of illuminated CAD-colored pixels, validates the assembled-first state, checks guided steps and reset, and records both assembled and exploded real Chromium screenshots. The report must contain those successful checks before a native acceptance receipt can be signed.

## Product experience

- **Assembled-first hero:** actual source STEP arrangement; no automatic unexplained part separation.
- **Real CAD geometry:** four source-identified BRep solids tessellated and loaded as native glTF meshes, not geometry reconstructed from bounding boxes.
- **Interactive inspector:** model picking, dimensions and STEP hash excerpts, part-focused isolation, section clipping, orbit, top/3-4 views and zoom.
- **Guided exploration:** stages from the verified parts manifest; smoothly interpolated disassembly visualization. This sequence is conceptual, NOT a verified service/assembly process.
- **Evidence panel:** digital provenance, native part count and deliberately zero physical validation certificates.
- **Actual HS frontend:** `apps/splice-ui` now includes a first-class Product explorer nav and home action. A **gated same-run packaging step** copies the verified offline Teardown HTML and evidence manifest into the React/Vite public directory, runs React tests, builds a static frontend, then checks embedded iframe controls in Chromium.
- The published frontend bundle remains offline-capable as static files served over HTTP. It is a downloadable CI artifact; this PR does not silently deploy a publicly hosted site.

## Reproduce in the native CI

```sh
# Runs only after CADCLAW -> build123d -> PartCAD were verified in the same workflow.
python scripts/export_teardown_product_001.py --multicad .cache/hs-multicad-parts --out .cache/hs-teardown-product
python scripts/build_teardown_cad_mesh_001.py --multicad .cache/hs-multicad-parts --cadclaw .cache/hs-cadclaw-dry-product --output .cache/hs-teardown-product/machine
node .cache/teardown-upstream/sims/build.mjs .cache/hs-teardown-product/machine
node scripts/verify_teardown_browser_001.mjs .cache/teardown-upstream .cache/hs-teardown-product/dist/machine.html .cache/hs-teardown-product
python scripts/verify_teardown_acceptance_001.py --product .cache/hs-teardown-product
python scripts/package_teardown_showcase_001.py --source .cache/hs-teardown-product --public apps/splice-ui/public/showcase
npm --prefix apps/splice-ui ci
npm --prefix apps/splice-ui run build
```

## Remaining product/engineering gaps

ClearBench remains a **conceptual four-solid dry reference**, not a realistic, manufacturer-qualified final hardware product; it lacks hoses, fasteners, internals and calibrated operating flow. The visual guided sequence uses scripted exploded offsets, not independently verified kinematics or a safe field-servicing order. There is no physical equipment simulation, customer acceptance test, manufacturing release or real utility measurement. To reach Teardown's flagship quality, next increase sourced assembly detail, authored materials and geometry fidelity, validated working mechanism models, controlled user feedback, and a public preview deployment.
