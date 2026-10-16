# Missions over donors, reverse-engineering evidence and physical feedback

Status: **physical feedback is implemented** (`MissionStore.supply_evidence`, `tests/test_mission_feedback.py`);
**P4 and P5 are designed, not yet built.** A Gemini 4 Argon review found eight ways the first draft could launder
grades or replay evidence; each was checked against the store and the fixes are folded in below.

Design for steps P4, P5 and physical feedback of the Fabrication Mission Runtime. It extends `docs/AGENT_MISSION.md`
and the "Fabrication missions" section of `docs/MACHINE_PROJECT_SPINE.md`. It builds on subsystems HS already has
and does not duplicate them:

- donor blocks: `donor:<board>:<block>` virtual modules and `InterfaceContract`
  (`donor/interface_contract.py`, schema `hardware_splicer.interface_contract.v1`);
- evidence values: `EvidenceValue` with an epistemic state (`observed | measured | inferred | assumed |
  reference_only | unknown`) and a review state (`unreviewed | accepted | rejected | superseded`)
  (`evidence/model.py`); a value is authoritative only when accepted, observed or measured, and backed by evidence ids;
- physical evidence: `PhysicalEvidenceEnvelope` and `physical_evidence_envelope_hash`
  (`physical_evidence_ledger.py`), whose responses never grant physical authority.

The rule throughout: **the agent proposes, HS records and checks, the person supplies physical facts and decides.**
Evidence can raise what HS knows. It never raises what HS authorizes. A mission stays `UNPROVEN`, and
`firmware_authorized` and `power_on_authorized` stay false.

## Evidence grades

A mission reports every fact it rests on with one grade, from weakest to strongest:

| Grade | Comes from | Can ground |
|---|---|---|
| `agent_assertion` | the agent's own statement | nothing HS checks; a labelled blocker only |
| `re_observation` | a reverse-engineering finding: a marking read, a firmware string, a signal capture, a vision guess | a hypothesis about a donor block; never a READY |
| `document` | a cited datasheet, manual or schematic page | an expected value; never a physical fact |
| `person_measurement` | an attested physical-evidence envelope a person supplied | a physical fact about this unit |
| `hs_check` | HS's own deterministic evaluation | a software verdict (plan, review, build, model run) |

Grades never combine upward. Ten RE observations do not make a measurement. A grade is attached to a fact, never to
the mission as a whole.

## P4: donors in a mission

### Intake

The intake gains `donors`: a list of `{"donor_id": "donor:<board>:<block>", "label": "<what the person calls it>",
"optional": false}`. It names donors **by reference only**. A contract is never embedded in the intake: an agent
opens missions, and an embedded contract could carry forged `measured` and `accepted` values that a person's
acceptance would appear to endorse. HS resolves each id from the project's own donor contract evidence (the
evidence contract store), where contracts are created and reviewed by the existing donor workflows. A donor id with
no stored contract reads as `unknown`. Donors are separate from the free-text `inventory`, so donor lines never reach
the parts reader's `left_out`.

### HS's donor reading

At acceptance, next to `inventory_read` and like it **before** the `accepted` event (a retry reuses a reading
already written), HS records a system event `donor_read` with each donor's:

- `contract_state` from `recompute_status` (`unknown | partial | verified | rejected`). Mission records never use
  the key `status`, which the store refuses at every depth;
- `can_generate_firmware`;
- per signal: name, direction, and for Vmax, polarity and controller pin, the value with its epistemic state, review
  state and evidence ids, mapped to a grade. Only `measured` + `accepted` with evidence ids that HS finds in the
  project's physical-evidence records maps to `person_measurement`. `observed` maps to `re_observation`, `inferred`
  and `assumed` to `agent_assertion`, `reference_only` to `document`, and `unknown` to none;
- `capabilities`: the functional roles the contract or its salvage analysis names (for example `h_bridge_driver`,
  `power_regulation`), each with the weakest grade among the facts that role needs.

