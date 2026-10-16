# Mission backend transaction hardening — 2026-10-16

## Scope and integration

Branch: `agent/mission-backend-hardening`, based on the published mission runtime
at `a5eb285e6de67ff27038c468b98aeed6e8c0337a` (PR #122).

Checkpoint `f815854e` preserves Claude's eight tracked, in-flight inventory/API
fixes as they stood when this checkout was created. It is a checkpoint, not an
independent authorship claim. Claude's original worktree and canonical `main`
were not edited. Hardening commit `da92428cce783fa14ace440fd3f2232cde51933d` contains Codex's changes only;
integrators should apply that commit after the equivalent Claude inventory fixes,
not blindly replay the checkpoint over a newer Claude branch.

## Reproduced defects and fixes

- Two simultaneous executor requests could both pass the remaining-job check and
  start expensive work. The losing write would fail only after that work ran.
- An agent could repair a candidate while an earlier check was executing. That
  check could then be recorded after the repair and credited to the new spec.
- Acceptance wrote `accepted` before computing/writing `inventory_read`. A reader
  exception or worker interruption left an accepted mission without inventory;
  ordinary acceptance retry was then refused as already accepted.

Eight new regression cases failed against the inherited code before these fixes.
The final concurrency/recovery file has 13 tests, with a further HTTP contention
test in `test_mission_api.py`.

All existing-mission mutations now share a nonblocking POSIX advisory lock on the
immutable mission marker. The executor holds it from reading the candidate and
checking its budget through recording the result. Competing runs, proposals and
internal evaluation writes receive `MissionConflict`; HTTP returns 409 with
`busy`. Readers and unrelated missions remain available. Independent processes,
separate store instances, exceptions and worker exit are covered by tests.

New acceptance writes the system inventory reading first and human acceptance
last. If interrupted between them, execution remains refused. Retrying acceptance
uses the frozen reading rather than re-running the parser, then records acceptance
once. Existing historical logs are not rewritten or silently backfilled.

## Verification

Run from the checkout with `PYTHONPATH=src` and the project's Python environment:

```sh
python -m pytest -q tests/test_mission_concurrency.py
python -m pytest -q tests/test_mission*.py tests/test_device_agent_surface.py \
  tests/test_device_draft*.py tests/test_project_store.py tests/test_project_api.py \
  tests/test_machine_project*.py tests/test_machine_evidence*.py \
  tests/test_machine_release*.py tests/test_project_thread*.py \
  tests/test_project_review*.py tests/test_mcp_backend_gateway.py
```

Inherited mission/API/device-agent baseline: 154 passed. Final broader backend
regression: 358 passed. The final concurrency/recovery file separately passes all
13 tests (also included in the broader result). Existing deprecation
warnings remain. This is not a full-repository or browser-suite result.

## Boundaries

- No live model invocation, external provider interaction, flashing or power-on.
- Project snapshots, revisions and physical authority are unchanged.
- `physical_correctness` remains `UNPROVEN`.
- This is per-mission serialization on a compatible POSIX filesystem, not a durable
  execution queue. As before, budgets count recorded evaluations, not interrupted
  or unrecorded attempts. Worker exit releases the lock, but does not manufacture
  a completed result or refund/charge an attempted run.
- Hosts without POSIX locking can still import/read the API; mission mutations
  refuse rather than run without serialization.
- `READY_FOR_HUMAN_BUILD` retains its existing plan/engineering/inventory meaning.
  These changes do not assert that firmware export, emulator execution, silicon,
  electrical behavior or physical assembly have been validated.
- Neither `main` nor the active Claude branch is merged or pushed by this tranche.
