# CAD / ECAD agent ecosystem adapter audit — 2026-07-31

## Decision

Hardware Splicer should **not** attempt to become every CAD, ECAD, rendering, simulation, and agent tool inside one process.

It should remain the canonical project, provenance, evidence, and authorization spine, while external projects are integrated as bounded executors, analyzers, compilers, or viewers.

The governing rule is:

> External tools may produce proposals, artifacts, observations, and evidence. They may not silently upgrade authority or replace `MachineProject` / `PROJECT_PACKAGE` truth.

This audit replaces the weaker idea that every repository exposing an MCP server is a direct competitor or should be embedded. A live KiCad editor, a code-first circuit compiler, a deterministic review tool, a parametric CAD runtime, and a Blender renderer solve different problems and require different trust boundaries.

---

## What the ecosystem actually contains

### 1. Read-only engineering analyzers

These parse existing engineering files and produce structured findings without modifying the source design.

**Best current candidate: [kicad-happy](https://github.com/aklofas/kicad-happy)**

- MIT licensed.
- Pure-Python deterministic extraction from KiCad schematic, PCB, and Gerber files.
- Agent skills for Codex, Claude Code, Gemini CLI, and other coding agents.
- Structured analysis for power trees, passive networks, protection, buses, thermal, EMC, BOM, datasheets, SPICE, and manufacturing readiness.
- Explicitly separates deterministic extraction from LLM reasoning.
- Read-only by default, which aligns with Hardware Splicer authority boundaries.

**Fit:** very high. Hardware Splicer should ingest the analyzer JSON as `observed` evidence, preserve detector/confidence/source metadata, and attach findings to requirements, interfaces, components, and release blockers.

**Do not:** copy prose findings into authority state without retaining the raw analyzer output and version.

### 2. Electrical authoring and compiler systems

These provide stronger electrical representations, package ecosystems, or web-native render/export stacks.

#### [atopile](https://github.com/atopile/atopile)

- MIT licensed.
- Declarative electronics language with modules, interfaces, units, tolerances, assertions, constraint solving, component selection, and KiCad layout integration.
- Stronger than Hardware Splicer at code-first electrical authoring and reusable circuit packages.

**Fit:** high as an optional authoring/compiler backend.

**Boundary:** Hardware Splicer exports only an electrically authorized subset to `.ato`, invokes `ato build` externally, and re-ingests generated KiCad/check artifacts as evidence. Atopile does not own donor identity, physical observations, bench evidence, or release authorization.

#### [tscircuit](https://github.com/tscircuit/tscircuit) and [Circuit JSON](https://github.com/tscircuit/circuit-json)

- MIT licensed ecosystem.
- TypeScript/React circuit authoring, browser schematic/PCB/3D viewers, routing, BOM, Gerber, SPICE, KiCad conversion, STEP and glTF conversion.
- Circuit JSON is a broad low-level representation spanning source, schematic, PCB, CAD, simulation, warning, and error elements.

**Fit:** very high for interchange, web rendering, and independent conversion/check paths.

**Current Hardware Splicer status is narrower than the catalog implies.** The existing importer only recognizes a minimal subset of `source_component` and `schematic_trace`, and assumes connected port identifiers have a `REF.PIN` shape. It does not yet implement the full source-port graph, PCB geometry, CAD elements, warnings, simulations, or round-trip identity.

**Boundary:** Circuit JSON is an interchange and presentation representation, not Hardware Splicer’s authority ledger. Stable Hardware Splicer IDs and provenance must survive mapping in a sidecar manifest or extension fields.

### 3. Live ECAD mutation tools

These let an agent modify an open KiCad session or underlying KiCad files.

#### [Konnect](https://github.com/mixelpixx/Konnect)

- Native KiCad 10 plugin and MCP server.
- Rust single-binary architecture.
- Uses the official KiCad IPC API for live PCB changes.
- Uses atomic S-expression writes for schematics and `kicad-cli` for checks/exports.
- On-demand toolsets, call observability, design reviews, routing, sourcing, and manufacturing export.
- Beta status.
- AGPL-3.0 with commercial licensing.

**Fit:** high as an optional user-installed sidecar; low as code to embed.

**License boundary:** do not copy, vendor, link, or derive the product core from Konnect without an explicit licensing decision. Hardware Splicer may interoperate over process/MCP boundaries and implement independently derived architectural lessons.

**Lessons to adopt independently:**

- Official KiCad IPC instead of deprecated SWIG paths.
- One clearly owned session per project.
- Atomic schematic writes and external-edit detection.
- Toolset discovery/context economy instead of exposing hundreds of tools at once.
- Structured recent-call logs and failure observability.

#### [KiCAD-MCP-Server](https://github.com/mixelpixx/KiCAD-MCP-Server)

- MIT predecessor with a large tool surface.
- Useful compatibility reference and proof of demand.
- Its history documents why tool count is not sufficient: broken schematic workflows, ineffective CI, SWIG ownership failures, stale-session writes, and silent backend failures were all real failure modes before later fixes.

**Fit:** compatibility/reference only. New first-class work should target KiCad 10 IPC or a process-isolated file workflow.

### 4. Mechanical CAD authoring and validation

These create real BREP/STEP geometry and provide agent feedback loops.

#### [build123d](https://github.com/gumyr/build123d)

- Apache-2.0.
- Modern typed Python CAD over OpenCascade.
- Appropriate default for new code-first BREP geometry; CadQuery can remain a compatibility path.

#### [agentcad](https://github.com/jdilla1277/agentcad)

- Apache-2.0.
- External CLI/MCP designed for coding agents.
- Versioned STEP output, PNG rendering, mesh exports, geometry metrics, validation, named-part inspection, specification checks, and visual/geometric diffs.
- Uses build123d by default and keeps CadQuery compatibility.

**Fit:** highest immediate mechanical-runtime candidate. Prefer an external subprocess adapter over duplicating its entire runtime.

#### [CAD Skills / text-to-cad](https://github.com/earthtojake/text-to-cad)

- MIT.
- Codex/Claude skills for CAD, viewers, STEP part sourcing, DXF, URDF/SRDF/SDF, slicing, G-code, and fabrication handoff.
- Includes benchmark prompts and inspectable outputs.

**Fit:** high as an optional agent skill and benchmark corpus. Skills guide workflows; they do not establish engineering authority.

#### [build123d-mcp](https://github.com/pzfreo/build123d-mcp)

- Apache-2.0.
- Persistent build/render/measure/validate/export session for agents.
- Its security documentation correctly notes that Python `exec`, AST filters, restricted builtins, and daemon-thread timeouts are not a production sandbox; timed-out work may continue and memory remains unbounded.

**Fit:** useful protocol and workflow reference. Production integration must use a killable subprocess/container boundary, not in-process execution.

#### [PartCAD](https://github.com/partcad/partcad)

- Apache-2.0.
- Product-package/digital-thread system covering requirements, CAD, electronics, software, BOM, sourcing, manufacturing, and validation.
- Supports CadQuery, build123d, OpenSCAD, STEP, KiCad, assembly definitions, documentation, and rendering.

**Fit:** future package import/export and comparison target. It overlaps Hardware Splicer’s project/package layer more than it overlaps the compile engine. Do not absorb it wholesale before defining identity and authority mappings.

### 5. Presentation and scene-generation tools

#### [Blender MCP](https://github.com/ahujasid/blender-mcp) and related projects

These are excellent at producing visually persuasive scenes, renders, materials, camera views, and generated meshes. They are not automatically manufacturable CAD and commonly permit broad Python or socket execution.

**Fit:** optional presentation adapter only.

**Boundary:** Blender outputs may be attached as `preview` artifacts. They cannot satisfy fit, dimensional, fabrication, or release gates unless independently measured against authoritative STEP/BREP geometry.

---

## Current Hardware Splicer gaps exposed by this audit

### Mechanical execution is unsafe and overstated

`apps/3d-splicer/src/core/cadquery_generator.py` writes generated Python to a temporary file and executes it in the API process with `runpy.run_path()`.

Current consequences:

- Generated code shares the server process, filesystem access, environment variables, network access, and Python runtime.
- There is no hard timeout or process termination.
- A crash or infinite computation can contaminate or block the service.
- The primary artifact is STL rather than a versioned STEP/BREP source of truth.
- The surrounding README calls the system production-ready even though GLB output is still a placeholder and the planner is presently heuristic/mock.

This is a P0 correction, before adding any new mechanical agent UI.

### Circuit JSON interoperability is only a local round trip

The current test exports Hardware Splicer’s own simplified Circuit JSON and imports the same shape back. That proves internal symmetry, not compatibility with real tscircuit output.

A real adapter must be tested against upstream fixtures and preserve:

- source component and source port identity;
- nets and traces through official ID references;
- PCB components, ports, pads, vias, traces, holes, keepouts, and board outline;
- errors and warnings;
- CAD/3D model references;
- units and coordinate transforms;
- manual-edit conflict information;
- simulation experiments/results where present;
- Hardware Splicer stable IDs, provenance, and authority in an explicit sidecar mapping.

### The integration catalog conflates availability with trust

Statuses such as `wired`, `partial`, and `opt_in` report whether a hook exists, but not what authority the result may receive.

Each adapter needs two independent dimensions:

1. **Execution maturity:** reference / planned / experimental / tested / production.
2. **Maximum authority:** preview / proposed / observed / measured / verified.

No external adapter should default to `authorized`.

---

## Target adapter architecture

Every adapter invocation should produce an envelope shaped like:

```json
{
  "adapter_id": "kicad-happy",
  "adapter_version": "2.x",
  "invocation_id": "stable-id",
  "input_artifacts": [
    {"path": "board.kicad_sch", "sha256": "..."}
  ],
  "outputs": [
    {"path": "analysis/schematic.json", "sha256": "...", "kind": "analysis"}
  ],
  "findings": [],
  "execution": {
    "started_at": "...",
    "finished_at": "...",
    "exit_code": 0,
    "timed_out": false,
    "isolated": true
  },
  "authority": {
    "maximum": "observed",
    "reason": "deterministic read-only analysis; requires independent gate for verification"
  }
}
```

Required properties:

- input and output hashes;
- exact tool version and command profile;
- bounded working directory;
- sanitized environment;
- hard-kill timeout;
- captured stdout/stderr without mixing structured output and diagnostics;
- explicit license and install mode;
- deterministic cache key;
- no implicit authority upgrade;
- casefile on failure;
- human-readable and machine-readable outputs.

---

## Prioritized implementation sequence

### P0 — correctness and safety

1. Replace in-process CadQuery execution with a killable subprocess runner.
2. Make STEP the primary mechanical artifact; derive STL/GLB previews from it.
3. Add geometry metrics, validation, and version-to-version diff artifacts.
4. Correct public claims around 3D-Splicer, FEM, GLB, and the mock planner.
5. Split integration status from maximum-authority status.

### P1 — highest-value external capability

1. Add a read-only `kicad-happy` analyzer adapter and ingest its JSON as evidence/findings.
2. Upgrade Circuit JSON support using real upstream fixtures and official ID relationships.
3. Add an `agentcad` or direct build123d subprocess backend behind a stable mechanical adapter contract.
4. Expose adapter runs through `MachineProject` proposals and immutable evidence records.

### P2 — authoring and live-edit sidecars

1. Add `.ato` export/import experiments for an electrically authorized subset.
2. Define a KiCad live-session sidecar contract compatible with KiCad 10 IPC tools such as Konnect, without embedding AGPL code.
3. Re-run Hardware Splicer compile, ERC/DRC, semantic diff, and review gates after every accepted external edit.

### P3 — broader product package and presentation

1. PartCAD package import/export mapping.
2. CAD Skills installation/runbook and benchmark corpus.
3. Blender presentation adapter, explicitly preview-only.
4. URDF/SDF/SRDF exports after mechanical identity and coordinate systems are stable.

---

## Acceptance gates

### Mechanical adapter

- Generated code never executes in the API process.
- Timeout kills the process tree.
- No inherited API keys or unrelated environment variables.
- Inputs and outputs remain inside controlled roots.
- STEP exists and passes OpenCascade validity checks.
- Requested dimensions and holes are machine-measured.
- STL/GLB are derivatives linked to the STEP hash.
- A/B geometry diff is generated for revisions.

### Circuit JSON adapter

- Imports at least three unmodified upstream fixtures.
- Round-trips stable component, port, and net identities.
- Reports unsupported element types instead of silently dropping them.
- Preserves warnings/errors as evidence.
- Coordinate and unit transformations have fixture tests.
- Exported output renders in an upstream viewer and converts back without topology loss inside the supported subset.

### KiCad analysis adapter

- Read-only behavior is asserted by pre/post file hashes.
- Tool version and detector confidence are retained.
- Findings map to stable MachineProject objects.
- Analyzer output cannot directly authorize a release.
- Independent `kicad-cli` ERC/DRC remains required.

### Live-edit sidecar

- Project/session ownership is explicit.
- External-edit conflicts fail closed.
- Every accepted edit creates a new revision and semantic diff.
- Recompile and checks run before authority changes.
- Tool calls and changed artifacts are auditable.

---

## Bottom line

Hardware Splicer is not losing because many repositories can show a PCB, generate a 3D object, or let Codex call KiCad.

It loses only if it keeps rebuilding their execution surfaces badly while failing to connect them to its stronger evidence and authorization model.

The winning architecture is:

**best available external authoring/execution tools**
→ **bounded adapters with hashes, versions, isolation, and casefiles**
→ **Hardware Splicer canonical project + evidence graph**
→ **independent compile/check gates**
→ **reviewed, inspectable `PROJECT_PACKAGE`**

That is a more defensible system than another all-powerful MCP server, but only after the current unsafe mechanical execution and shallow interchange claims are corrected.
