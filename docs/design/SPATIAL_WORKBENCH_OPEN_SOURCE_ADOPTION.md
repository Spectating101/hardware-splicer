# HS Spatial Workbench — Open-Source Adoption Plan

**Status:** design / dependency selection only. No frontend implementation is authorized by this document alone.
**Date:** 2026-08-29

## Decision

Do **not** build a browser CAD/engineering workbench from first principles.

Hardware-Splicer already has a strong React/Three.js foundation. The next frontend should be assembled from mature open-source primitives for docking, CAD import, spatial queries, measurement, selection, and exact geometry, while HS owns the distinctive layer: evidence state, authority state, donor provenance, interface contracts, requirements, alternatives, and lifecycle history.

The target is not "Blender in a browser." It is:

> **A spatial evidence-and-authority workbench for engineering physical systems.**

## 1. Existing HS assets to keep

Current frontend already includes Next.js 15 / React 19, Three.js + React Three Fiber, Drei, React Three Postprocessing, Zustand, XYFlow, and a real 3D PCB viewport with selection, camera controls, engineering/production render modes, issue overlays, explode state, and analysis lenses.

Therefore the correct move is to **promote the current PCB viewport into one spatial asset type inside a larger machine workbench**, not replace it.

## 2. Adoption matrix

| Need | Candidate | Licence | Decision | Why |
|---|---|---|---|---|
| Dockable IDE/CAD shell | `dockview-react` | MIT core | **ADOPT FIRST** | React 19 support, tabs, splits, floating groups, popouts, serialization, zero-dependency core; already used by modern Cascade Studio. |
| Alternative dock shell | `flexlayout-react` | MIT | HOLD | Mature and capable, but Dockview maps more naturally to IDE/CAD workbench behavior. |
| 3D rendering / selection | existing R3F + Three.js + Drei | MIT | **KEEP** | Current HS renderer is already sophisticated; no reason to rewrite. |
| Fast mesh picking / spatial queries | `three-mesh-bvh` | MIT | **ADOPT EARLY** | Accelerated raycasting, distance/intersection queries, foundation for large assemblies, measurements and clipping helpers. |
| STEP / IGES / BREP import | `occt-import-js` | LGPL-2.1 | **ADOPT AS ISOLATED ADAPTER** | Browser-native OpenCascade importer; good for tessellating engineering files. Keep behind worker/adapter boundary and comply with LGPL distribution obligations. |
| Exact B-rep CAD generation/editing | `replicad` | MIT | **PHASE 2** | Library-first OpenCascade abstraction; suitable for generated enclosures, brackets and exact geometry without writing an OCCT wrapper ourselves. |
| Full browser CAD reference | Cascade Studio / `cascade-core` | MIT | **REFERENCE / EVALUATE EMBEDDING** | Excellent interaction reference: OpenCascade, Dockview, Monaco, history timeline, STEP/IGES/STL import/export, agent API. Do not fork whole app unless embedding proves cheaper than integration. |
| General model import/viewer patterns | Online 3D Viewer | MIT | **REFERENCE / REUSE PATTERNS** | Mature file import, assembly exploration, multi-format viewer architecture. |
| STEP viewer UX patterns | `STEP-viewer` | MIT app + LGPL OCCT import | **REFERENCE** | Already implements assembly tree, isolate/frame, measurement, annotations, section/explode controls, view cube. Strong source of interaction patterns. |
| AI browser CAD reference | Sphaire | MIT | **REFERENCE** | Useful reference for browser CAD + agent + deterministic validation loop. |
| Agent-first CAD reference | PartMode | AGPL-3.0 | **REFERENCE ONLY — DO NOT COPY CODE** | Strong conceptual overlap but copyleft licence is undesirable for HS unless deliberately accepted. |
| Assembly tree | custom HS tree initially; consider `react-complex-tree` | MIT | **CUSTOM V0 / LIB LATER** | HS needs domain-specific badges/state. Current tree is simple enough to replace locally; bring a general tree library only if hierarchy/drag/drop complexity warrants it. |
| Huge list/tree virtualization | `@tanstack/react-virtual` | MIT | LATER | Useful when machine/component/evidence trees become large. |
| Command palette | `cmdk` | MIT | **LIKELY EARLY** | Natural CAD/IDE command surface for focus/isolate/explode/evidence lenses/actions. |
| Resizable fixed panes only | `react-resizable-panels` | MIT | SKIP if Dockview adopted | Dockview already solves the larger docking problem. |
| Mesh CSG | `three-bvh-csg` | MIT, experimental | REFERENCE / NON-AUTHORITATIVE PREVIEW ONLY | Fast visual CSG but explicitly experimental; never treat as proof-grade exact CAD. Exact geometry should go through Replicad/OpenCascade. |