The reading is what HS knows, not what the agent says.

### Candidates

A candidate spec may name the donor blocks it uses in a top-level `donors_used: ["donor:..."]`. Each must be in the
intake. HS deduplicates and sorts it; candidate distinctness compares the sorted list. The device planner still plans only library modules; a donor block is not wired by the planner in this step.
That is frozen for later; see the plan below.

### Terminal rules

- READY is refused while any donor the candidate uses is not `verified` (accepted measured Vmax, polarity and
  controller pin). The refusal names the missing facts.
- A new HS-grounded blocker path: `BLOCKED_NEEDS_PHYSICAL_MEASUREMENT` is grounded `hs_donor_contract` when the
  candidate uses a donor whose contract lacks an accepted measurement HS names. Without that, it stays
  `agent_assertion` as today.
- Donor coverage works like inventory coverage. READY and NO_FEASIBLE need every non-optional intake donor in
  `donors_used`. A repair may not drop a donor the current spec uses.

## P5: reverse-engineering findings as evidence

### Recording a finding

A new proposal type, `finding_offered`, open to agents and to RE tools acting as agents:

```json
{"type": "finding_offered",
 "finding": {"donor_id": "donor:...", "signal": "UART_TX" | null,
             "claim": "J3 pin 2 carries UART TX at 3.3 V",
             "method": "marking | document | firmware_analysis | signal_capture | vision | continuity",
             "artifacts": [{"name": "...", "sha256": "<64 hex>"}],
             "source": "<tool or agent name>"}}
```

HS records every agent-authored finding as `re_observation`, whatever its `method`, including `document`: an
artifact hash the agent supplies proves nothing about what the artifact is. It never becomes a measurement and never
changes a donor contract's accepted values. It can:

- appear in the mission view under that donor, with its grade and artifacts;
- be cited by an `evidence_required` need to say what is suspected and what must be measured.

Findings never ground a blocker. `BLOCKED_NEEDS_REVERSE_ENGINEERING` is grounded `hs_donor_reading` only from HS's own
donor reading: the cited need names a donor whose `contract_state` is `unknown`, or a named signal whose epistemic
state is `unknown`. Otherwise it stays `agent_assertion`.

Raw RE artifacts are referenced by hash. The mission does not store binaries.

### What it may never do

- Mark any contract value `accepted` or `measured`.
- Satisfy READY's donor rule.
- Be authored as `system` or `human`.

## Physical feedback: a mission can wait for a person and resume

Today a physical need ends the mission (`BLOCKED_NEEDS_PHYSICAL_MEASUREMENT` is terminal) and no evidence need can
ever be resolved. Feedback adds the missing half without making terminal states mutable.

### Asking

`evidence_required` gains an optional structured `request`:

```json
{"kind": "dimensional | electrical | continuity | boot_log",
 "target": "mcu" | "donor:..." | "<free text>",
 "quantity": "pcb_mm.x" | "voltage" | null,
 "expected": {"min": 4.75, "max": 5.25, "unit": "V"} | null,
 "instructions": "Measure the 5 V rail at TP3 with the board powered from USB."}
```

An agent waiting for a person leaves the mission in `EVIDENCE_REQUIRED`. It does not propose a terminal state.
Terminal states stay final.

### Answering

`POST /v1/projects/{project_id}/missions/{mission_id}/needs/{need_seq}/evidence`, with the person's operator token
(kind `human`, like `/accept`). The body carries:

- `envelope`: a `PhysicalEvidenceEnvelope`, validated by the existing ledger code, with its hash recomputed by HS;
- `values`: the readings, `[{"quantity": "pcb_mm.x", "value": 28.1, "unit": "mm"}]` or
  `{"log": "<text>"}` for a boot log (at most 64 KB);
- `expected_event_seq`, as for proposals.

