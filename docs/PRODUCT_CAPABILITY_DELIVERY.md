# Product capability delivery

This document defines how Hardware Splicer presents external engines as product value rather than as a list of repositories.

## Product promise

Hardware Splicer does not need to become a second KiCad, atopile, tscircuit, agentcad, PartCAD, or fabrication suite.

It should let a user move through a coherent sequence:

1. **Describe or import** a hardware intent.
2. **Produce** an electrical, mechanical, firmware, or assembly proposal.
3. **Inspect** the proposal in formats humans can understand.
4. **Verify** it with independent tools and traceable evidence.
5. **Disposition** findings through a named review step.
6. **Package** the approved revision for fabrication, assembly, bring-up, or further engineering.

External projects perform specialist work. Hardware Splicer owns project identity, revisions, evidence, review state, and authorization.

## Capability language shown to users

The interface must not use `integrated` as a catch-all label.

| Product state | Meaning |
|---|---|
| **Core** | Required runtime used by the standard product path. |
| **Wired** | Callable from the current API or interface. |
| **Opt-in** | Callable only after explicit operator confirmation. |
| **Partial** | A bounded subset or optional enrichment is implemented. |
| **Documented sidecar** | The user can operate the external tool alongside Hardware Splicer, but HS does not execute it. |
| **Reference** | Used for architecture or interchange research only. |
| **Planned** | Accepted direction with an implementation contract, but no callable adapter. |

Every capability card must answer:

- What does the user receive?
- How is it invoked?
- Does it mutate project files?
- What runtime and license boundary applies?
- What is the maximum authority its output can acquire?
- What remains unimplemented?

## Four product workflows

### 1. Reviewable board package

**Available foundation.**

Input may arrive through compose, a supported Circuit JSON subset, or a KiCad netlist exported by tools such as SKiDL or atopile.

Deliverables:

- KiCad project files;
- ERC/DRC evidence;
- BOM and fabrication-oriented artifacts;
- browser preview through KiCanvas;
- PDF/SVG and optional assembly views.

No imported or generated design becomes authorized merely because it compiles.

### 2. Engineering review packet

**Next primary adapter.**

kicad-happy is integrated as a read-only, bounded subprocess. Its deterministic findings, assessments, confidence, evidence source, input hashes, and schema version are attached to the project.

Deliverables:

- structured schematic, PCB, Gerber, thermal and EMC findings;
- stable references to MachineProject components and interfaces when resolvable;
- unresolved-reference records when mapping is uncertain;
- human dispositions and an immutable adapter casefile.

The adapter may contribute `observed` evidence and may block release through policy. It cannot independently set `verified` or `authorized`.

### 3. Mechanical fit and enclosure handoff

**Worker foundation in progress.**

The target is a STEP-first build123d/agentcad path with CadQuery compatibility.

Deliverables:

- authoritative STEP geometry;
- STL and GLB derivatives;
- dimensions and topology metrics;
- fit/spec checks;
- visual and geometric revision diffs.

Generated Python must execute outside the API process. Multi-user or hostile-input deployment additionally requires network-disabled and filesystem-restricted containers.

### 4. Fabrication and assembly handoff

**Partial.**

The reviewed project can be packaged using KiCad CLI, optional KiKit, JLC/LCSC enrichment, InteractiveHtmlBom, and PcbDraw.

Deliverables:

- Gerbers and drill files;
- BOM and position data;
- sourcing observations;
- assembly views;
- PROJECT_PACKAGE with evidence and review state.

Sourcing availability and manufacturer formatting are observations, not fabrication authorization.

## Interface packaging

The Integration Lab becomes a **Capability Studio** over time.

The primary screen should be workflow-first:

1. Select an outcome: reviewable board, engineering review, mechanical handoff, or fabrication handoff.
2. Show required and optional capabilities for that outcome.
3. Detect runtime availability.
4. Explain skipped capabilities before execution.
5. Execute steps one at a time with visible artifacts and evidence.
6. End with a readiness summary and next blocking action.

The repository catalog remains available as a secondary technical view.

## Adapter envelope

Every external execution should produce a common envelope:

```json
{
  "adapter_id": "kicad-happy",
  "adapter_version": "upstream commit or release",
  "profile": "schematic",
  "runtime": "bounded_subprocess",
  "started_at": "ISO-8601",
  "finished_at": "ISO-8601",
  "exit_code": 0,
  "timed_out": false,
  "input_hashes": {},
  "output_hashes": {},
  "stdout_tail": "",
  "stderr_tail": "",
  "authority_ceiling": "observed",
  "artifacts": [],
  "findings": [],
  "casefile": null
}
```

Adapter output never silently upgrades project authority. Promotion occurs only through Hardware Splicer policy and review actions.

## Implementation order

1. Land the capability-oriented catalog and workflow metadata.
2. Integrate kicad-happy as the first read-only evidence adapter.
3. Finish isolated CAD execution and add STEP-first mechanical output.
4. Add upstream Circuit JSON interoperability fixtures and explicit support levels.
5. Build the workflow-first Capability Studio interface.
6. Add optional atopile and Konnect sidecar handoff helpers.
7. Evaluate PartCAD interchange only after revision and identity ownership are stable.
