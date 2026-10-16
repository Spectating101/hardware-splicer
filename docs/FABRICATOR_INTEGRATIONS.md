# Fabricator Integrations v0

This tranche extends Hardware Splicer from bounded physical execution and feedback into a capability-driven digital-to-physical toolchain. It does **not** make connector availability equivalent to fabrication correctness.

## Architecture

```text
Fabrication Mission / later project revision
        |
        v
capability requirements
        |
        v
server-owned capability registry
        |
        +--> KiCad CLI ---------> ERC / DRC / manufacturing receipts
        +--> ngspice -----------> model/simulation receipt
        +--> MTConnect ---------> retained read-only machine observation
        +--> G-code dry-run ----> bounds/hazard/opaque-semantics report
        +--> OpenPnP package ---> simulator-ready job package
        |
        v
existing physical_fabrication control plane
        |
        v
human-bound physical actuation
        |
        v
camera / serial / SCPI / machine observations
        |
        v
PhysicalEvidenceRecord
        |
        v
reviewable physical revision proposal
```

## Trust boundaries

- Agents select stable ids and bounded parameters only.
- Executable paths, KiCad files, SPICE files, MTConnect URLs, OpenPnP roots, machine envelopes and credentials are server configuration.
- KiCad/ngspice subprocesses use fixed argv and `shell=False`.
- MTConnect is GET/read-only and raw XML is retained in the physical observation store.
- CNC/laser G-code is analyzed only; this tranche has no live CNC/laser transport.
- OpenPnP integration emits a simulator/job package only; it cannot power or play a real job.
- Simulation, dispatch success and observation capture keep `physical_correctness = UNPROVEN`.
- Failed promoted physical evidence may ground a revision proposal. The proposal never mutates the project automatically.

## Capability registry

`FabricationCapabilityRegistry` provides a vendor-neutral server-owned capability graph. A mission can request capabilities and numeric minimums rather than naming a specific machine. Public descriptors contain ids, capabilities, limits and simulated/availability flags but no endpoints or credentials.

Example requirement:

```json
{
  "required_capabilities": ["additive_fabrication", "pla"],
  "kind": "printer",
  "numeric_minimums": {"build_x_mm": 200},
  "allow_simulated": false
}
```

## KiCad

`KicadCliOperator` supports registered projects only. v0 provides:

- schematic ERC with JSON report and violation exit code;
- PCB DRC with JSON report and violation exit code;
- Gerber export;
- drill export;
- component-position CSV export;
- STEP export.

KiCad tool output is authoritative for what KiCad checked. It does not establish physical correctness or manufacturability outside those checks.

## ngspice

`NgspiceOperator` runs registered netlists in batch mode. `report` mode retains the simulator log; `raw` mode additionally retains ngspice raw output. A successful simulation means the configured model executed, not that the physical circuit will match it.

## MTConnect

`MtconnectObserver` supports the standard read flows:

- `probe` for device/data-item description;
- `current` for the latest state snapshot;
- bounded `sample` from a sequence number.

Responses are retained byte-for-byte as machine telemetry observations. There is no write/control API in this adapter.

## CNC / laser dry-run

`GcodeDryRunAnalyzer` parses a deliberately narrow linear-motion subset and reports:

- X/Y/Z bounds;
- maximum feed seen;
- configured-envelope violations;
- hazardous M-codes;
- unsupported or opaque G-code semantics.

Arcs, probing/canned cycles, macros/expressions and unknown commands are blockers rather than guessed. `ready_for_live_execution` is always false in v0.

## OpenPnP

`OpenPnpSimulationInspector` validates a server-registered `.job.xml`, summarizes the XML structure, discovers local XML references that remain inside the registered root, and hashes the package. The output is explicitly simulator-only; feeder setup, fiducials, nozzle compatibility, placement accuracy and solder quality remain unproven.

## Physical feedback -> revision

`PhysicalRevisionProposalBuilder` reads the mission physical sidecar. Only promoted physical evidence with `passed=false` can ground `needs_revision=true`. Dispatch receipts and raw observations are provenance, not failure claims. The result is a hash-bound proposal for later P3/project-revision logic; no original mission event or project revision is changed automatically.

## Benchmarks

Three progressively harder benchmark definitions are frozen in `fabricator_benchmarks.py`:

1. `B1_CLOSED_LOOP_LOGGER` — clean-sheet EDA -> fabrication/programming -> serial/electrical/dimensional evidence -> injected failure -> revision.
2. `B2_DONOR_RECLAIM_BUILD` — donor-heavy build requiring P4/P5 evidence for reused capabilities.
3. `B3_MULTI_MACHINE_FABRICATION` — EDA, assembly package, additive/subtractive path, programming, telemetry and instrumented validation.

The harness explicitly flags false persisted physical truth. Passing the trace harness still does not substitute for real hardware acceptance.

## Deliberately not built yet

- live CNC spindle/laser control;
- live OpenPnP power/play;
- robot motion;
- arbitrary SCPI writes or bench-power enable;
- automatic camera interpretation as pass/fail;
- automatic project mutation from physical evidence;
- P4 donor capability modeling or P5 reverse-engineering findings;
- any claim of personnel, electrical, machine or functional safety certification.

Those require hardware-specific validation, manufacturer guidance, interlocks and—where consequential—professional safety engineering.
