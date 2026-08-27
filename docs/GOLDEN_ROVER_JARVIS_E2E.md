# Golden Rover JARVIS End-to-End Validation

This validation closes the first complete Hardware Splicer software loop on the existing reference-rich indoor inspection rover case.

It is a validation tranche, not a new agent feature.

## Complete revision trace

The harness creates one isolated project and requires this exact sequence:

1. Revision 1 — source-rich rover project persisted.
2. Revision 2 — one source-grounded architecture candidate and one `run_compose` proposal persisted.
3. Revision 3 — a named human reviewer accepts the proposal for software preview only.
4. Revision 4 — the accepted compose preview fails on a deliberate, deterministic 3.3 V logic-threshold error.
5. Revision 5 — one bounded repair successor is appended while the failed action and artifact remain immutable.
6. Revision 6 — JARVIS answers a readiness question using the failed tool result and pinned rover source, reports blockers, and emits one typed `prepare_verification` proposal.
7. Revision 7 — the exact revision-6 project state is exported as a deterministic Engineering Package record.

The package is then replayed using source revision 6. Replay must verify the existing ZIP and return idempotently without creating revision 8.

## Rover evidence

The validation reuses:

- `examples/robot_reference_corpus/robot_reference_catalog.json`
- `examples/robot_reference_e2e/reference_rich_indoor_inspection_rover.json`
- the existing guided-planner rover E2E
- the pinned fixture URDF
- firmware and ROS interface manifests
- declared public repository, documentation, assembly, CAD-index, research, and video references

The base guided-planner E2E must still pass before the JARVIS trace begins.

## Deterministic injected AI

The validation does not depend on a live model provider.

Three schema-shaped fixtures are injected:

- project proposal;
- failure repair;
- JARVIS decision briefing.

The responses still pass through the production parsers, evidence registries, action allowlist, revision persistence, human-decision boundary, and authority checks.

This proves integration deterministically. It does not benchmark live-model quality.

## Deliberate preview failure

The compose callable is intentionally injected to raise:

`golden rover logic threshold unresolved: verify motor-driver VIH`

Before raising, the fixture verifies that:

- `allow_llm_first` is false;
- `export_gerber` is false.

The production tool executor must persist the failure as a bounded software artifact with SHA-256 and byte count.

The repair layer must reference that exact failed action and create a separate child session. It must not rewrite the failure.

## JARVIS evidence contract

The briefing must cite:

- the persisted failed tool-result identity;
- the pinned rover URDF source identity.

It must report that the rover is not ready for physical bring-up and append a typed `prepare_verification` proposal. The proposal returns to normal `proposed` state and receives no decision or tool result.

## Engineering Package checks

The verified package must contain:

- project brief;
- requirements;
- source manifest and conflicts;
- architecture candidates;
- human decisions;
- action trace;
- deterministic tool results;
- repair lineage;
- JARVIS conversation briefings;
- blockers;
- authority state;
- artifact references;
- manifest and README.

The validation checks:

- package ID and exact source revision;
- ZIP SHA-256 and byte count;
- required file set;
- failed action and failed tool result;
- repair parent/child lineage;
- JARVIS turn and recommended action identity;
- explicit blocker aggregation;
- manifest file count;
- raw rover source omission;
- verified idempotent replay;
- all physical authority remaining closed.

## Outputs

The strict runner writes:

- `GOLDEN_ROVER_JARVIS_E2E.json`
- `GOLDEN_ROVER_JARVIS_E2E.md`
- `GOLDEN_ROVER_ENGINEERING_PACKAGE.zip`

The GitHub workflow uploads all three as the `golden-rover-jarvis-e2e` artifact.

## Run locally

```bash
PYTHONPATH=src python scripts/run_golden_rover_jarvis_e2e.py \
  --strict \
  --out /tmp/golden-rover-jarvis-e2e
```

Focused subprocess contract:

```bash
PYTHONPATH=src python -m pytest -q tests/test_golden_rover_jarvis_e2e.py
```

## Workflow coverage

`.github/workflows/golden-rover-jarvis-e2e.yml` runs:

- Python compilation of the owning modules;
- the strict golden rover runner;
- the golden subprocess test;
- the existing rover, orchestrator, preview, repair, conversation, and package API tests;
- AI Studio repair-lineage frontend contract;
- JARVIS Console frontend contract;
- Engineering Package workspace frontend contract;
- strict TypeScript validation;
- production Next.js build;
- artifact upload.

## Authority boundary

This run performs no:

- arbitrary command execution;
- live-model call;
- LLM-first compose;
- Gerber export;
- device access;
- fabrication;
- firmware flashing;
- power-on;
- motion;
- operational approval;
- release approval.

A passing report proves that the revisioned software workflow and reproducible handoff remain coherent. It does not prove that real rover hardware is safe, complete, fabricated, powered, moving, operational, or releasable.
