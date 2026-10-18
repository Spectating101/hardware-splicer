# Canonical machine project spine

Hardware Splicer stores one traceable machine project per build. PCB, mechanical,
firmware, sourcing, assembly, splice and bench data attach to that project as
discipline payloads instead of becoming competing project formats.

This document covers the persistent project layer shipped after
[`INTEGRATION_STACK.md`](INTEGRATION_STACK.md): the canonical model, durable
revisions, semantic diffs, and the staged review workflow that guards them.

## Ownership boundary

The spine owns:

- project identity and revision history;
- cross-discipline structure (subsystems, components, requirements, constraints);
- authority state per engineering claim;
- release assessment and its blockers;
- which candidate edits may become the next durable revision.

The spine does **not** own compile output, DRC/ERC truth, bench measurements, or
firmware artifacts. Those remain with their existing subsystems and are attached
as payloads.

## Core doctrine

**Authority is never implicitly upgraded.** Importing, seeding, composing,
diffing, or reviewing a project reports state — none of them promote a claim.
Release assessment reports blockers rather than silently marking a project
build-ready or operationally authorized.

## Ontology

Four enums carry the semantics. They live in `machine_project.py` and are shared
by API, UI, and future CI gates.

| Enum | Values |
|------|--------|
| `Domain` | `system`, `mechanical`, `electrical`, `firmware`, `software`, `sourcing`, `assembly`, `verification` |
| `AuthorityState` | `unknown` → `proposed` → `declared` → `observed` → `measured` → `verified` → `authorized` |
| `LifecycleState` | `intake` → `architecture` → `design` → `verify` → `bench` → `package` |
| `ReleaseState` | `concept` → `design_ready` → `build_ready` → `bench_ready` → `operationally_authorized` |

`RequirementKind` classifies requirements as `functional`, `performance`,
`safety`, `interface`, or `constraint`.

Release authority is **monotonic**: evidence supporting a higher state also
satisfies a lower requested state (`machine_release.release_state_satisfies`).
Blockers always win — see `assessment_allows` for the single permission rule
shared by API, UI and CI.

## Modules

| Module | Role |
|--------|------|
| `machine_project.py` | Canonical model and ontology (`hardware_splicer.machine_project.v1`) |
| `machine_project_seed.py` | Deterministic seed from project intake |
| `machine_project_diff.py` | Identity-aware semantic diff |
| `machine_project_compile_adapter.py` | Projection from compile spec |
| `machine_release.py` | Release-state ordering and the permission rule |
| `project_store.py` | Durable revisions (`hardware_splicer.project_snapshot.v1`) |
| `project_review_store.py` | Staged review workflow (`hardware_splicer.project_review.v1`) |
| `project_thread_store.py` | Append-only review threads (`hardware_splicer.review_thread.v1`) |
| `mission_store.py` | Fabrication missions: append-only event log replayed into a state machine (`hardware_splicer.fabrication_mission.v1`) |
| `mission_executor.py` | Software-only device checks for an accepted fabrication mission; never physical, never authority |
| `mission_runner.py` | Deterministic agent that drives one accepted mission to a terminal state via the public mission API only |
| `device_suggestions.py` | Pure first-suggestion repairs from a device plan; copies the spec and never mutates its arguments |
| `project_api.py` | `/v1/projects` — persistence and review |
| `machine_project_api.py` | `/v1/machine-projects` — model, seed, diff, release |

Seeding is deliberately conservative: it creates purpose, requirements,
subsystems, components and declared constraints, but never invents pin mappings,
mechanical fits, firmware behavior, or verification evidence.

## Semantic diff

The diff is identity-aware rather than line-oriented. It reports engineering
object additions/removals, field changes, and **authority transitions**, so human
or agent edits can be reviewed before replacing a persisted revision.

Changes carry a `ReviewSeverity` of `info`, `warning`, or `required`. A diff
never grants authority; it only reports what changed and what demands explicit
review.

## Staged review workflow

Candidate snapshots are stored **outside** revision history until explicitly
accepted. A review decision never upgrades engineering authority — it only
controls whether a candidate may become the next durable revision.

Review status lifecycle:

```text
pending ──accept──> accepting ──> accepted
   └─────reject───> rejected
```

