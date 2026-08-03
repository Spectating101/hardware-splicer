# Source-Agnostic Engineering Benchmark

This benchmark tests whether Hardware Splicer can do more than reproduce a known robot from a repository or video.

The ceiling is an unfamiliar physical system with incomplete, conflicting, or failure-derived evidence that must be transformed into a bounded engineering candidate for a new user need.

## Evidence channels

The benchmark treats all engineering media as entries in one source graph:

- repositories and release histories;
- CAD, drawings, schematics, PCB files, BOMs, and datasheets;
- manuals, papers, service notes, and issue discussions;
- videos, photos, and operator observations;
- direct measurements, telemetry, test logs, and prior project snapshots;
- user requirements and donor-hardware inventories.

A source URI is not engineering truth. Every source must retain identity, version or hash, claims, and an authority ceiling. Conflicting claims must remain visible until explicitly dispositioned.

## Four modes

### Reconstruction

Build one internally coherent project from mutually incompatible revisions. The fixture deliberately combines legacy and newer Pupper claims so the system must select a revision boundary instead of mixing actuator, frame, compute, and control architectures.

### Requirement-driven synthesis

Design a compact indoor inspection rover from width, threshold, payload, runtime, noise, speed, budget, and safety constraints. There is no canonical repository, tutorial, or video to copy.

### Donor repair and splicing

Recover a useful rover from a damaged chassis, partly undocumented electronics, a burned driver, and a mismatched motor. The system must retain only measured-compatible donor blocks and produce a current-limited bring-up path.

### Field evolution

Revise a previously working rover after a camera mast causes tipping and logic-rail brownouts. The system must pin the baseline revision, connect measurements and telemetry to failure hypotheses, propagate affected subsystems, and define regression scope before field return.

## Scoring dimensions

Each case is evaluated for:

1. structured requirements;
2. retention of engineering-source identities;
3. pinned source provenance and authority ceilings;
4. explicit conflict identity and disposition;
5. candidate-machine synthesis;
6. donor reuse and splice mapping where required;
7. baseline-to-candidate impact analysis where required;
8. identity continuity across evidence and design objects;
9. visible uncertainty and unresolved information;
10. verification, safety, and authority boundaries.

A high score is not fabrication, power-on, or field authorization. Physical evidence remains required.

## Run

```bash
python scripts/benchmark_source_agnostic_engineering.py
```

## Expected first-pass finding

The current intake planner should synthesize a conventional requirement-only rover and provide useful evidence gates. It is expected to lose source provenance, contradiction records, cross-source canonical identity, and explicit field-revision impact. Repair may recover some donor mapping through the existing salvage stack, but undocumented donor interfaces must remain unresolved rather than guessed.

These failures are the product roadmap. The benchmark is designed to remain stable while source graph, conflict resolution, native robot topology, change propagation, and physical-evidence support improve.
