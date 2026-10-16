# Hardware Splicer fabrication pipeline v0

This document defines the first trusted path from an HS-generated geometry artifact to a configured 3D printer.

## Boundary

The fabrication path is deliberately split into three authority domains:

1. **agent/software authority** may choose among registered capabilities, create geometry, request slicing, stage an exact sliced artifact, and read machine status;
2. **HS deterministic authority** validates hashes, registry membership, profile/printer binding and the immutable provenance chain;
3. **human physical authority** alone may mint a one-shot grant that starts or resumes a physical print.

Mission acceptance does not grant physical authority.

## Canonical flow

```text
geometry bytes
    |
    | SHA-256
    v
server-approved SlicerProfile
    |
    | configured slicer runner
    v
SlicerReceipt
  - geometry SHA-256
  - profile SHA-256
  - slicer name/version
  - target printer id
  - output G-code SHA-256
  - bounded estimates
    |
    v
SlicedArtifact
    |
    | FabricationPipeline re-hashes G-code
    | and verifies receipt/printer binding
    v
configured PrinterRegistry entry
    |
    | stage only; never auto-start
    v
StagedFabrication
  - PreparedPrint
  - SlicerReceipt
  - canonical receipt SHA-256
    |
    v
human one-shot FabricationGrant
  - project
  - mission
  - printer
  - action
  - exact G-code SHA-256
    |
    v
printer start/resume
```

## Server-owned registries

The printer registry is the only source of network endpoints and credentials. Agent-facing descriptors expose only the stable printer id, display name, backend and capabilities. They do not expose `base_url`, headers or API keys.

The slicer profile registry holds the actual printer/material profile bytes. Agent-facing descriptors expose only the profile id, printer id, material label and profile SHA-256.

An agent therefore selects `printer_id` and `profile_id`; it does not provide an arbitrary URL, credential, executable path or profile file.

## Slicing

`SlicerOperator` accepts only a server-created `SlicerProfile`. Its receipt binds the exact input geometry and profile to the exact output G-code. The initial real runner is PrusaSlicer with a fixed argv shape and `shell=False` semantics through `subprocess.run`.

The runner executable and declared version are server configuration. No model value becomes a shell command.

## Staging and actuation

`FabricationPipeline.stage_sliced` is the intended agent-facing staging path. It refuses:

- a receipt for another printer;
- G-code whose bytes no longer match the slicer receipt;
- a staged artifact whose printer-side hash differs from the receipt;
- a mutated slicer receipt at later start time.

Raw `FabricationPrinter.stage_gcode` remains an internal/trusted-server primitive and should not be exposed directly through the future MCP task.

Starting and resuming consume a human grant before the network command is sent. Ambiguous network failure therefore cannot be retried with the same authority.

Pause and cancel remain risk-reducing controls and do not require a new grant.

## Truth boundary

Printer status and print completion are observations only. They never promote:

```text
physical_correctness = UNPROVEN
```

A later physical-feedback tranche may accept human measurements, camera/inspection evidence or instrument observations. Those observations must remain provenance-typed and must not be confused with software verification.

## Next gate

Before exposing the printer through mission MCP, add a bounded server API over the registries/pipeline with these properties:

- agents can list safe printer/profile descriptors;
- agents can request slice, stage, status, pause and cancel;
- agents can request that a human approve a start, but cannot mint that grant;
- start/resume require an already-issued human grant;
- raw printer URLs, credentials, raw profile bytes and raw `stage_gcode` are not agent-visible;
- every mission event records the geometry hash, profile hash, G-code hash, receipt hash and printer id.

Only after that contract is tested should a live printer be configured.
