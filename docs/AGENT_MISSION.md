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
| `POST /{mission_id}/package` | After READY: build the mission's package and return its manifest |
| `GET /{mission_id}/package` | After READY: download the package (a ZIP) |
| `POST /{mission_id}/stage` with `{"author": {...}}` | After READY: open a project review of the design, once |

Operations HS can run: `device_plan` (wiring checks; its `findings` carry `severity` and, for some errors,
`suggestions`), `device_engineering` (bus, supply, heat, antenna, fit and printing review; `counts.exceeds_limit`
are errors, `counts.advisory` are warnings; it never "passes" anything), `device_case`, `device_application`,
`device_application_run`. Each run costs one job from the mission's `max_operator_jobs` budget.

You cannot accept a mission, record an evaluation or inventory reading, or write as Hardware Splicer. Those are refused.

Only one mutation or check may run per mission at a time. A competing request returns `409` with `busy`;
read the mission and retry after that operation completes. Reads and unrelated missions remain available.

When a person accepts, HS records `inventory_read` immediately before `accepted`. If acceptance is interrupted,
the reading grants no permission to run; a retry reuses it and completes acceptance. The mission's `inventory` holds
`reading` (fragments, controller, parts and left_out), `draft` (`ok`, `error`, `plan_errors`, `plan_warnings`,
`plan_unrepairable`: error/warning findings without a planner suggestion), and
`result_sha256` of their canonical JSON. HS parses the person's inventory and plans its own draft with the same
planner used for candidate checks. This costs no operator job. If parsing or drafting refuses, HS records the error;
unparseable lines stay uncovered. Missions accepted before inventory readings were added have `inventory: null` and
cannot reach READY. Old terminal records are replayed as recorded, with no new grounding claimed.

Each candidate shows `covers_inventory`, `uncovered_inventory` (the lines it lacks), and `not_in_inventory` (extra
module ids). Quantities count, and an instance cannot cover two inventory lines. Unknown lines are always uncovered.
Extra parts are allowed; they still face the same planner and engineering checks.

Two intake fields hold what only the person can say, and a person's acceptance endorses them:

- `measurements`: `{"<library module id>": {"pcb_mm": {"x": 28.1}, "above_board_mm": 4}}`, sizes the person measured.
  A candidate or repair spec may carry `modules[].overrides` only when they equal the intake's measurement for that
  module exactly. Any other override is refused (422): a measured size is physical evidence, and you have measured
  nothing.
- `requirements`: `[{"path": "case.antenna_clearance", "equals": false}]`, over `case.wall_mm`,
  `case.clearance_mm`, `case.antenna_clearance`, `case.board_stops` and `power.source`. A key you leave out takes
  the planner's default, so deleting a block does not escape a requirement. Each candidate shows
  `violated_requirements`; READY is refused while any is violated, and a repair may not violate a new one.

Free-text `constraints` are reported to you and to the person; HS does not enforce them.

## Events you can propose

Donor references and the `finding_offered` event are described under "Donors and findings" below.

- `candidate_proposed`: `{"candidate": {"id": "A", "kind": "clean_sheet" | "reclaim_heavy" | "hybrid", "label": "...", "spec": {...}, "rationale": "..."}}`. At most the budgeted number of candidates.
- `repair_proposed`: `{"candidate_id": "A", "spec": {...}, "rationale": "..."}`. Allowed only after HS's latest plan of that candidate failed, and only within the repair budget. Once HS has read the inventory, a repair may not leave a listed line uncovered that the current spec covers, or break a requirement the current spec meets. A repair resets the candidate: earlier checks no longer count.
- `evidence_required`: `{"blocker": "<a BLOCKED_* state>", "need": "<what is missing>", "candidate_id": "A" (optional; omit for a need about the whole mission)}`.
  Add a `request` when a person could answer it: `{"kind": "dimensional | electrical | continuity | boot_log", "target": "<library module id for dimensional; otherwise what to measure>", "quantity": "pcb_mm.x | pcb_mm.y | pcb_mm.z | above_board_mm" (dimensional) or a short name such as "voltage", "expected": {"min": 3.2, "max": 3.4, "unit": "V"} (optional), "instructions": "<what the person does>"}`.
- `terminal_proposed`: `{"state": "...", "reason": "...", "candidate_id": "..." (when it concerns one), "cites": [<event seqs>]}`.

## Terminal states and when HS accepts them

