# Driving a fabrication mission (for agents)

A fabrication mission turns a person's goal, constraints and parts list into either a plan a person can build or
an honest reason it cannot be built yet. You are the agent: you reason and propose. Hardware Splicer (HS) runs the
checks and decides. A person accepted the mission before you started; that acceptance lets HS run its
software-only checks for you within the mission's budgets. Nothing you do is physical, and nothing you do grants
authority.

**Success is reaching the correct terminal state with an evidence trail, not reaching "ready".** A mission that
stops at an honest blocker has succeeded. A mission that reaches `READY_FOR_HUMAN_BUILD` by dropping a part the
person asked for, or by skipping a check, has failed.

## What you can call

All routes are under `/v1/projects/{project_id}/missions` unless noted. Send JSON. Your author is always
`{"kind": "agent", "id": "<your name>"}`.

| Call | What it does |
|------|--------------|
| `GET /{mission_id}` | The mission: intake (goal, constraints, inventory), HS's `inventory` reading and draft verdict, budgets, phase, candidates with their evaluations and inventory coverage, events, terminal state |
| `POST /v1/devices/draft` with `{"text": "<parts, one per line>"}` | HS's draft from a typed parts list: a wired spec, what each line matched (`parsed.fragments`), what matched nothing (`parsed.left_out`), and the planner's findings. A draft approves nothing |
| `GET /v1/devices/spec-schema` | The spec format and the module library (controllers and parts, with their pins) |
| `POST /{mission_id}/events` | Propose one event (below). Send `{"event": {...}, "author": {...}, "expected_event_seq": <the mission's last_event_seq>}` |
| `POST /{mission_id}/candidates/{candidate_id}/run` with `{"operation": "..."}` | Ask HS to run one check on the candidate's current spec. Returns the mission and the new evaluation |
| `GET /{mission_id}/runs/{name}` | The full output of a check (the evaluation's `artifact` is `runs/<name>`) |

Operations HS can run: `device_plan` (wiring checks; its `findings` carry `severity` and, for some errors,
`suggestions`), `device_engineering` (bus, supply, heat, antenna, fit and printing review; `counts.exceeds_limit`
are errors, `counts.advisory` are warnings; it never "passes" anything), `device_case`, `device_application`,
`device_application_run`. Each run costs one job from the mission's `max_operator_jobs` budget.

You cannot accept a mission, record an evaluation or inventory reading, or write as Hardware Splicer. Those are refused.

Only one mutation or check may run per mission at a time. A competing request returns `409` with `busy`;
read the mission and retry after that operation completes. Reads and unrelated missions remain available.

When a person accepts, HS records `inventory_read` immediately before `accepted`. If acceptance is interrupted,
the reading grants no permission to run; a retry reuses it and completes acceptance. The mission's `inventory` holds
`reading` (fragments, controller, parts and left_out), `draft` (`ok`, `error`, `plan_errors`, `plan_warnings`), and
`result_sha256` of their canonical JSON. HS parses the person's inventory and plans its own draft with the same
planner used for candidate checks. This costs no operator job. If parsing or drafting refuses, HS records the error;
unparseable lines stay uncovered. Missions accepted before inventory readings were added have `inventory: null` and
cannot reach READY. Old terminal records are replayed as recorded, with no new grounding claimed.

Each candidate shows `covers_inventory`, `uncovered_inventory` (the lines it lacks), and `not_in_inventory` (extra
module ids). Quantities count, and an instance cannot cover two inventory lines. Unknown lines are always uncovered.
Extra parts are allowed; they still face the same planner and engineering checks.

## Events you can propose

- `candidate_proposed`: `{"candidate": {"id": "A", "kind": "clean_sheet" | "reclaim_heavy" | "hybrid", "label": "...", "spec": {...}, "rationale": "..."}}`. At most the budgeted number of candidates.
- `repair_proposed`: `{"candidate_id": "A", "spec": {...}, "rationale": "..."}`. Allowed only after HS's latest plan of that candidate failed, and only within the repair budget. Once HS has read the inventory, a repair cannot increase the number of uncovered inventory lines. A repair resets the candidate: earlier checks no longer count.
- `evidence_required`: `{"blocker": "<a BLOCKED_* state>", "need": "<what is missing>", "candidate_id": "A" (optional; omit for a need about the whole mission)}`.
- `terminal_proposed`: `{"state": "...", "reason": "...", "candidate_id": "..." (when it concerns one), "cites": [<event seqs>]}`.

## Terminal states and when HS accepts them

| State | HS accepts it when |
|-------|--------------------|
| `READY_FOR_HUMAN_BUILD` | HS has recorded its inventory reading and the current spec covers every line. Since the candidate's latest repair: a `device_plan` with 0 errors and 0 warnings, then a `device_engineering` with 0 errors, and no evidence need standing for that candidate or the mission |
| `BLOCKED_NEEDS_PART_DATA` | You cite an `evidence_required` with this blocker, and HS's own reading of the inventory shows the gap: a left_out line, or its draft refuses or has planner errors or warnings. A failing plan of your own candidate does not count: it shows a wiring fault, not missing data |
| `BLOCKED_NEEDS_PHYSICAL_MEASUREMENT`, `BLOCKED_NEEDS_REVERSE_ENGINEERING`, `BLOCKED_NEEDS_PROCUREMENT_EVIDENCE`, `BLOCKED_UNSAFE` | You cite an `evidence_required` with that blocker, for that candidate or the mission |
| `NO_FEASIBLE_ARCHITECTURE` | All candidate slots are used, current specs are pairwise distinct designs (a new name, wire colours or order do not count) and cover the inventory, every candidate's latest plan fails and its repairs are spent, and HS's own inventory draft does not plan clean. If it does, propose that draft |
| `BUDGET_EXHAUSTED` | The operator-job budget is spent and no candidate is already ready |

Every `BLOCKED_*` state and `NO_FEASIBLE_ARCHITECTURE` also refuses to stop short of a candidate already ready.
Uncheckable physical, reverse engineering, procurement and safety needs remain allowed assertions; HS labels them,
and does not claim to have established them. New terminal records expose `grounding`: `hs_inventory_reading` or
`hs_inventory_reading` for a part-data blocker, `agent_assertion` for the other blockers, `hs_evaluation` for READY and
NO_FEASIBLE, and `hs_budget` for BUDGET_EXHAUSTED. These labels grant no authority.

A refused proposal returns 409 or 422 with the reason. Read it; do not retry the same thing.

## A sensible loop

1. Read the mission. Draft from the inventory (`POST /v1/devices/draft`). Look at what every line matched and what
   was left out. A part the person listed that HS has no data for is a need, not something to drop.
2. Propose a candidate from the draft, or record the need and stop with the matching blocker.
3. Run `device_plan`. If it reports errors or warnings, read the plan's findings in its run file. Where a finding
   carries a suggestion, apply it to the spec and propose a repair, then plan again. Where there is no repair HS
   can express, record the need and stop with the matching blocker.
4. When the plan is clean, run `device_engineering`. An exceeded limit is a reason to stop, not to proceed.
5. Propose the terminal state the evidence supports, citing the events it rests on.

Keep within the budgets: each check costs a job, and running out before the engineering review is itself an
honest outcome.
