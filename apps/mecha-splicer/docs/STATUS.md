# Status

Implemented (v1):
- Spec schema (enclosure + bracket)
- DFM heuristic checks (printability/fit warnings + blockers)
- BOM heuristics (fasteners/inserts)
- OpenSCAD generation
- “Mint” pipeline from RSS → categories → bundles
- Mint template selector (`--force-template`, `--list-templates`)
- Optional 3d‑splicer client (wired into spec + mint via `--use-3d-splicer`)
- Basic commerce estimates (digital pack) in bundle output
- Procurement locking (SKU overrides + buy lists + lock report)
- Distribution-ready bundle artifacts (manifest + build recipe)
- Optional OpenSCAD STL rendering (`--render-openscad-stl`)
- Standalone mechanism primitive: GT2 belt-driven linear axis (printable mounts + checks + BOM)
- Standalone mechanism primitive: T8 lead-screw axis (printable mounts + checks + BOM)
- Standalone mechanism primitive: bearing-supported rotary joint (printable block + arm + checks + BOM)
- Standalone movement primitive: GT2 belt reduction stage (plate + checks + BOM)
- Standalone mechanism primitive: servo scissor gripper (parts + checks + BOM)
- Standalone mechanism primitive: servo pan/tilt plates (parts + checks + BOM)
- Mechanism assembly placement file (`ASSEMBLY.scad`) via `assembly` spec
- Assembly mates + auto-anchors (constraint-based placement) + overlap warnings
- Print/export artifacts: `PARTS.json`, `PRINT_PLAN.md`, optional OpenSCAD→STL rendering

Missing for “Circuit‑Splicer level”:
- Real costing/commerce model for physical kits (COGS, shipping, returns)
- Mechanical catalog + Taiwan (Shopee) sourcing helpers
- CAD kernel integration (FreeCAD/STEP) and real geometry checks
- Mechanism library expansion (hinges, sliders, gear trains, linkages) + validation hooks
