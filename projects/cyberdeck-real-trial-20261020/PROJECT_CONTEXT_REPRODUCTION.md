# Real cyberdeck board: isolated-file vs original-project DRC reproduction

Observed on the Optiplex at 2026-10-20, using the exact RPI_DEV GitHub cyberdeck source obtained in the [real trial](./README.md). This is an **empirical discrepancy**, not a synthetic test or evidence of device readiness.

## Input and tool

- Upstream project: `sector07-dev/RPI_DEV`, cloned at `ebdfcff` for the real cyberdeck trial.
- Original board `RPI_Dev_1.kicad_pcb` (original 222,472-byte file), with adjacent `RPI_Dev_1.kicad_pro` (15,504 bytes) in the repository extraction.
- KiCad CLI version: 9.0.2.
- `kicad-cli pcb drc --exit-code-violations -o /tmp/hs-cyberdeck-pro-context-drc.txt RPI_Dev_1.kicad_pcb` run **inside the directory containing the original `.kicad_pro`** returned exit code 5 and **16** findings: `lib_footprint_issues:15` and `lib_footprint_mismatch:1`.
- Newly implemented opt-in `hardware_splicer.kicad_registered_source_check.check_kicad_bytes` invoked on the **same exact PCB bytes**, with the companion `.kicad_pro` absent from its temporary directory, returned exit code 5 and **211** findings: `clearance:195`, `lib_footprint_issues:15`, `lib_footprint_mismatch:1`.
- The schematic via the same HS function reported **43** ERC findings and successfully exported **26** component entries and **47** nets. The original independent ERC check also reported 43 findings.

## Finding and required fix

**HS's standalone PCB source checker is not producing an equivalent DRC to the original project.** The isolated-file check loses design/project settings that materially change the result. Treat the 211 figure as *not comparable to project-level DRC*, and do **not** claim that the third-party PCB has 195 genuine clearance defects. The source parser's functionality is still an improvement over merely recording file hashes, but the new DRC surface needs either a full companion KiCad project context or an explicit `project_context_missing` / incomplete-design-check qualifier; it must not promote standalone figures to manufacturing acceptance.

This is an integration failure directly exposed by exercising real engineering files, and a product bug requiring correction on the **same cyberdeck project**, not justification to add unrelated benchmarks.

## Still-unmet original cyberdeck goal

No independently verified cyberdeck power/interface BOM, dimensioned enclosure, source-backed adapted PCB, matching manufacturing output, simulated firmware or functioning physical device. An HS tool check is one part of engineering validation, **not completion of the engineering objective**.
