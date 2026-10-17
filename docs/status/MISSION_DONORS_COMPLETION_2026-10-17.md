# Donor missions and RE findings — verified backend handover

Branch: `agent/mission-donors`, based on verified `agent/mission-step4-integration` at `819aa815`.
Nothing pushed or merged. Main, frozen mission branches and the original Step 4 WIP branch are unchanged.

## Completed

- P4: reference-only donor intake; read-only project-scoped contract resolver; frozen HS donor readings before
  acceptance, reused after interruption; explicit evidence grades and weakest-fact capability grades.
- Candidate donors_used membership, sorting and deduplication; required donor coverage at READY/NO_FEASIBLE;
  repairs cannot drop a used donor; unverified donors block READY with named missing facts.
- P5: strict agent-only finding_offered events, always re_observation, even method=document. Findings can be cited
  by needs, survive replay and never promote contracts, establish physical evidence or ground blockers.
- Donor-specific grounding only from HS's frozen reading. Invented, unused and already-measured signal concerns
  do not gain physical grounding. Unknown actual donor/signal facts can ground reverse-engineering needs.
- Human donor measurements displayed separately, with matching non-simulated envelope targets required. They
  invalidate prior checks as before but never silently promote the frozen contract.
- Existing FastAPI routes, project revisions and event-store architecture retained; no new service or parallel
  evidence store. Human acceptance/evidence routes remain outside the fabrication MCP task.

Source commits:

- `2940cf1e` — Add evidence-graded donor references and mission findings
- `1cf5a835` — Document donor mission evidence and trust boundaries

## Verification

57 new donor cases cover the feature and abuse paths, including real software-executor planner/review runs, HTTP
422 refusals, restart/replay, forged references, identity substitution, symlinks and grade laundering.

Initial test-first run: `26 failed, 4 passed, 1 warning in 5.90s`. Most failures initially stopped at the unsupported
intake boundary; this is not 26 independently reproduced defects. Four refusal controls already passed. Separate
failing regressions preceded fixes for empty/absent candidate distinctness, wrong-target/simulated donor feedback,
and unknown-direction capability grading. Supplementary coverage is not represented as fail-before evidence.

Final focused command:

```text
PYTHONPATH=src <root>/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_mission_*.py tests/test_device_agent_surface.py tests/test_mcp_backend_gateway.py tests/test_interface_contract_provenance.py --tb=short --junitxml=.cache/donors-focused.xml
286 passed, 11 warnings in 50.11s
```

Full suite, run once after final source changes:

```text
PYTHONPATH=src <root>/.venv/bin/python -m pytest -q -p no:cacheprovider tests --tb=short --junitxml=.cache/donors-full-suite.xml
2 failed, 4203 passed, 56 skipped, 124 warnings in 863.17s (0:14:23)
```

`<root>` is the shared primary Hardware-Splicer workspace, whose existing .venv supplies the interpreter.
The full XML contains all 57 donor cases. Failed test identities and assertion messages exactly match the saved
untouched-#124 baseline used in the Step 4 handover:

- test_project_intake_evidence_pack_closes_scoped_production_package
- test_project_intake_extracts_notes_into_production_evidence

Both retain their existing local production-package/KiCad failure (`assert False is True`); no additional failed
tests appeared. The assembly-geometry test passed again. The full suite is not claimed green. Remote CI has not
run on these unpushed commits. No separate browser suite, live model trial, real mission acceptance or physical
operation was invoked. No operator token was retrieved. All Codex-started test processes have exited.

## Persistence and trust limits

Existing standalone donor evidence packages had no project-scoped contract location. The resolver reads existing
InterfaceContract JSON at `<project-store-root>/<project-id>/donors/contracts/donor__<board>__<block>.json`.
It never creates, edits, promotes or imports a contract. A missing contract remains unknown. Contract writing and
review remain with their existing owning workflow; no import/promotion endpoint was added here.

Accepted measurement IDs count only if every ID resolves to a unique, hash-checked, non-simulated, passing electrical
envelope for this project and donor in the stored snapshot's
`physicalValidation.audited_physical_evidence.envelopes`. This is the location written by the canonical physical
validation API. Arbitrary snapshot dictionaries, persisted status labels and agent artifact hashes do not count.

This checks identity and envelope integrity, not instrument truth, raw-byte attestation or transcription correctness.
Someone able to PUT snapshots or write contract/evidence files remains a trusted writer and can fabricate records;
hashes are not signatures. Public mission proposals cannot assign grades, but no claim is made that all existing
project-write routes are safe against a privileged agent. See AGENT_MISSION.md for the exact limits.

Donors_used is tracking/coverage only. Donor wiring, controller compatibility, pin geometry, donor firmware and
mechanical integration are not implemented by this tranche; generated artifacts still implement library modules.
The donor reading is frozen, so later external contract changes do not retroactively affect an accepted mission.
Mission feedback never auto-promotes it. Physical correctness remains UNPROVEN and mission firmware/power flags
remain false.

Detailed per-test rules, fail-before observations and exact command results are in the worktree-local ignored
`.cache/donors-report.md`; final XML is beside it. Earlier stack context remains in
`I2C_STEP4_COMPLETION_2026-10-16.md` and `MISSION_HANDOVER_2026-10-16.md`.

## Still separate work

The accepted live reruns, remaining hardened red-team missions and upstream PR review/merges are not completed by
this backend tranche. Donor-aware planning/wiring and promotion of new physical facts need their own reviewed
implementation. RE tool execution, procurement and physical automation remain frozen for later as designed.