`accepting` is a journaled intermediate state. If the process dies mid-accept,
`_reconcile_accepting` replays the journal on next load so the workflow resumes
rather than stranding the candidate. The event log is append-only.

Review covers the **entire candidate snapshot**, not only machine fields — a
change to any part of the snapshot surfaces in the console.

### Concurrency

`project_store` raises `RevisionConflict` when `expected_revision` does not match
the stored revision; `project_review_store` raises `ReviewConflict` for a
decision against a review that has already moved on. Both surface as a stable
API error contract — clients may rely on the shape.

## API surface

`/v1/projects`

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `""` | List projects (`include_archived`) |
| `GET` | `/{project_id}` | Load a project |
| `PUT` | `/{project_id}/snapshot` | Save snapshot (optimistic `expected_revision`) |
| `GET` | `/{project_id}/revisions` | Revision history |
| `POST` | `/{project_id}/duplicate` | Duplicate |
| `DELETE` | `/{project_id}` | Delete |
| `GET` | `/{project_id}/reviews` | List reviews |
| `POST` | `/{project_id}/reviews` | Open a review for a candidate |
| `GET` | `/{project_id}/reviews/{review_id}` | Load a review + diff |
| `POST` | `/{project_id}/reviews/{review_id}/decision` | Accept or reject |
| `GET` | `/{project_id}/threads` | List review threads |
| `POST` | `/{project_id}/threads` | Open a review thread |
| `GET` | `/{project_id}/threads/{thread_id}` | Load a review thread + events |
| `POST` | `/{project_id}/threads/{thread_id}/events` | Append a comment, resolve, or reopen |
| `GET` | `/{project_id}/events` | Live change stream (SSE); information only — [`PROJECT_EVENTS.md`](PROJECT_EVENTS.md) |
| `GET`/`POST`/`DELETE` | `/{project_id}/presence` | Ephemeral presence; not an audit log — [`PROJECT_EVENTS.md`](PROJECT_EVENTS.md) |

`/v1/projects/{project_id}/missions`

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `""` | Open a fabrication mission |
| `GET` | `""` | List missions |
| `GET` | `/{mission_id}` | Load a mission |
| `POST` | `/{mission_id}/accept` | Accept a mission and its budgets |
| `POST` | `/{mission_id}/events` | Propose a candidate, repair, evidence need, or terminal state |
| `POST` | `/{mission_id}/candidates/{candidate_id}/run` | Run a software-only device check |
| `GET` | `/{mission_id}/runs/{name}` | Read a hashed run file referenced by an evaluation |

Acceptance (`POST /{mission_id}/accept`) requires a person's operator token in
`X-HS-Operator-Token` — see [`OPERATOR_IDENTITY.md`](OPERATOR_IDENTITY.md). That
route is not in the MCP `fabrication_mission` task.

Retained KiCad revision artifacts and redlines: [`ARTIFACT_RETENTION.md`](ARTIFACT_RETENTION.md). Rendered 3D GLB views of retained PCB bytes: [`MODEL3D.md`](MODEL3D.md). Parts intelligence for a retained schematic revision: [`PARTS_INTELLIGENCE.md`](PARTS_INTELLIGENCE.md). Candidate edit proposals (never a write to a revision): [`CANDIDATE_PROPOSALS.md`](CANDIDATE_PROPOSALS.md). Review packet of a revision, hash-bound and read-only: [`REVIEW_PACKET.md`](REVIEW_PACKET.md).

