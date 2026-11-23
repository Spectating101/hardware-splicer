# CLEARBENCH S1 — complete product-level digital demonstrator

**Revision:** 2026-11-01. **Design class:** human-supervised, non-potable sediment filtration R&D demonstrator. **Not built, not pressurized, not verified to remove particles, not for drinking.**

## The reason for this milestone

Hardware Splicer should not finish with a collection of parts, unrelated provenance ledgers and no recognizable object. The point of compiling engineering capability is to **synthesize the whole device around what its user wants done**. This release is the first top-level, operator-facing *digital product specimen* on the water-filter path, not an additional isolated component module.

The product is called **ClearBench S1**. Its user sees an assembled freestanding laboratory station: centrally mounted commercial filter module, upstream non-potable feed path, downstream sampling path, two distinct pressure observation locations, an accessible sample container, a maintenance area, a panel, a catch tray, and conspicuous non-potable labeling. These are tied by the same source functional specification and acceptance plan from PRs #236–239.

## Digital physical assembly

| System element | Actual source/representation | Verification status |
|---|---|---|
| Filter housing | Pentair Pentek 158007 Blue/Clear 10-inch, 3/8-inch NPT; externally bounded at Ø118 × 308 mm | Manufacturer reference, **external envelope only**, no internal/seat details |
| Filter medium | Pentair Pentek P5 155014-43, nominal 5 µm | Manufacturer reference; not physically installed or treatment-tested |
| Mounting | Manufacturer-listed Slim Line bracket candidate 244047 | **No documented 158007-specific hole pitch or load rating.** Product scene shows no actual drill pattern |
| Structure | Concept panel 450 × 12 × 716 mm, drip tray 450 × 260 × 14 mm | Native OpenSCAD geometry; no material strength/fastening validation |
| User interface | Two distinct symbolic inlet/outlet pressure dial locations | **No calibrated instruments, taps or fittings selected** |
| Wet path | Feed → pressure observation → OEM housing → outlet pressure observation → sample valve → sample cup | Directional **layout concept**; no routed pressure-tight hose network |
| Maintenance | Housing z=228–536 mm, illustrative lower service region z=78–228 mm | OpenSCAD bounding space, **NOT manufacturer's required sump removal clearance** |
| User controls | Non-potable marking, setup/observe/sample/service workflow | Proposed operating procedure, **not completed or cleared for use** |
| Functional targets | 0.5 L/min input and ≥70% removal of a **defined non-potable turbidity challenge** | **Unmeasured targets**, no efficacy claim |

The scene may visually imply mechanical/fitting connections that cannot be proven from datasheets. Every such visual is explicitly a **diagrammatic system-design placeholder**, never a manufacturer CAD model or pressurized functioning assembly.

## Generated product-level deliverable

Source: `examples/products/clearbench_s1_product.json`

Generator: `whole_product_sample.py`

1. Revalidates the exact **same-run** assembly receipt, unresolved physical/electrical/hydraulic gates and source hash.
2. Validates full product requirements, operator journey, **11-item product BOM**, external assembly dimensions, instrument allocation and no physical authorization.
3. Verifies the conceptual feed-to-sample directed path **cannot bypass the treatment node**. This is process-topology analysis only; it does not validate real plumbing or bypass seal.
4. Generates an assembled `PRODUCT_SCENE.scad`, a source-bound `PRODUCT_BOM.json`, `PRODUCT_OPERATOR_WORKFLOW.json`, `PRODUCT_ARCHITECTURE.json` and `PRODUCT_RECEIPT.json`.
5. The fifth CI stage calls the **real OpenSCAD toolchain** to render an assembled 1500 × 1150 PNG and five named STL concepts: tray, back panel, OEM housing *envelope*, illustrative service volume and sample cup. `trimesh` checks real STL extents, vertical placement, watertightness and winding. Exact file SHA-256 hashes are recorded in `PRODUCT_RENDER_EVIDENCE.json`.
6. The CI tests deliberate product graph bypasses, missing valves or observation stations, incorrect OEM part identities, fabricated mounting-hole data, falsely passed water tests and manufactured physical authority. Any fails the whole product demonstration.

The electronic architecture is deliberately **passive/instrumentation only**: a manual-filter station doesn't require custom firmware unless monitoring actually justifies it. If a future version chooses electronic sensors, H-Splicer can reuse ESP32 firmware/native electrical verification, but it should not bolt on electronics for the sake of boasting coverage.

## Reproduction

With the preceding assembly evidence already generated:

```sh
python scripts/build_clearbench_product_001.py \
  --assembly-package .cache/hs-filter-assembly-interface-gate \
  --product examples/products/clearbench_s1_product.json \
  --out /tmp/clearbench-product

python scripts/render_clearbench_product_001.py --project /tmp/clearbench-product
pytest -q tests/test_whole_product_sample.py
```

The full workflow automatically runs `function-intent → technology-screening → component native CAD → assembly interface audit → whole product design` and archives the resulting product preview/3D source/models with acceptance reports.

## Critical clarity: digital product vs real physical product

**What exists:** One complete **digital** product example, one assembled render and real OpenSCAD-generated CAD concept, a unified proposed operator process and full *role-level* BOM with vendor/catalog uncertainty explicitly labeled. It is **not** just an array of parts.

**What does not exist:** A 3D-printed, assembled or wetted physical product; verified bracket/cartridge exact-SKU fit; a pressure-rated inlet/outlet manifold; calibrated pressure instrumentation; validated 0.5 L/min operation; measured 70% turbidity reduction; actual safety compliance; a fully qualified purchasing BOM. The scene must never be exported or described as a printable/pressure-safe consumer product. Even a geometrically watertight STL does not imply a watertight physical vessel.

### Product release gates

1. Verify manufacturer's exact 158007 housing/244047 bracket and 155014-43 cartridge seating drawings and actual real fit (including rated support loads).
2. Qualify full actual fittings/tubing/valve and pressure-instrumentation BOM with documented revision/ratings.
3. Verify service accessibility including actual sump removal; no assumed hole pitch or service sweep.
4. Model **measured** pressure-flow with bounded operating conditions and controlled non-potable challenge.
5. Obtain independent supervised physical flow/leak and paired influent/effluent turbidity measurements using calibrated instruments.
6. Only then consider a reviewed, physically manufacturable stand/packaging specification; pressurized pressure-containing parts remain OEM-provided unless independently engineered/certified.

This example establishes a reusable **product-synthesis layer** between HS's functional system and its domain-specific native toolchains. Its natural next milestone is an independently reviewed complete physical engineering sample, once genuine parts and verified interface dimensions are available. No physical operations are authorized by this PR.
