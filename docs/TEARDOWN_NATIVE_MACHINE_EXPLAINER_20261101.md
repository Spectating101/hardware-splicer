# HS product-facing native CAD explorer

## November 18 robotics comparison

HS already uses Elvar's Teardown runtime for the ClearBench explorer and the
separate OpenArm Sortcell workcell. The Sortcell build now verifies both the
source mesh and its metadata against the approved revision, and checks that all
542 named mesh nodes match the source parts list. The Chromium replay verified
all five task phases and the explode control. The PyBullet trajectory uses a
separate OpenArm URDF. Under the candidate mounting transform, the reach check
demonstrated zero of the four displayed fixture targets. The model and workcell
coordinates still need registration. [Teardown source](https://github.com/elvarofficial/teardown)

| Reference | What it adds to HS |
| --- | --- |
| [OpenAMRobot mobile base](https://github.com/openAMRobot/openamr-platform-hw) | A full assembly STEP, wiring, electrical and mechanical BOMs, and variant history. HS opened the full assembly and counted 2,924 CAD solids. The sources cover different configurations, so an exact build needs a revision-aware cross-reference. |
| [SO-ARM102](https://github.com/roboninecom/SO-ARM102) | A smaller reproducible arm with itemized sourcing, printable parts, assemblies, an assembly guide and a URDF. HS imported its eight links and seven joints. This is a good reference for testing whether HS keeps fasteners, model joints and purchased components aligned. |
| [PathOn SO-101 wrist](https://github.com/PathOn-AI/PathOnRoboticsOSS/tree/20940773bc2e6c83fea869580d53380ab1573795/hardware/robots/so101_6dof_wrist) | A useful comparison for adding a joint and changing the gripper. The original hardware has a restricted license, so the comparison links to the source. |
| [Calibrex](https://github.com/rsasaki0109/calibrex) and [RoboSimStudio](https://github.com/robosimstudio/robosimstudio) | Calibrex can check calibration from recorded sensor data and report unobserved axes. RoboSimStudio is a comparison for reconstructing a physical scene and testing manipulation in simulation. |

The [robotics signal feed](../examples/github_signals/robotics_candidates_20261118.json)
pins the candidates for review through the existing GitHub signal pipeline. The
[comparison evidence](status/generated/robotics-external-comparison-20261118.json)
holds the exact inputs and observed results.

The missing product workflow is a rebuildable teardown for one coherent revision.
Selecting a part should reveal its native geometry, assembly location, exact BOM
entry, and connected schematic or wiring source. A substitution should identify
which mounting, electrical and motion checks need to run again. Evidence for
that workflow and the public service controls are tracked in the
[deployment guide](PACKAGING_AND_DEPLOYMENT.md#external-backend-release).

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
