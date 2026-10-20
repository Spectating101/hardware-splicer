# Real cyberdeck source-processing correction — 2026-10-20

**New HS capability, not a completed engineering device.** Source-level result is reproducible using the canonical FastAPI ingestion/project storage path and a new sibling-preserving registered-source bundle operation.

## What was actually run

- Registered four unchanged public source files from the actual `sector07-dev/RPI_DEV` clone: `RPI_Dev_1.kicad_sch`, `RPI_Dev_1.kicad_pcb`, **companion** `RPI_Dev_1.kicad_pro`, and `Front Case.stl`.
- Used the HS source ingestion endpoint to persist source IDs and SHA256-addressed blob content into an isolated HS project store. Then called the new `/v1/projects/{project_id}/engineering/source-bundle/check` route, which re-reads only registered hashes, stages sibling KiCad files and runs `kicad-cli 9.0.2` against the project. It exports and parses a real KiCad XML netlist containing component reference/value/footprint and named net/pin connections. It extracts **raw, unitless** STL triangle bounds using the registered mesh bytes.
- The second call returned the stored result without mutating the project. Initial source project revision 1; four registered sources to revision 5; analysis stored at revision 6.
- Actual replay command: `PYTHONPATH=src .venv/bin/python scripts/replay_real_cyberdeck_source_project.py --source-dir /tmp/hs-capability-trial-20261020/reference/extracted --out-dir /tmp/hs-real-cyberdeck-replay-20261020`. The original trial files are on the authorized Optiplex only; no third-party CAD was copied into Git.

| Actual result | New HS report |
| --- | ---: |
| ERC findings | 43 |
| PCB DRC findings | 16 |
| Netlist components | 26 |
| Netlist connections / nets | 47 |
| STL triangles | 5,180 |
| STL raw coordinate spans | [223, 17, 138.61] (UNITS UNKNOWN) |

Most KiCad errors are unresolved library/footprint references in this tool environment. The source files provide a real connector/switch/control PCB, **not** a verified complete keyboard, compute, display or battery design. No flight or power authorization is involved.

## Prior failure repaired and remaining truth limits

Standalone temporary-board DRC reported **211** because it lacked the original project settings; project-aware DRC correctly reproduces **16**, identical to independent earlier control. No source check is allowed to claim equivalence when companion project configuration is missing. Source signatures, registered hashes, and safe filenames are enforced; readings remain `declared` design evidence, not electrically measured evidence.

This does not auto-create a new PCB, mechanical adapter, compatible BOM, powered device or saleable artifact. That remains the next distinct orchestration and engineering problem.

**Audit data:** original replay bundle details and exact per-file hashes are retained in `/tmp/hs-real-cyberdeck-replay-20261020/real_source_execution.json` on Optiplex. This file includes derived component/net records, not raw upstream source bytes.