`/v1/machine-projects`

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/schema` | Canonical schema |
| `POST` | `/validate` | Validate an envelope |
| `POST` | `/from-intake` | Seed from intake |
| `POST` | `/from-compile-spec` | Project a compile spec |
| `POST` | `/from-session` | Migrate a legacy session |
| `POST` | `/diff` | Semantic diff |
| `POST` | `/assess-release` | Release assessment + blockers |

## Frontend

`apps/splice-ui/src/projectSession/` holds the durable workspace:
`projectPersistence.js` (revision save/load), `projectReviewApi.js` (browser
client), and `projectSession.js`. `ProjectWorkspace.jsx` mounts
`ProjectReviewPanel` (revision review console) and `MachineArchitecturePanel`
(cross-discipline structure).

Review traffic is suppressed until a durable revision actually exists, so a fresh
project does not emit review calls against nothing.

## Review threads

Review threads are append-only discussion records anchored to a project object,
finding, or artifact at a specific revision. They sit beside the project tree
(`threads/`) and are separate from staged reviews: a comment, resolve, or reopen
never changes a snapshot, a revision, a review decision, or authority state.

An optional `position` (`x_mm`, `y_mm`) may accompany an artifact. Position is a
LOCATION, never an object identity.

Author identity is self-declared unless the caller presents a server-issued
operator token in `X-HS-Operator-Token` only. `Authorization` is ordinary app
auth (the Next.js UI proxy forwards `Authorization: Bearer <app API key>`), so
it is never treated as an operator token. A valid token stores the registry
`id`/`kind`, `author_verified: true`, and `verified_by: "operator-token"`. A
verified comment is still only a comment: it does not authenticate the operator
beyond possession of that token, and it never upgrades authority. See
[`OPERATOR_IDENTITY.md`](OPERATOR_IDENTITY.md). Mentions are plain text.

## Fabrication missions

A mission is the persistent record of one attempt to turn a goal, constraints and an inventory into a buildable
plan. It lives beside the project tree (`missions/<mission_id>/`): an immutable `mission.json` holding the intake,
budgets and the revision it is anchored to, and `events/00000001.json…`, never rewritten. Phase, candidates, budgets
used and the terminal state are not stored; they are replayed from the events every time.

Phases run `INTAKE → ARCHITECTING → EVALUATING → REPAIRING / EVIDENCE_REQUIRED → TERMINAL`. An agent can only
propose: up to three candidates (`clean_sheet`, `reclaim_heavy`, `hybrid`), repairs, evidence needs and a terminal
state. Evaluations are written only by Hardware Splicer itself, and an agent cannot sign as the system author.

Immediately before acceptance, HS appends its own `inventory_read`, at no operator-job cost. It parses the intake
inventory and plans its own draft with the canonical device planner. The mission view exposes this as `inventory`:
`reading` (fragments, controller, parts, left_out), `draft` (ok, error, plan_errors, plan_warnings), and a
`result_sha256` of their canonical JSON. A parser refusal leaves the original lines uncovered and the draft not ok.
Each candidate reports `covers_inventory`, `uncovered_inventory` and extra module ids in `not_in_inventory`.
Module counts are consumed in inventory order; no instance covers two fragments, quantities must be met, and every
left_out line stays uncovered. Extra modules are allowed. A repair may not newly uncover a listed line.

The intake may also carry the person's `measurements` (measured sizes per library module) and structured
`requirements` (`{path, equals}` over the case settings and power source). A mission spec's module overrides must
equal the person's measurement exactly, so an agent cannot supply a measured size. Requirements are resolved through
the planner's own validated spec, so an absent key takes its default; READY and NO_FEASIBLE need every candidate
concerned to meet them, and a repair may not newly break one. Free-text constraints are reported, never enforced.
Missions accepted before this event was added have no inventory reading and cannot newly reach READY. Existing
terminal events are replayed as recorded; old records do not acquire a grounding claim.

The inventory reading precedes the acceptance event deliberately: interruption cannot leave a new mission accepted
without inventory. Retrying acceptance reuses a stored reading and completes the human acceptance; a reading alone
never permits execution. Historical accepted-without-inventory logs are not backfilled.

Success is the **correct** terminal state, not reaching "ready":

- `READY_FOR_HUMAN_BUILD` needs an HS inventory reading and full inventory coverage, HS's own latest plan evaluation since the candidate's latest repair to be clean, an
  engineering review without errors after it, and no evidence need standing for that candidate or the mission. It
  still lists the physical evidence only a person can establish.
- Every `BLOCKED_*` state must cite an evidence need with that blocker for that candidate (or the whole mission), and
  may cite only real evidence or evaluation events. A part-data blocker also needs HS grounding in its own reading
  of the inventory: a left_out line, a refused draft, or error/warning findings without planner suggestions
  (`plan_unrepairable`). Historical readings without this field retain their former error/warning rule. A cited failing plan
  is not grounding, since an agent can break its own wiring to get one.
- `NO_FEASIBLE_ARCHITECTURE` needs all candidate slots used, current specs that are distinct designs (ignoring names, wire colours and order)
  and cover the inventory,
  and every candidate failing since its latest repair with its repairs spent. If HS's own inventory draft plans
  clean with zero errors and warnings, HS refuses and tells the agent to propose it.
- `BUDGET_EXHAUSTED` needs the operator budget spent. No blocked, no-feasible or budget terminal may stop short of
  a candidate that is already ready.

New terminal records carry `grounding`: `hs_inventory_reading` for part-data blockers;
`hs_donor_contract` or `hs_donor_reading` for the checked donor cases below; otherwise
`agent_assertion` for physical measurement, reverse engineering, procurement and unsafe blockers;
`hs_evaluation` for READY and NO_FEASIBLE, and `hs_budget` for BUDGET_EXHAUSTED. The other blockers remain allowed:
HS labels the agent's concern without claiming to have measured or established it. Grounding never grants authority.

A person accepts the mission and its budgets once. That acceptance covers HS's software-only checks within budget;
anything physical still stops for a human. The executor (`mission_executor.py`) runs only those checks on an accepted
mission: it calls the canonical device functions, maps their verdicts onto evaluation errors and warnings, and stores
the full output as a hashed run file. A check that refuses or cannot run is recorded as a failure, never as a pass.
The executor never writes a project snapshot and never grants physical authority.

Mission mutations use a nonblocking POSIX advisory lock on the immutable `mission.json` marker, shared across
threads, store instances and worker processes. The executor holds it from budget/spec selection through result
recording. Proposals, acceptance and direct internal evaluation writes use the same lock. Contention returns
`MissionConflict` / HTTP 409 (`busy`), before executing another check; reads and other missions are not locked.
Locks are reentrant only on the same store/thread, and the OS releases them on worker exit. This is serialization,
not a durable execution queue: the existing budget counts recorded evaluations, not interrupted/unrecorded attempts.

The runner (`mission_runner.py`) is an agent with no privileged path: it may only read the mission
(`get_mission`, `read_run`), propose events with the given agent author and the current
`expected_event_seq`, and ask the executor to run checks. It must not call `record_evaluation` or
`accept_mission` or write files. `tests/test_mission_gate.py` declares each scenario's correct
terminal state in advance: `READY_FOR_HUMAN_BUILD` where everything checks out;
`BLOCKED_NEEDS_PART_DATA` for parts HS has no data for or a different board; the BME280 address-clash case reaches
READY through a recorded strap repair. `BUDGET_EXHAUSTED` applies when the budget cannot pay for the review.

`mission_delivery.py` turns a READY mission into a deterministic package
(`hardware_splicer.mission_package.v1`, stored under `missions/<id>/packages/` by content hash) and stages its design
as a staged project review: the candidate snapshot adds `deviceDesigns[<mission_id>]` with the spec, package hash,
evaluations and repair chain, which the review flags as a required snapshot change. HS records `design_staged` on the
mission once, after the terminal state, without changing the phase or the verdict. The package covers events up to
the verdict, so staging never changes it.

A mission can wait for a person. An `evidence_required` may carry a structured `request` (dimensional, electrical,
continuity or boot log). A person answers it with `supply_evidence`: a `PhysicalEvidenceEnvelope` whose hash HS
recomputes, bound in `metadata.mission` to the project, mission, need and values, and never used before in the
project. HS records `evidence_supplied` (`within`, `outside` or `not_comparable` against the requested range). A
`resolved` need stops blocking READY, `outside` leaves it `contradicted`, and either way earlier checks no longer count.
Dimensional answers become usable module overrides. The design for donors and reverse-engineering findings built on
the same evidence grades is in [`MISSION_DONORS_EVIDENCE_FEEDBACK.md`](MISSION_DONORS_EVIDENCE_FEEDBACK.md).

Donor intake is references only. For missions naming donors, HS freezes a project-scoped `donor_read` before
acceptance and reuses it on retry. Candidate `donors_used` is normalized and checked for required donor coverage;
repairs cannot drop a used donor. READY requires verified contracts and names missing facts otherwise. Facts carry
separate epistemic, review and grade fields; accepted measurement IDs alone are insufficient without matching,
hash-checked physical records. The resolver is read-only and adds no contract-write API or parallel evidence store.

Agents may offer hash-referenced RE findings via the existing events route. Findings always remain
`re_observation`, can be cited by needs, and never establish measurement or terminal grounding. Only the frozen
HS reading can ground `hs_donor_reading` or `hs_donor_contract`. Human donor measurements are shown separately and
never rewrite or promote that contract. Persistence location and trust limits: [`AGENT_MISSION.md`](AGENT_MISSION.md).

Native passive-switch donor modules can now enter the device planner with measured contact geometry and explicit
electrical protocols. The mission executor injects only the frozen donor context; standalone JSON cannot supply it.
Native donor modules cannot be duplicated or dropped into mere tracking references by a repair. Plans, engineering
reviews and enclosure exports include those modules. Supported sensor applications may include a separate passive
input firmware proposal and GPIO/clock modeled phase; unsupported combinations stay explicitly blocked rather than
silently omitting donor behavior. Scope and trust limits: [`DONOR_DEVICE_PLANNING.md`](DONOR_DEVICE_PLANNING.md)
and [`DONOR_INPUT_FIRMWARE.md`](DONOR_INPUT_FIRMWARE.md).

## Verification

```bash
pytest -q \
  tests/test_operator_identity.py \
  tests/test_project_store.py \
  tests/test_project_review_store.py \
  tests/test_project_api.py \
  tests/test_project_review_api.py \
  tests/test_project_thread_store.py \
  tests/test_project_thread_api.py \
  tests/test_machine_project.py \
  tests/test_machine_project_diff.py \
  tests/test_machine_project_diff_review_flags.py \
  tests/test_machine_release.py \
  tests/test_mission_store.py \
  tests/test_mission_executor.py \
  tests/test_mission_gate.py
