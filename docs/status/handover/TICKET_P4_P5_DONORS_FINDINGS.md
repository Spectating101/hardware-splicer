# Ticket: donors in missions (P4) and reverse-engineering findings as evidence (P5)

Repository: this directory, a git worktree on the new branch `agent/mission-donors`, cut from `agent/mission-feedback`
(which stacks on `agent/mission-delivery` and PR #122). You run without a sandbox. Commit as you go: one concern per
commit, imperative mood, capitalized, no trailing period, each message ending with a blank line and
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not push. Do not touch other branches. Leave the git
author config alone. Run Python as `PYTHONPATH=src .venv/bin/python -m pytest ...`.

## Read first

- `CLAUDE.md`. The rule that matters: authority is never implicitly upgraded.
- **`docs/MISSION_DONORS_EVIDENCE_FEEDBACK.md`: the design you implement.** Its "Physical feedback" part is already
  built (`MissionStore.supply_evidence`, `tests/test_mission_feedback.py`); build the P4 and P5 parts exactly as
  written there. A Gemini Argon review shaped it; do not weaken any of its rules. Where the design is silent, choose
  the more conservative option and say so in your report.
- `docs/AGENT_MISSION.md`, the mission section and invariants of `docs/MACHINE_PROJECT_SPINE.md`,
  `docs/INTEGRATION_STACK.md` (donor virtual modules), `src/hardware_splicer/mission_store.py`,
  `donor/interface_contract.py`, `evidence/model.py`, `evidence_contract_store.py`, `physical_evidence.py`.

## What to build

P4: intake `donors` by reference only (`donor_id`, `label`, `optional`); HS's `donor_read` written before `accepted`
and reused on retry; grades as the design maps them; `donors_used` on candidate specs (deduplicated, sorted, counted
in candidate distinctness); donor coverage at READY and NO_FEASIBLE, and repairs that cannot drop a donor; READY
refused while a used donor is not `verified`, naming the missing facts; `hs_donor_contract` grounding only when the
cited need's `request` names a specific donor signal still missing an accepted measurement; `donors` in the mission
view. Mission records never use the key `status` (the store refuses it at every depth): use `contract_state`.

**Where donor contracts come from.** Find how a project's donor interface contracts are persisted today
(`evidence_contract_store.py` reads "evidence packages" by path; `donor_capture.py`, `evidence_salvage_bridge.py`,
`integration_stack.py` produce them). Add the smallest read-only resolver,
`resolve_donor_contract(project_store, project_id, donor_id)`, that finds a stored contract for that id inside the
project's own tree, or returns none, so the donor reads `unknown`. It must not create, edit or promote contracts. If
there is no project-scoped location today, define one under the project directory (for example
`donors/contracts/<safe id>.json` holding the existing contract JSON), document it, and have tests write fixtures
there with the existing contract code. Say what you chose and why. A contract that claims `measured` + `accepted`
with evidence ids not found in the project's physical-evidence records grades below `person_measurement`. Decide
how "found" is checked from what the physical-evidence persistence code actually stores, and describe it.

P5: the `finding_offered` proposal, always recorded as `re_observation` whatever its method; strict validation
(donor in the intake; method from the list; artifacts as `{name, sha256}` with 64-hex hashes, at most 20; text
limits; no grade, authority, `accepted`, `measured` or author override fields); findings shown per donor in the view;
citable by evidence needs; never satisfying READY's donor rule; never grounding a blocker.
`BLOCKED_NEEDS_REVERSE_ENGINEERING` is grounded `hs_donor_reading` only from HS's own `donor_read` (the cited need
names a donor whose `contract_state` is `unknown`, or a named signal whose epistemic state is `unknown`); otherwise
it stays `agent_assertion`.

## Tests

The design's "Tests the implementation must carry" list, each written first and confirmed failing before the fix.
Also, specifically:

- grade laundering: a finding with `method: document` is still `re_observation`; a contract with forged accepted
  measurements and unknown evidence ids does not grade `person_measurement`;
- an embedded contract in the intake is refused (422);
- `donors_used` reordered or duplicated does not make two candidates distinct;
- a repair dropping a used donor is refused, naming it;
- the red-team rule: no route or proposal lets an agent raise any grade.

All existing mission tests must stay green: `tests/test_mission_*.py`, `tests/test_device_agent_surface.py`,
`tests/test_mcp_backend_gateway.py`. If `finding_offered` belongs in the `fabrication_mission` MCP task, it already is,
since it goes through `/events`; the evidence route must stay out of it.

## Docs

Update `docs/AGENT_MISSION.md` (donors, findings, grades), the spine doc's mission section plus a new invariant, and
the status line of `docs/MISSION_DONORS_EVIDENCE_FEEDBACK.md` (P4 and P5 built). Same plain style.

## Verification

1. `PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_mission_*.py tests/test_device_agent_surface.py tests/test_mcp_backend_gateway.py`
   plus any donor or evidence test files you touch.
2. The full suite once at the end: `PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider tests` (about 15
   minutes; run nothing else heavy alongside). Three tests fail locally before your change and pass in CI (a KiCad
   environment gap): `test_assembly_plan.py::test_outlines_agree_with_kicads_own_geometry_for_turned_and_flipped_parts`
   and the two `test_project_intake.py` production-package tests. Report them, don't touch them.

## Final report

Write `.cache/donors-report.md` and print a summary: commits (SHA and subject), each test and the rule it pins with
fail-before confirmation, exact pytest result lines, the contract-location choice, how evidence ids are checked, and
anything in the design you think is still exploitable.
