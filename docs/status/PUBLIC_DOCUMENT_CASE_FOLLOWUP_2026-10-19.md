# Public-document case follow-up

The practical problem is not just whether an agent can use the tools. A saved
project must not hide a danger warning, and a clean partial check must not look
like a useful donor implementation. This follow-up makes those limits explicit
without changing evidence grades, physical authority or the existing READY gate.

## Scope and experiment boundary

Claude's four public-document case reports describe Samsung remote, Logitech
mouse, microwave and Canon encoder trials against `a0530015`. Those reports
are the motivation for this work, not results from the updated implementation.
The newer intact-input bundle and interactive mouse demo were not part of those
trials. Their frozen artifacts and original run records are unchanged.

This follow-up is on the existing salvage-investigation branch. It does not
create another PR, modify the mission-page frontend in PR #139, launch paid
model runs, submit anything externally or authorize hardware actions.

## Changes

1. The mission view and salvage context derive `safety_concerns` from existing
   `evidence_required / BLOCKED_UNSAFE` events. They expose the concern, original
   need sequence, declared reporter and current need state. Grounding is always
   `agent_assertion`; no keyword classifier or stronger safety evidence is
   invented. An unresolved explicit warning gets a safety-specific next-step
   hint, even after an independent candidate changes the mission phase. A blocked
   terminal no longer recommends downloading a READY package.
2. Candidates expose `donor_coverage`: used references, missing required donors
   and unverified used donors. This projection shares the canonical donor gate's
   implementation. Coverage explicitly does not establish wiring/implementation.
3. Candidates expose `spec_diagnostics`. The mission event stores unknown design
   keys; the catalog planner drops them from its normalized spec. Unknown paths
   are now reported as JSON pointers, including nested module/connection/case
   fields. No proposal content is silently removed by this change, and generic
   partial proposals remain admissible. The strict intact-reuse checker remains
   a separate scope, not mislabeled by catalog diagnostics.
4. The quickstart, compact manifest and event description explain explicit unsafe
   refusal, persisted bounded work before waiting, and how to read the new
   coverage/omission diagnostics. They do not require fabricated designs or
   alternatives when evidence cannot support them.

No new mission event type, evidence store or authority transition was added.
Views are derived from existing intake, frozen donor readings and event history.
The regression tests check unchanged old event bytes across a repair and unchanged
project state across warning recording.

## Validation and remaining limits

The new regression file is `tests/test_mission_case_regressions.py`. The initial
pre-fix run was **7 failed, 2 passed**: it reproduced missing warning/coverage/
diagnostic surfaces, while generic proposals were already accepted.

The initial focused run after implementing the projections was **174 passed**.
That included the first nine new controls plus mission storage, donor, salvage
context and onboarding tests. The next expanded run was **306 passed**.
The final run, including device planning/engineering, public API, answer and
physical-log regressions, was **599 passed, 37 warnings in 80.83s**. It includes
13 new controls in the regression file. These counts overlap; do not add them.
This is a targeted suite, not a new full-repository or live-agent result.
Warnings concern duplicate OpenAPI operation IDs and deprecated HTTP constant
names, also seen in the earlier focused runs.

Final command (use the configured test Python/environment):

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_mission_case_regressions.py tests/test_salvage_agent_onboarding.py \
  tests/test_mission_store.py tests/test_mission_donors.py \
  tests/test_mission_feedback.py tests/test_mission_executor.py \
  tests/test_mission_gate.py tests/test_mission_delivery.py \
  tests/test_mission_concurrency.py tests/test_salvage_fabrication.py \
  tests/test_intact_reuse.py tests/test_mouse_reuse_demo.py \
  tests/test_device_plan.py tests/test_device_engineering.py \
  tests/test_mission_api.py tests/test_mission_answer.py \
  tests/test_mission_physical_log.py
```

Important limits:

- An agent can still omit a warning entirely. An empty `safety_concerns` list
  means no explicit warning recorded, not that HS assessed the goal as safe.
- Declared event authors are not independently authenticated by this projection.
- Advisory diagnostics do not validate types, electrical semantics or unsupported
  extension fields, and do not change historical evaluation counts. Some unknown
  fields in strict subobjects already cause parser refusal; these diagnostics do
  not predict whether parsing will succeed.
- Referencing a donor and passing narrow checks does not prove a useful design.
- Guidance changes alone do not demonstrate better agent engineering, improved
  completion rates or prompt-injection resistance.
- No hardware has been measured or powered. Physical correctness remains UNPROVEN.

## Written/photo response proposal — not implemented

Keep the existing human-only operator-token boundary. Add a separately typed
reference response to a need, containing written observations and/or references
to admitted source artifacts. Retain the answerer and artifact hashes through
the existing mission/source stores, not a new evidence database.

A reference response must not impersonate a physical-evidence envelope, become
`person_measurement`, rewrite a frozen donor contract, automatically resolve a
measurement/safety need or grant READY. The agent could reconsider a bounded
proposal from the added reference information, while physical gaps remain open.
Exact event/resolution and revision-invalidation semantics need agreement before
implementation. The existing numeric answer route and PR #139 are untouched.

## Independent handback

Claude should rerun the original cases with unchanged source packets and original
false-result criteria, reporting successful and unsuccessful outcomes. Record the
new code revision separately; do not revise the old experiment after the fact.
Check the saved unsafe concern and terminal grounding, donor coverage, ignored-key
diagnostics and whether useful bounded work was actually persisted before waiting.

Claude also owns the proposed richer Canon engineering-quality experiment and
hostile-document experiment. Neither has been launched by this follow-up.
Inspect actual design/prose as well as stored-state checks: no observed false
stored results is not a guarantee against every hostile agent or source.