```

Frontend: `make splice-ui-build`.

## Authority invariants

1. Seeding, importing, or migrating never upgrades an authority state.
2. A diff reports authority transitions; it does not perform them.
3. Accepting a review promotes a **snapshot to a revision**, never a claim to a
   higher authority.
4. Release assessment reports blockers; blockers always outrank achieved state.
5. Release authority is monotonic — one ordering rule shared by API, UI and CI.
6. Review acceptance is journaled and crash-recoverable; a partial accept
   resumes rather than silently dropping or double-applying.
7. The review event log is append-only.
8. Revision and review conflicts raise a stable, documented error contract.
9. Review threads are discussion only; they never alter a snapshot, revision, review decision, or authority state.
10. The thread event log is append-only; resolve/reopen are events, not edits.
11. A mission never writes a snapshot or revision and never carries an authority field, at any depth. Inventory readings and terminal grounding grant no physical, firmware or power-on authority.
12. A mission's terminal state is checked against HS's inventory reading, recorded evaluations and cited evidence. READY covers the person's inventory and meets their structured requirements; a repair cannot newly uncover a listed line or break a requirement, and only the person's intake can supply measured sizes. Part-data blockers need grounding in HS's own reading of the inventory, uncheckable concerns are labelled agent assertions, and NO_FEASIBLE needs a full distinct search covering the inventory with no clean HS draft available. A proposal alone never establishes evidence.
13. Staging a mission design opens a review; only a person's decision on that review makes it a revision, and that review is decided only with a verified human operator token (the decider is the token's identity, not a name in the request). Other reviews keep the older rule, where the request names its actor. A mission package names what HS could not generate and never claims physical truth.
14. Only a person answers a mission's evidence need, with an envelope HS can verify, bound to that mission and need and used once. An answer resolves a need or records a contradiction; it never authorizes anything physical, and checks made before it no longer count towards READY.
15. Donor references, RE findings and person measurements remain distinct. No agent finding or claimed measurement ID promotes a donor fact; donor coverage and verified contracts are required for READY, and only HS's frozen donor reading can ground a donor-specific blocker. Resolving or replaying donors never writes contracts, snapshots, revisions or authority.
16. Native donor implementation uses frozen electrical and dimensional evidence, not catalogue inheritance or caller-supplied module definitions. Generating a donor topology or enclosure never implies donor firmware, physical operation or authorization, and a repair cannot erase a placed donor while retaining only its reference.
