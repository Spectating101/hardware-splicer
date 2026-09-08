# Machine Workbench v0 — Architecture

**Status:** implementation blueprint only.
**Date:** 2026-08-29

## Goal

Promote the current PCB-centric CAD surface into a machine-level engineering workbench without rewriting the existing renderer.

Workbench v0 is a **read/inspect/understand** milestone first. It should make Hardware-Splicer's machine, evidence, interface, and authority models visually legible before adding direct CAD editing.

## Default layout

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Project / revision / release state / authority summary / command palette│
├─────────────────┬─────────────────────────────────────┬──────────────────┤
│ MACHINE TREE    │                                     │ INSPECTOR        │
│                 │         SPATIAL VIEWPORT            │                  │
│ ▾ Deck-001      │                                     │ selected entity  │
│  ▸ Compute      │    assembly / PCB / imported CAD   │ provenance       │
│  ▸ Display      │                                     │ evidence         │
│  ▸ Input        │                                     │ interfaces       │
│  ▸ Power        │                                     │ unresolved       │
│  ▸ Thermal      │                                     │ authority        │
│  ▸ Enclosure    │                                     │ actions          │
├─────────────────┴─────────────────────────────────────┴──────────────────┤
│ Evidence │ Interfaces │ Constraints │ Verification │ History │ Alternatives│
└──────────────────────────────────────────────────────────────────────────┘
```

Docking/layout should be owned by `dockview-react`, with a serialized default layout and user persistence.

## Component architecture

```text
MachineWorkbench
├── WorkbenchHeader
│   ├── ProjectIdentity
│   ├── RevisionState
│   ├── AuthoritySummary
│   └── CommandPalette
├── DockWorkspace
│   ├── MachineTreePanel
│   ├── SpatialViewportPanel
│   │   └── SpatialViewport
│   │       ├── MachineAssemblyScene
│   │       ├── PcbSpatialAsset adapter -> existing PcbViewport concepts
│   │       ├── ImportedMeshSpatialAsset
│   │       ├── InterfaceOverlay
│   │       ├── EvidenceOverlay
│   │       └── ConstraintOverlay
│   ├── EntityInspectorPanel
│   ├── EvidencePanel
│   ├── InterfacePanel
│   ├── ConstraintPanel
│   ├── VerificationPanel
│   ├── HistoryPanel
│   └── AlternativesPanel
└── WorkbenchStore (Zustand)
```

## Shared selection contract

Every panel should use one canonical selection model instead of inventing local selection state.

```ts
type WorkbenchSelection = {
  projectId: string;
  entityType:
    | 'project'
    | 'subsystem'
    | 'component'
    | 'interface'
    | 'constraint'
    | 'verification'
    | 'evidence'
    | 'spatial_asset';
  entityId: string;
  spatialTargetIds?: string[];
};
```

Tree click, viewport click, issue click, evidence click, and inspector navigation all update the same selection.

## Spatial asset adapter

Do not force every engineering object into PCB geometry.

```ts
type SpatialAsset = {
  id: string;
  entityId: string;
  kind: 'pcb' | 'mesh' | 'brep_tessellation' | 'primitive' | 'keepout' | 'interface';
  transform: Transform3D;
  authority: 'unknown' | 'proposed' | 'declared' | 'observed' | 'measured' | 'verified' | 'rejected';
  sourceRef?: string;
  geometryRef?: string;
  metadata?: Record<string, unknown>;
};
```

The current PCB renderer becomes a specialized adapter. Future STEP imports and generated enclosures use other adapters while sharing selection, camera, overlays, and authority semantics.

## Workbench store slices

Use existing Zustand rather than introducing another state framework.

Recommended slices:

- `projectSlice` — active MachineProject/revision;
- `selectionSlice` — canonical selected entity;
- `visibilitySlice` — hidden/isolated/ghosted entities;
- `viewportSlice` — camera preset, explode amount, active lenses;
- `layoutSlice` — serialized Dockview layout identity;
- `alternativesSlice` — active architecture candidate/Pareto selection;
- `authoritySlice` — current blockers and release summary.

Do not duplicate backend evidence truth in frontend state. Frontend state may cache/projection only.

## v0 lenses

The viewport should start with semantic lenses that HS can already support:

1. **Authority** — verified / proposed / unresolved / blocked;
2. **Provenance** — donor / new / generated / external;
3. **Interfaces** — visible links between endpoints, colored by evidence/contract state;
4. **Constraints** — spatial keepouts/collisions/blockers where geometry exists;
5. **Verification** — highlight entities touched by selected verification method;
6. **Subsystem** — isolate selected machine subsystem.

Existing PCB voltage/current/thermal/BOM lenses remain available when the active spatial asset supports them.

## v0 interaction set

Required:

- orbit / pan / zoom;
- selection;
- tree ↔ viewport synchronization;
- frame selected;
- isolate;
- hide/show/ghost;
- subsystem visibility;
- explode amount;
- orthographic/top/front/side presets;
- blocker focus;
- evidence/authority lenses;
- persisted panel layout.

Deferred until v1+:

- direct transforms;
- snapping;
- measurement authoring;
- section planes;
- cable routing;
- articulated assemblies;
- exact CAD modification;
- enclosure generation.

## First fixture

Use `DECK-001` as a synthetic machine fixture because it contains:

- donor compute;
- donor display;
- donor input;
- new power system;
- generated enclosure;
- thermal subsystem;
- high-speed and low-speed interfaces;
- unresolved fields;
- blocking constraints.

The fixture must remain visibly marked synthetic. It is a UI stress case, not physical evidence.

## First real asset

Embed the existing PCB scene as the first real spatial engineering object. Selecting a PCB component should still expose existing issue/analysis behavior while also participating in the machine-level selection/provenance/authority model.

## Implementation order

1. Introduce Dockview shell with placeholder panels.
2. Extract shared workbench store + selection contract.
3. Adapt current PCB viewport into `SpatialViewportPanel` without behavior regression.
4. Implement hierarchical Machine Tree and Inspector against synthetic DECK-001.
5. Add authority/provenance visual states.
6. Add interface overlay and blocker focus.
7. Add bottom Evidence/Interfaces/Constraints/Verification tabs.
8. Preserve existing CAD route until the workbench reaches parity; do not delete `/cad` early.

## Acceptance bar

Workbench v0 is successful when a new evaluator can answer, without opening JSON:

- What machine am I looking at?
- Which parts are donor/new/generated?
- What subsystem does this object belong to?
- What does HS know about it?
- What remains unresolved?
- Which interfaces connect it?
- Why is the project blocked or allowed to proceed?
- What evidence/verification supports that state?

That comprehension bar matters more than feature count.