| State | HS accepts it when |
|-------|--------------------|
| `READY_FOR_HUMAN_BUILD` | HS has recorded its inventory reading, and the current spec covers every line, every required donor and every requirement; all used donors are verified. Since the candidate's latest repair or physical feedback: a `device_plan` with 0 errors and 0 warnings, then a `device_engineering` with 0 errors, and no evidence need standing for that candidate or the mission |
| `BLOCKED_NEEDS_PART_DATA` | You cite an `evidence_required` with this blocker, and HS's own reading shows a left_out line, a refused draft, or `plan_unrepairable > 0`. Repairable findings such as a BME280 address strap do not establish missing part data. Historical readings without this field keep their former error/warning rule. A failing plan of your own candidate does not count: it shows a wiring fault, not missing data |
| `BLOCKED_NEEDS_PHYSICAL_MEASUREMENT`, `BLOCKED_NEEDS_REVERSE_ENGINEERING`, `BLOCKED_NEEDS_PROCUREMENT_EVIDENCE`, `BLOCKED_UNSAFE` | You cite an `evidence_required` with that blocker, for that candidate or the mission |
| `NO_FEASIBLE_ARCHITECTURE` | All candidate slots are used, current specs are pairwise distinct designs (a new name, wire colours or order do not count) and cover the inventory and required donors, every candidate's latest plan fails and its repairs are spent, and HS's own inventory draft does not plan clean. If it does, propose that draft |
| `BUDGET_EXHAUSTED` | The operator-job budget is spent and no candidate is already ready |

Every `BLOCKED_*` state and `NO_FEASIBLE_ARCHITECTURE` also refuses to stop short of a candidate already ready.
Uncheckable physical, reverse engineering, procurement and safety needs remain allowed assertions; HS labels them,
and does not claim to have established them. New terminal records expose `grounding`: `hs_inventory_reading` for a
part-data blocker; `hs_donor_contract` or `hs_donor_reading` only for the checked donor-specific cases below;
`agent_assertion` for other blocker concerns; `hs_evaluation` for READY and NO_FEASIBLE; and `hs_budget` for
BUDGET_EXHAUSTED. These labels grant no authority.

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

## Delivery after READY

READY says HS's software checks support the design. The package is what the person builds from. It is
deterministic (the same mission gives the same bytes) and stored by its content hash:

- `01_requirements/`: the intake, the person's acceptance, and HS's inventory reading;
- `02_design/`: the spec, and the exact plan and engineering run files READY rests on;
- `03_firmware/`, `04_enclosure/`: what HS generates, or `BLOCKED.md` with the reason when it cannot (for example,
  the application source supports one sensor breakout);
- `05_validation/`: every software check recorded for the candidate, and the physical checks still required;
- `06_provenance/events.jsonl`: the mission's events up to its verdict;
- `MISSION_PACKAGE.json`: the manifest, hashing every file.

Deliverable statuses are `generated`, `blocked`, `not_run`, `modeled_passed`, `modeled_partial`, `modeled_failed`
and, for physical work, `required`. A firmware test status comes only from a recorded `device_application_run`; ask
HS for one before READY if you want it in the package. The manifest keeps `physical_correctness: UNPROVEN` and
both authorizations false.

Staging opens a project review holding the design, the package hash, the evaluations and the chain of repairs that
produced it. It promotes nothing: the design becomes a project revision only if a person accepts that review in the
existing review workflow. You cannot decide a review.

## Waiting for a person

When the design needs a physical fact, propose an `evidence_required` with a `request` and **stop without a terminal
state**. The mission waits in `EVIDENCE_REQUIRED`; a terminal blocker would end it.

A person answers at `POST /{mission_id}/needs/{need_seq}/evidence` with their operator token, a physical-evidence
envelope bound to this project, mission and need (`metadata.mission`), and the values. You cannot answer for them.
HS checks the envelope's hash, that it is bound to this need, that it was not used before, and that the values match
what was asked. The mission's `needs` then show each need's `need_state`:

- `resolved`: the need no longer blocks READY. Checks recorded before the answer no longer count, so run
  `device_plan` and `device_engineering` again. You may also repair after a person's answer.
- `contradicted`: the reading is outside the expected range. The need still stands; read the values and decide
  what to change.

A dimensional answer for a library module becomes usable as that module's `overrides`, like an intake measurement. A
boot log is kept as text; HS does not interpret it. A resolved need can no longer be cited for a blocker. None of
this authorizes flashing or power-on.