Binding and replay: the envelope's hashed payload must itself name `project_id`, `mission_id`, `need_seq` and carry
the same `values`. HS recomputes the hash over all of it. An envelope hash already used anywhere in the project is
refused, so evidence cannot be replayed into another mission or need. The author is taken only from the verified
operator token, never from the body. Only an open need with a structured `request` can be answered, and the values
must match the request's `kind` and `quantity`.

HS appends `evidence_supplied` (author: the person) with the need's seq, the envelope hash, the values and, when
`expected` was given, an HS comparison: `within | outside | not_comparable`.

- `within` or `not_comparable`: the need is resolved. It no longer blocks READY, and the phase returns to
  `EVALUATING` when no other need stands. READY then also needs a `device_plan` and `device_engineering` evaluation
  recorded **after** the `evidence_supplied` event, as after a repair: new facts invalidate earlier checks.
- `outside`: the need stays open, marked `contradicted`. The reading is recorded and the agent may repair.

A resolved need can no longer be cited for a `BLOCKED_*` terminal.

### Using it

- A `dimensional` need's `request.target` must be a library module id in the candidate. Its value becomes usable as
  that module's override, exactly like an intake `measurement`, validated by the planner's own spec validation. It
  does not replace an intake measurement for the same key; a conflicting one is refused.
- A repair is allowed after a failing plan (as today), after an engineering review with errors, or after an
  `evidence_supplied` event since the candidate's latest repair.
- An `electrical` value for a donor's signal is shown in the donor reading with grade `person_measurement` for this
  mission. It does **not** rewrite the donor contract file. Promoting it into the contract stays the existing
  evidence workflow's job, with its own review.
- A `boot_log` is stored as text with its hash. HS does not interpret it. The agent may read it and propose a repair.
- An `outside` comparison is recorded. It is a fact for the agent, not a verdict.

### What it may never do

- Grant flashing, power-on or field authority.
- Be posted by an agent or without an operator token.
- Change a terminal mission.

## Mission view additions

- `donors`: HS's donor reading, with findings and person measurements per donor, each with its grade.
- `needs`: every evidence need with its request, `need_state` `open | resolved | contradicted`, and the evidence
  that answered it.
- Terminal `grounding` gains `hs_donor_contract` (only when the cited need's request names a specific donor signal
  still missing an accepted measurement in the mission view) and `hs_donor_reading`.

## Tests the implementation must carry

- An intake donor is a reference. An embedded contract refuses the open. `donor_read` is written before `accepted`
  and reused on retry. A donor with no stored contract reads `unknown`. A stored contract claiming `measured` +
  `accepted` with evidence ids HS cannot find grades lower than `person_measurement`.
- READY is refused for a candidate using an unverified donor, naming the missing facts. It is allowed when the donor
  is verified and the usual checks pass.
- `finding_offered` by an agent is recorded as `re_observation`, including `method: document`. Attempts to set
  `accepted`, `measured`, a system or human author, or a grade field are refused. A finding never satisfies READY's
  donor rule and never grounds a blocker.
- `evidence_supplied` requires a human operator token (403 without, 401 unknown). An agent cannot post it through
  `/events`. A bad envelope hash, an envelope bound to another mission or need, a reused envelope, or values that
  differ from the envelope's are refused. A resolved need stops blocking READY only once a plan and engineering
  review run after it. An `outside` reading keeps the need open. A dimensional value becomes a usable override for
  its named module only. A resolved need cannot be cited for a blocker.
- A terminal mission refuses evidence. Nothing here sets an authority flag.
- The red-team rule holds: no route lets an agent raise a grade.

## Frozen for later

- Wiring donor blocks into the device planner as first-class modules (needs donor pin geometry and electrical
  contracts in planner form).
- Running RE tools from HS (the operator integration itself). This design only receives their findings.
- Promoting mission-supplied measurements into the shared donor contract (the existing evidence review owns that).
