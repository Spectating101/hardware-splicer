# Hardware Splicer + SolidCraft (formerly SolveCraft): tested integration

Execution date: 2026-10-20. Official upstream:
https://github.com/tangency-labs/solidcraft
Upstream revision e4d9015. SolidCraft v0.16.2 release, MIT OR Apache-2.0.
Release archive SHA256 verified against publisher checksum.

## Division of responsibilities

Hardware Splicer owns requirements, evidence and provenance, donor
characterization, compatibility, electrical/SPICE/control and physical
engineering authority gates.

SolidCraft owns the parametric mechanical CAD session, timeline,
assemblies and STEP export. It has a desktop and web frontend and a
working JSON-command/MCP interface.

SolidCraft should become HS's mechanical engineering workspace, not its
evidence authority or electrical simulator.

## Actual engineering fix tested

The canonical HS planner historically classified an explicitly
stationary barcode label feeder as a rover. This branch provides
functional-first decomposition and a separate functional requirement
oracle. A stationary indexing cell gets five functions: item reading,
local decision/logging, material motion, independent motion inhibition
and protected power. A stationary pump gets fluid-handling functions,
not a barcode scanner. An unspecified machine stays unresolved.

The canonical planner now records and rejects an irrelevant rover
topology when the user declares stationary-only operation. It omits the
erroneous robotics_project compile specification, preserves raw
diagnostic provenance, and retains missing physical evidence gates.
Existing claim/hash/conflict provenance protection remains in place.

This corrects the observed domain error, NOT arbitrary general
expertise across all kinds of hardware.

## Real SolidCraft command and MCP execution

The test case has explicitly supplied conceptual dimensions:
120 x 80 x 25 mm. These are arbitrary SOFTWARE TEST inputs, not
measurements from any broken device.

HS generated four native SolidCraft commands:
sketch.create, sketch.rectangle.two_point, sketch.finish,
solid.extrude.

Actual official SolidCraft CLI v0.16.2:
- Returned successful four-command execution.
- Saved an editable .solidcraft document with actual Sketch and
  ExtrudeFeature timeline rows.
- Exported a real STEP file.
- Native eval measured bbox [0,0,0] to [120,80,25] and volume 240000 mm3.
- Rendered a 900x650 screenshot through SolidCraft.

Actual SolidCraft MCP stdio server:
- Started and negotiated protocol 2025-06-18.
- Listed 15 tools.
- Ran the same four commands through MCP batch.
- Measured the same 240000 mm3 result through MCP measure.

Actual artifacts are in examples/solidcraft/native_trial:
- SOLIDCRAFT_CONCEPT.commands.json
- SOLIDCRAFT_CONCEPT.solidcraft
- SOLIDCRAFT_CONCEPT.step
- SOLIDCRAFT_CONCEPT.png

The reproducibility/provenance summary with artifact SHA-256 is
in docs/evaluations/SOLIDCRAFT_FUNCTIONAL_ARCHITECTURE_TRIAL_2026-10-20.json.

## New Hardware Splicer entrypoints

HS SDK: prepare_solidcraft_workspace(scenario=...)
HS MCP: hs_prepare_solidcraft_workspace

The response includes source-integrity evaluation and a functional
subsystem graph. It emits a SolidCraft CAD script ONLY when the
scenario provides explicit, finite concept_envelope_mm fields:
width/depth/height (1..2000 mm). The original unowned marketplace
donors have no known dimensions, so no geometry is produced from them.

Run the fixture locally:

    PYTHONPATH=src python -m scripts.run_solidcraft_workspace_trial --case examples/solidcraft/declared_conceptual_envelope.json --out /tmp/hs-solidcraft

Test against an already trusted installed SolidCraft CLI:

    PYTHONPATH=src python -m scripts.run_solidcraft_workspace_trial --case examples/solidcraft/declared_conceptual_envelope.json --out /tmp/hs-solidcraft --cli /path/to/solidcraft-cli

Upstream's documented GUI-to-MCP bridge is:

    solidcraft --control 7878
    solidcraft-cli mcp --connect 127.0.0.1:7878

A live graphical SolidCraft desktop session was NOT launched in
the current trial; headless CLI and MCP were actually executed.

## Fork versus adopt

Recommend ADOPT VIA MCP FIRST, FORK ONLY FOR NATIVE HS UI WORK.
Upstream is active and implements far more CAD infrastructure than
HS needs to reproduce. Upstream documents a future plugin architecture,
but its docs/plugins.md is a design proposal, NOT a verified runtime
for an HS plugin today.

The likely long-term UI has the editable SolidCraft CAD workspace
plus HS evidence/claims, candidate interfaces, cost/part sourcing,
CAD-to-electrical bindings, repair workflow and verification gates
as a sidecar or native fork sidebar.

## Critical limitations

- No salvage donor purchased, measured, repaired or wired.
- No electrical rating, pinout, mechanism dimension or component fit
  was inferred from seller advertisements.
- No actual novel composite machine constructed.
- Functional domain selection covers selected explicit classes only.
- Upstream current source needs Rust >=1.95, host has 1.89; we tested
  the published prebuilt CLI instead of claiming a source build.
- Model and MCP functionality proved; physical engineering authority
  remains blocked until trusted instrumentation and verification.

Verdict: real CAD/MCP interoperability demonstrated. New fully
functional physical product still UNPROVEN.
