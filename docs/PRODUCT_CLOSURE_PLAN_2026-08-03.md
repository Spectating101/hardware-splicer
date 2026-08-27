# Hardware Splicer product closure plan — 2026-08-03

This document is an executable consolidation contract, not a feature wishlist.
It defines what must be true before Hardware Splicer can be described as a
coherent public alpha rather than a collection of individually strong branches.

## Product thesis

Hardware Splicer owns canonical project identity, evidence, uncertainty,
review, authority, and final packaging. External electrical, firmware,
mechanical, sourcing, and analysis tools may create proposals, artifacts,
observations, or evidence; they never silently authorize fabrication, flashing,
bench power, or release.

## Consolidation graph

The intended integration order is:

1. `agent/interchange-review-workflow-20260802` — Circuit JSON intake and
   engineering review delivery.
2. `agent/electrical-authoring-spine` — includes the complete bench-capture,
   machine-authoring, and machine-evidence stack from PR #10 plus canonical
   electrical components, pins, nets, power domains, deterministic editing,
   and ERC.
3. `agent/product-launch-consistency-20260731` — one documented product
   launcher.
4. `agent/isolate-cad-execution-20260731` — bounded generated-CAD subprocess
   execution before any additional mechanical agent features.

PR #10 is not an independent merge target because its head is an ancestor of
PR #11. PRs #16 and #17 remain recovery branches until their combined successor
is green. PR #18 is not an implementation base; only non-duplicative product
language may be retained.

## Required closure gates

### Gate 1 — Combined repository verification

- Full Python suite passes.
- Product UI tests and production build pass.
- KiCad engine, DRC, fabrication, netlist, geometry, casefile, evidence,
  security, live-smoke, and exploration gates pass.
- No skipped external runtime is presented as locally certified.

### Gate 2 — Durable-project compatibility

Every persisted project envelope must have an explicit schema version. New
machine, electrical, interchange, review, and mechanical payloads must satisfy:

- older snapshots still load without dropping unknown fields;
- migrations are deterministic and idempotent;
- unsupported future versions fail with a structured error;
- migration tests use committed historical project fixtures;
- saving a migrated project records the source and target schema versions.

### Gate 3 — Cross-domain identity

The project must be able to trace an engineering object across relevant
representations without relying on display names alone:

- MachineProject component ID;
- electrical component and pin IDs;
- KiCad reference, symbol, footprint, and net;
- BOM line and manufacturer part number;
- firmware board, constant, and physical pin;
- mechanical body, connector, mount, or keep-out feature;
- external finding and review disposition;
- bench measurement target;
- packaged artifact and revision hash.

Unresolved mappings remain explicit and block stronger claims where required.

### Gate 4 — One operator journey

The normal product surface must expose one project-status model with:

- current stage and next recommended action;
- required, optional, unavailable, and completed capabilities;
- blockers and unresolved assumptions;
- evidence and review state;
- artifact downloads;
- release and power-on boundaries.

Specialist pages may remain, but a user must not need repository architecture
knowledge to complete the primary intake → design → review → verify → package
flow.

### Gate 5 — Runtime capability truth

For every optional backend, Hardware Splicer reports separately:

- discovered;
- configured;
- version-compatible;
- tested successfully on this machine;
- used successfully on this project.

The canonical capability report records executable path, version/commit,
supported schema range, delivery mode, license boundary, security profile,
last run, and setup remediation. Missing optional tools produce structured
`skipped` results rather than false failures or implied support.

### Gate 6 — Manufacturing reconciliation

Packaging must cross-check at minimum:

- build-graph instance counts against BOM quantities;
- schematic references against PCB footprints;
- PCB footprints against placement records;
- firmware pin maps against compiled electrical nets;
- connector mating pairs against harness instructions;
- mechanical fastener and mount counts against assembly instructions;
- source revision hashes against every generated manufacturing artifact.

A contradiction blocks packaging; it is not merely another warning document.

### Gate 7 — Mechanical truth

The first mechanical product contract is STEP-first and includes:

- source geometry and coordinate-system provenance;
- board outlines, holes, connectors, keep-outs, mounts, clearances, and
  tolerances;
- measurable dimensions and topology checks;
- revision comparison;
- STL/GLB only as delivery derivatives;
- fit evidence linked back to the canonical project.

Generated Python remains bounded by subprocess limits and must move to a
network-disabled, filesystem-restricted container before hostile multi-user
execution is claimed.

### Gate 8 — Firmware-to-bench traceability

A tested firmware claim records source revision, toolchain, dependency lock,
build command, binary hash, flash result, hardware revision, pin-map hash,
configuration, logs, procedure revision, instrument identity/calibration, and
verification result.

### Gate 9 — Physical and outsider proof

Before broad outreach:

- one founder-assisted physical golden case completes print/fabricate → wire →
  flash → measure → power-on;
- one simpler second case proves repeatability;
- one person who did not build Hardware Splicer completes a bounded zero-help
  dry run from clean installation to project package;
- failures and interventions are retained as casefiles and product metrics.

### Gate 10 — Release discipline

A public alpha has one release-candidate branch, one version, one launcher, one
capability matrix, one claims matrix, clean installation, license inventory,
security profile, migration note, support boundary, and known-limitations list.

## Explicit non-priorities until closure

- additional live-edit MCP integrations;
- broad multi-user SaaS;
- Blender as engineering truth;
- autonomous fabrication or power authorization;
- more LLM agents without a measured closure benefit;
- support for every CAD/ECAD interchange format.

## Immediate execution sequence

1. Green the combined Circuit JSON + engineering-review PR.
2. Build a release-consolidation branch from that passing head.
3. integrate PR #11 as the single bench/evidence/electrical stack;
4. apply launcher consistency and CAD isolation;
5. add historical project migration fixtures and cross-domain identity tests;
6. add capability-state and manufacturing-reconciliation contracts;
7. implement the STEP-first mechanical contract;
8. complete physical and outsider proof;
9. freeze alpha claims and packaging.
