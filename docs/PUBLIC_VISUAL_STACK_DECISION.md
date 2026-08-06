# Public Visual Stack Decision

Hardware Splicer should reuse public rendering and conversion projects wherever they solve a file-format or visualization problem. Hardware Splicer should own only the cross-domain project semantics that those tools do not provide.

## Product boundary

Hardware Splicer owns:

- canonical object identity across system, schematic, PCB, 3D, manufacturing, assembly, evidence, and bring-up views;
- evidence provenance and authority ceilings;
- revision history and immutable deterministic results;
- visual proposal and repair lineage;
- JARVIS explanations and proposed actions attached to selected objects;
- physical-authority gates.

Hardware Splicer does not need to own:

- native KiCad parsing and faithful display;
- PCB drawing primitives;
- Gerber rendering;
- generic STEP triangulation;
- generic graph pan/zoom/selection;
- assembly-BOM highlighting;
- native KiCad ERC, DRC, export, and manufacturing generation.

## Approved public stack

### System canvas: React Flow

Already present in the frontend dependency graph. Use it for the canonical cross-domain graph and visual proposal overlays.

### Native KiCad viewer: KiCanvas

Use a self-hosted, pinned KiCanvas bundle behind a narrow adapter. Read-only only. KiCanvas never owns project state or editing authority.

### Proposal schematic and PCB: tscircuit viewers

Use Circuit JSON as a candidate/proposal representation, not the sole source of truth. Conversion into KiCad remains a deterministic accepted action followed by native KiCad validation.

### Manufacturing: tracespace

Use for Gerber and drill rendering after deterministic export. Exported manufacturing files are separate evidence objects from the source KiCad design.

### Assembly: InteractiveHtmlBom

Generate deterministically on the backend and embed as a restricted assembly surface. Initially treat output as an artifact, not canonical project state.

### Mechanical and PCB 3D

Use the existing React Three Fiber stack for cross-view selection and overlays. Use public importers or tscircuit 3D only behind adapters. STEP/OpenCascade licensing must be reviewed before redistribution.

### Deterministic engines

Keep KiCad CLI, KiBot, KiKit, PcbDraw, and related tools behind explicit accepted-action boundaries.

## Adapter contract

Every visual adapter consumes a sanitized artifact descriptor and canonical object mappings. It may emit selection and viewport events. It may not mutate project truth directly.

Required fields:

- adapter ID and version;
- artifact ID, type, hash, and project-relative path;
- source revision;
- canonical component/net/interface mappings;
- read-only or proposal-edit capability;
- external-network requirement;
- license notice;
- authority effect, always `none` for viewers.

## First integration tranche

1. Replace the Studio's card-dominant center with a React Flow system canvas.
2. Synchronize selected canonical object into the JARVIS/right inspector.
3. Show evidence, failure, and proposal overlays on nodes and edges.
4. Add view tabs with explicit readiness states:
   - System: active now;
   - KiCad: adapter contract ready, bundle pending pinning;
   - Proposal: tscircuit adapter contract ready, dependency pin pending;
   - 3D: existing R3F foundation;
   - Gerber: tracespace adapter planned;
   - Assembly: InteractiveHtmlBom artifact planned.
5. Do not add editing or physical authority.

## Non-goals

- building a browser KiCad clone;
- replacing KiCad as authoritative ECAD;
- treating a rendered image as engineering proof;
- allowing an embedded viewer to modify persisted state;
- allowing JARVIS to silently commit visual changes;
- making an external cloud service necessary to open private project artifacts.
