# Fabricator digital thread

This tranche connects Hardware Splicer's engineering artifacts to the physical-operator control plane without turning tool output into physical truth or authority.

## Flow

```text
mission/revision
  -> EDA/CAD/simulation
  -> retained engineering artifacts
  -> machine-executable artifacts where appropriate
  -> #125 physical plan + human grant
  -> dispatch
  -> #126 raw observation/evidence
  -> reviewable revision
```

The two artifact classes are intentionally separate:

- `EngineeringArtifactStore`: non-executable retained bytes such as STEP/STL source geometry, PCB fabrication request ZIPs, BOMs, EDA/manufacturing bundles and handoff bundles.
- `PhysicalArtifactRegistry`: executable machine inputs such as G-code, firmware, motion plans and bounded instrument recipes.

A non-executable artifact never becomes executable merely because an agent can discover it.

## Mechanical path

Hardware Splicer's existing Mecha-Splicer/OpenSCAD output is registered by id. `MechanicalFabricationPipeline` performs:

1. registered `.scad` -> OpenSCAD fixed-argv render;
2. exact STL/3MF bytes -> registered slicer profile;
3. slicer receipt binds source geometry, profile and exact G-code hash;
4. exact G-code is registered in `PhysicalArtifactRegistry`;
5. physical staging/start still belongs to the separate human-gated physical-fabrication workflow.

`FreeCadExportOperator` provides a precision-CAD bridge for registered FCStd documents. A fixed server-generated script exports STEP or STL and stores the result as a non-executable engineering artifact. Agent-supplied Python/macros are not accepted.

## Electronics/manufacturing path

`KicadFabricationPipeline` runs fixed KiCad exports for Gerbers, drill data, component positions and BOM. It then creates a deterministic vendor-neutral PCB fabrication request package and stores it as `pcb_fab_request`.

The package explicitly has no selected vendor, no quote and no submitted order. Future provider adapters should consume this request rather than rebuilding fabrication intent from chat text.

## Programming/debug path

`OpenOcdProgrammerHandle` extends the generic `programmer` physical operator beyond RP-specific picotool. Target config files and binary addresses are server-owned. Firmware must already be a registered `firmware` artifact and staged before flash. The existing physical dispatcher is responsible for consuming the exact human grant before the handle is called.

OpenOCD v0 requests program+verify and deliberately omits reset/run after programming.

## Industrial/workcell observation

- MTConnect: read-only HTTP/XML observation retained in the physical observation store.
- OPC UA: agents choose configured measurement ids; endpoint, security and NodeIds remain server configuration. Live support is the optional `opcua` dependency.
- ROS 2: graph observation only (`node list`, `topic list -t`). No publish/service/action interface.
- Motion plans: JSON trajectory dry-run checks joint identity, position limits, timing and configured velocity limits. It always returns `ready_for_live_execution=false`.

## Reproducible handoff

`FabricationHandoffBuilder` produces deterministic ZIP bytes with fixed timestamps and a manifest hashing every member. `StoredHandoffService` accepts only retained engineering artifact ids, reads the private bytes server-side and stores the resulting ZIP as another immutable non-executable artifact.

This is the bridge from scattered tool outputs to one reproducible fabrication revision.

## Digital thread

`FabricationDigitalThread` is a hash-linked provenance graph over artifacts and activities. It records model/tool/dispatch/observation/evidence/human-decision classes but deliberately keeps artifact `physical_correctness=UNPROVEN` and `grants_physical_authority=false`.

Physical truth remains owned by the physical-evidence model. Physical authority remains owned by the physical-plan/grant model.

## Canonical agent surface

`/v1/fabricator/digital/*` is always present in OpenAPI but fails closed with HTTP 503 unless a server-owned `FabricatorDigitalThreadWorkbench` is injected.

The bounded manifest is `fabricator_digital_thread_manifest()`.

The agent can select registered ids and bounded specs. It cannot:

- provide executable/tool paths;
- provide network endpoints or credentials;
- provide raw OpenSCAD/FreeCAD/Python source through these routes;
- write OPC UA;
- publish ROS 2 commands;
- start robot/CNC/laser motion;
- submit a PCB order;
- mint a physical grant;
- claim that successful tool execution proves the physical object.
