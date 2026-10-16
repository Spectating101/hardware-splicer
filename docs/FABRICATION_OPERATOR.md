# Fabrication Operator v0 — physical work without giving the agent physical authority

Hardware Splicer can now reason through a fabrication mission, but mission acceptance is deliberately software-only. This operator layer is the first bridge from an evidence-governed mission to a machine that can create a physical artifact.

The first operator is a 3D printer because its boundary is unusually clean: HS can prepare a file, inspect a printer and monitor a job without granting the agent permission to make the machine move or heat. A physical `start` or `resume` crosses a separate authority boundary.

## Authority model

Mission acceptance does **not** authorize fabrication.

A print start needs a short-lived, one-shot `hardware_splicer.fabrication_grant.v1` issued by a human operator and bound to all of:

- project id;
- mission id;
- printer/operator id;
- exact action (`start` or `resume`);
- SHA-256 of the exact staged G-code.

The grant is consumed **before** the physical command is sent. If the network fails after the printer receives the command but before HS receives the response, HS will not automatically retry with the same authority. A person must decide whether a new grant is safe.

`pause` and `cancel` are safety-reducing controls over a print that was already started under human authority and do not require new authority. `resume` does.

No printer observation or successful print changes `physical_correctness`: it remains `UNPROVEN`. Fabrication success and engineering correctness are different claims.

## v0 normalized surface

The code lives in:

- `fabrication_operator.py` — persistent human physical grants;
- `printer_operator.py` — normalized printer job boundary and backend adapters;
- `printer_transport.py` — configured HTTP transport for a real printer endpoint.

The transport accepts an operator-configured HTTP(S) base URL and headers, supports JSON requests and multipart G-code upload, and deliberately performs no printer discovery. Credentials are not part of mission data and the repository contains no endpoint or secret. Tests use `httpx.MockTransport`, so CI cannot contact a real printer.

The first backend mappings are:

### OctoPrint

- stage: upload to `/api/files/local` with `select=true`, `print=false`;
- observe: `/api/job` and `/api/printer`;
- start: `POST /api/job` with `{"command":"start"}`;
- pause/resume/cancel through the job command API.

### Moonraker / Klipper

- stage: `/server/files/upload` with `print=false`;
- observe: `/printer/objects/query?print_stats&virtual_sdcard&extruder&heater_bed`;
- start: `/printer/print/start?filename=...`;
- pause/resume/cancel through the corresponding print endpoints.

The printer adapters depend only on the injected transport. Importing them does not open a socket or discover a printer. A live connection exists only when server/operator configuration deliberately constructs `HttpxPrinterTransport` with a real endpoint.

## Intended mission loop

```text
FabricationMission
    |
    +-- enclosure / part artifact
    |
    +-- slicer operator (next tranche)
    |       -> G-code + slicer receipt
    |
    +-- printer.stage_gcode
    |       -> PreparedPrint {artifact hash, printer, remote path}
    |
    +-- printer.status / preflight
    |
    +-- AWAIT HUMAN FABRICATION GRANT
    |
    +-- printer.start(grant)
    |
    +-- status / camera / telemetry
    |
    +-- completed / failed fabrication observation
    |
    +-- mission/project revision records physical result
            -> accept, measure, diagnose, redesign or reprint
```

The mission state machine does not yet gain an `AWAITING_HUMAN_FABRICATION_APPROVAL` terminal/phase in v0. That is intentional: #122 is still establishing the mission truth boundary. The printer layer is stacked on #122 and proves the physical authority contract independently before mission semantics are widened.

## What comes next

1. Add a slicer operator (PrusaSlicer CLI first, CuraEngine as a second codec) that produces G-code plus an immutable receipt: source geometry SHA, slicer/profile identity, material, machine profile and output SHA.
2. Add a server-only printer registry that supplies endpoint/credentials to `HttpxPrinterTransport`. Agent/MCP surfaces may inspect and stage, but the human grant-mint endpoint must not be agent-callable.
3. Add mission/project events for `fabrication_prepared`, `fabrication_started`, `fabrication_paused`, `fabrication_completed`, `fabrication_failed` and physical observations. Those events are evidence; none grant engineering truth.
4. Add camera/telemetry ingestion and bounded failure classification so a failed print can generate a reviewable design revision rather than an opaque chat retry.
5. Only after a real printer dry run, decide whether to admit a reusable generic `physical_operator` MCP task for CNC, laser, programmers, bench instruments and robotics.

## Safety / scope boundary

v0 does not:

- start a real printer in CI or tests;
- store printer credentials or a printer address in the repository;
- expose grant minting to an AI agent;
- infer that a successful print is dimensionally correct;
- authorize flashing, energising electronics, cutting, CNC or robotics;
- retry an ambiguous physical start automatically.

The design rule is the same one used by the mission runtime: **the agent may decide what to try; HS decides what the evidence supports; a person decides when software may cause a physical action.**