## 3. Recommended stack by phase

### Workbench v0 — shell + spatial truth

Add only what gives immediate product value:

1. `dockview-react`
2. `three-mesh-bvh`
3. optionally `cmdk`

Keep `@react-three/fiber`, `@react-three/drei`, `three`, `zustand`, `@xyflow/react`, and current `PcbViewport`.

Do **not** add OpenCascade/Replicad yet unless v0 requires real STEP import.

### Workbench v1 — engineering file ingestion

Add `occt-import-js` behind a Web Worker / lazy-loaded adapter, STEP/IGES/BREP → assembly tree + tessellated geometry, and metadata/provenance binding from imported geometry to HS entities.

### Workbench v2 — exact generated geometry

Add `replicad` / OpenCascade worker, exact enclosure/bracket/keepout generation, STEP export, and exact geometry evidence references.

Do not use mesh CSG as authoritative manufacturing geometry.

## 4. Interaction patterns worth reusing

### From Cascade Studio

- Dockview-based movable panels;
- modeling/history timeline;
- code/parameter/viewport synchronization;
- persistent layout;
- agent API concept.

HS adaptation: replace CAD construction history with **engineering/evidence state history**; agent actions remain bounded by HS authority contracts.

### From STEP-viewer / Online 3D Viewer

- assembly hierarchy;
- click tree ↔ select geometry;
- frame selection;
- isolate / hide / ghost;
- view cube;
- distance/angle measurement;
- section planes;
- explode assemblies;
- annotations.

HS adaptation: annotations become evidence / unresolved-field / blocker overlays; explode preserves interface relationships and provenance; section/isolate can follow subsystem or evidence state, not only geometry.

### From Sphaire

- human/agent operation on the same editable model;
- explicit deterministic validation between AI generation and export.

HS adaptation: the deterministic validator is HS's existing evidence/authority stack; visual confidence must never upgrade authority on its own.

## 5. HS-specific workbench semantics

Third-party libraries provide interaction mechanics. HS must provide the semantic layer.

### Geometry state

- **verified / measured** — normal solid rendering;
- **declared / approximate** — semi-transparent;
- **proposed** — ghost/wireframe;
- **rejected** — hidden by default or red strike/outline;
- **unresolved region** — striped/amber overlay;
- **blocking collision / constraint** — red spatial overlay.

### Interface state

Every visible interconnect may expose protocol, electrical contract, mechanical contract, evidence count, unresolved fields, authority state, and linked verification methods.

### Physical authority

Spatial actions are not equivalent to authorization. A user/agent may move a proposed component in the viewport without HS claiming the design is buildable. Irreversible/build/power actions remain governed by deterministic backend authority state.

## 6. Licensing boundary

Preferred direct dependencies are permissive MIT where possible.

Special handling:

- `occt-import-js` is LGPL-2.1. Use as a separately packaged/lazy-loaded adapter and retain required licence notices/source availability obligations.
- OpenCascade itself carries its own licensing obligations; verify exact packaged distribution before production release.
- PartMode is AGPL-3.0: use for product/UX research only unless HS deliberately accepts AGPL implications.
- Do not copy proprietary Dockview Enterprise behavior/code; free Dockview core is sufficient for v0.

## 7. Things we should not build ourselves now

Do not spend HS time recreating panel docking/tab management, generic transform gizmos, basic orbit/pan/zoom, STEP tessellation, generic assembly-tree mechanics, generic measurement UX, generic section planes, generic model explode algorithms, generic command palette, or an OpenCascade binding.

Spend custom engineering time on evidence overlays, authority/blocker visualization, donor provenance, MachineProject ↔ spatial entity binding, interface/evidence graph overlays, architecture alternatives / Pareto candidates, lifecycle revision history, and agent actions with bounded authority.

## 8. Immediate implementation recommendation

Build one `MachineWorkbench` shell using Dockview and the existing PCB renderer.

Default panels:

- **Machine Tree** — left;
- **Spatial Viewport** — center;
- **Inspector** — right;
- **Evidence / Interfaces / Constraints / Verification / History** — bottom tabset.

First stress fixture: synthetic `DECK-001` cyberdeck, because it exercises multi-subsystem hierarchy and unresolved interfaces.

First embedded real engineering object: existing PCB viewport.

The v0 success criterion is not CAD authoring. It is:

> A user can load one machine, select any subsystem/component/interface, see it spatially, understand its provenance/evidence/authority state, isolate blockers, and move between machine/tree/evidence views without losing context.

Only after that works should we add direct transform/editing operations.