## Donors and findings

Intake may include `donors: [{"donor_id": "donor:radio:buttons", "label": "Buttons", "optional": false}]`.
These are references, not contracts. Embedded facts, grades and contracts are refused. Keep donor references out of
the free-text inventory, which is still parsed as library parts. At acceptance HS freezes its own `donor_read`
before `accepted`; a retry reuses that exact reading. The mission view's `donors` contains those facts plus later
findings and person measurements. A missing contract reads `unknown`, not guessed from a similar library module.

The read-only `mission_donors.resolve_donor_contract` resolves existing InterfaceContract JSON at
`<project-store-root>/<project-id>/donors/contracts/donor__<board>__<block>.json` (colons replaced with `__`).
IDs use lowercase alphanumeric/hyphen board and block segments. It refuses symlinks and identity mismatches and
never writes a contract. Existing standalone salvage evidence packages are not searched across projects or imported
automatically. A reviewed contract must be placed in that project-local location by its owning evidence workflow.

Each fact reports `epistemic_state`, `review_state`, `evidence_ids` and `grade`, never the forbidden mission key
`status`. `observed` maps to `re_observation`, `reference_only` to `document`, `inferred`/`assumed` to
`agent_assertion`, and `unknown` to no grade. `measured` plus `accepted` maps to `person_measurement` only when every
referenced ID resolves to a valid, hash-checked, non-simulated, passing electrical envelope for that project and donor.
HS reads those envelopes from the latest stored snapshot's `physicalValidation.audited_physical_evidence.envelopes`,
not arbitrary nested dictionaries, contract labels or agent artifact hashes. Duplicate evidence IDs are ambiguous
and receive no credit. Capability grades take the weakest required fact, never an average or vote.

A candidate spec can carry `donors_used: ["donor:radio:buttons"]`. Every ID must be in intake; HS deduplicates and
sorts the list. Its order, duplicates, or an empty list versus an absent list cannot create distinct architectures.
READY and NO_FEASIBLE must cover every non-optional donor. Repairs cannot drop any used donor, even an optional one.
READY also requires every used donor to be `verified`; a refusal names missing signal facts. Verification here needs
accepted measured Vmax, polarity and controller pin, interface completeness and contact linkage. It is not physical
build authority. Native measured passive switch modules now have a bounded mission-only wiring path; see
[`DONOR_DEVICE_PLANNING.md`](DONOR_DEVICE_PLANNING.md). Tracking references alone do not implement donor hardware.

Offer an RE finding through `/events`:

```json
{"type":"finding_offered","finding":{"donor_id":"donor:radio:buttons","signal":"KEY",
 "claim":"The marking suggests an active-low input","method":"marking","artifacts":[],"source":"RE agent"}}
```

Only an agent may offer a finding, after acceptance. Methods are `marking`, `document`, `firmware_analysis`,
`signal_capture`, `vision`, and `continuity`. A signal may be null. At most 20 artifacts, each exactly
`{name, sha256}` with a 64-hex digest, are references only; HS neither opens paths nor stores binaries. Claims are
limited to 4000 characters, sources and artifact names to 200, signal names to 120. Every offered finding is
`re_observation`, including method `document`; grade, accepted/measured and author overrides are refused.

An evidence need may cite existing finding sequence numbers in `cites`. A donor request names its ID in `target`
and optionally a particular `signal` (electrical/continuity only). Cross-donor finding citations are refused.
Findings never satisfy READY, alter contracts, or ground terminal blockers. RE grounding is `hs_donor_reading` only
when the frozen HS reading shows the cited donor unknown, or the named signal has unknown facts. Physical grounding
is `hs_donor_contract` only for a cited electrical request naming a used donor signal still missing an accepted
measurement. Other concerns retain `agent_assertion`; an invented signal is not HS grounding.

Human electrical answers for donor signals appear in `person_measurements` with grade `person_measurement`, including
outside-range answers as facts, not successes. The envelope must name the donor in `target_ids` and be non-simulated.
An answer does not promote the frozen contract or change its file; existing evidence review owns promotion.

Trust limit: this resolver checks retained evidence identity and envelope integrity, not instrument truth, raw-byte
attestation, or whether a contract paraphrases a measurement correctly. Someone with snapshot-PUT or filesystem
write access can supply records; hashes are not signatures. Those pre-existing persistence permissions remain a
trust boundary. Mission-level firmware/power authority flags remain false and physical correctness stays UNPROVEN.
