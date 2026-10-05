# Finding provenance

Read-only projection of how each persisted finding was **established**. It does
not say whether a finding is correct, complete, or authorised. Authority is
never upgraded: every finding carries `authority_ceiling: "observed"`.

If stored fields do not record how a finding was produced, the kind is
`unknown`. Unknown is the default. Provenance is never guessed or flattering.

## Scope

This endpoint labels only findings derivable from persisted data:
`engineeringSystemGraph` node blockers, failed session actions,
traceability issues computed from the stored machine project,
write-time ledger rows in `engineeringFindings`, and measured findings
declared by `finding_links` on non-simulated physical measurement
records in `physicalValidation`. A finding a client derives some other
way (for example a UI fallback graph) has no entry here. Clients must
treat that as provenance-not-recorded, never as deterministic.

## Endpoint

```http
GET /v1/projects/{project_id}/findings?revision=<int optional>
```

The handler loads the latest revision, or the requested revision, through
existing `ProjectStore` read methods and projects `envelope["snapshot"]`. It
does not write.

Success body:

```json
{
  "ok": true,
  "project_id": "…",
  "revision": 1,
  "findings": [
    {
      "finding_id": "finding-<16 hex>",
      "category": "failed_check",
      "object_id": null,
      "text": "…",
      "provenance": {
        "kind": "unknown",
        "basis": "…",
        "source_ref": "action-…",
        "authority_ceiling": "observed"
      }
    }
  ],
  "unmatched_links": []
}
```

`finding_id` is `finding-` plus the first 16 hex characters of SHA-256 over
canonical JSON of `[category, object_id or "", text, source_ref or ""]`.

Errors reuse the project API contract `{detail: {type, message}}`
(`not_found`, `invalid_identifier`, `invalid_request`, …). A non-integer or
non-positive `revision` query is `422 invalid_request`.

## Findings collected

| Category | Stored source |
|----------|----------------|
| `failed_check` | `engineeringAiSessions[].actions[]` with `status` equal to `failed`, and write-time `design_quality_gate` ledger rows |
| `object_blocker` | `engineeringSystemGraph.nodes[].blockers` (the persisted field the UI reads onto a canonical object) |
| `release_blocker` | Write-time `release_assessment` ledger rows recorded from `MachineProject.assess_release` blockers |
| `measured_finding` | `physicalValidation` envelopes whose record carries an `establishes` finding link (see `physical` below) |
| `traceability_issue` | `MachineProject.traceability_issues()` from `machineProject` / `machine_project`, or one validation finding when that stored object fails `MachineProject` validation, or one finding when a persisted ledger row or measurement record is malformed |

Identical `(category, object_id, text)` rows are collapsed. A persisted
ledger row wins the collision and keeps its write-time `provenance` and
`source_ref`. Order is `failed_check`, then `object_blocker`, then
`release_blocker`, then `measured_finding`, then `traceability_issue`,
then `object_id`, then `text`.

## Derivation table

A kind is assigned only when the named stored field qualifies. Otherwise
`unknown`.

### `failed_check`

Collect the recorded type from `action.action_type`, `action.tool`,
`tool_result.action_type`, and `tool_result.tool` (non-empty values only).
If those fields contain two or more distinct values, the record is
inconsistent: kind is `unknown` and `basis` is
`recorded action_type/tool fields disagree`. Neither field qualifies on
its own when they disagree. If there is exactly one distinct value, use
that value as follows.

| kind | Stored field that qualifies |
|------|-----------------------------|
| `deterministic` | the single recorded type is in `EXECUTABLE_AI_PREVIEW_ACTIONS` (`run_guided_plan`, `run_compose`) **and** a `tool_result` is recorded (the action actually ran) |
| `model_derived` | the single recorded type is in `ALLOWED_AI_ACTION_TYPES` and `tool_result` is `None` (never executed), including an executable type that was only proposed |
| `unknown` | any other failed action, including an unimplemented type that recorded a `tool_result`, or disagreeing type/tool fields |

`source_ref` is `action_id`.

### `object_blocker`

Checked in this order; the first qualifying stored record wins.

| kind | Stored field that qualifies |
|------|-----------------------------|
| `human` | an AI-session `actions[].decision` with a `reviewer` (or `actor`) whose `note` / `message` / `text` equals the blocker |
| `model_derived` | the blocker text appears in a session's recorded output (`blockers`, `open_questions`, `risks`, including `conversationTurns[]`) and that session has both `provider` and `model` recorded |
| `unknown` | none of the above |

`source_ref` is the decision `action_id` or the `session_id`. A session
missing `provider` or `model` never yields `model_derived`. Citing an
evidence record on the object (including `simulated: false`) does not
establish the blocker.

### `traceability_issue`

`traceability_issues(project)` is a pure deterministic function over the
stored `MachineProject`. Every issue is therefore `deterministic` by
construction. Supporting `EvidenceRef.basis` values are ignored: they
describe how evidence was acquired, not how the issue was computed.

| kind | Stored field that qualifies |
|------|-----------------------------|
| `deterministic` | the issue exists in `traceability_issues()` output |
| `deterministic` | a non-empty stored `machineProject` / `machine_project` fails `MachineProject.model_validate` (`ValidationError`, `ValueError`, or `TypeError`) |

For a valid stored project, `source_ref` is `issue.code` (for example
`unverified_requirement`) and `basis` is
`computed by traceability_issues() over the stored machine project`.

If validation rejects the stored object, the endpoint emits exactly one
finding instead of dropping the project: `object_id` is null, `source_ref`
is `machine_project_invalid`, `basis` is
`MachineProject validation rejected the stored machine project`, and `text`
is `Stored machine project fails validation: ` plus the validation
message(s) joined with `; `, truncated to 500 characters, with no stack
traces or pydantic URLs. Missing or empty `machineProject` yields no
traceability findings. Codes such as `duplicate_id` and `invalid_ref` raise
inside `validate_graph_references`, so they appear only through this
validation finding — not as silent omissions.

### `physical`

`physical` is reachable only through `finding_links` on a persisted
`PhysicalEvidenceRecord` inside `physicalValidation` envelopes
(`physicalValidation.audited_physical_evidence.envelopes[].record`).
Citing non-simulated evidence on an object does not establish a
physical finding.

A record qualifies only when all of the following hold:

- it validates as `PhysicalEvidenceRecord` (same write-time validators)
- `metadata.simulated` is exactly `false` (missing or `true` never qualifies)
- `authority` is `measured`, `verified`, or `authorized`
- for each `establishes` link: `passed` is `false` and `text` is present
  (at most 1000 characters)

Each qualifying `establishes` link emits category `measured_finding`
with `object_id` and `text` from the link,
`source_ref` equal to `evidence_id`, `kind` `physical`,
`authority_ceiling` `observed`, and `basis`
`non-simulated measurement record states that it establishes this finding`.
`finding_id` is the shared id over
`(category, object_id, text, source_ref)`.
When two or more qualifying records establish the same `(object_id, text)`,
one finding is kept: `source_ref` is the first `evidence_id` in sorted
order, and each remaining id is appended to `physical_evidence` as
`{evidence_id, relation: "establishes", passed: false, authority}`.

`physical` means only that a non-simulated measurement record states
that it establishes this finding. It does not close a gate, upgrade
authority, or change release, fabrication, or power-on state. Simulated
evidence can never produce a physical finding.

A qualifying passing record (`passed` true, same validators,
non-simulated, measured/verified/authorized) may carry `clears` links.
Those links **annotate** a matching existing finding
(`physical_evidence: [{evidence_id, relation: "clears", passed: true, authority}]`).
The finding stays in the list. Its provenance kind is unchanged.
A `clears` annotation is a measurement claim, not closure: it never
removes the finding, never closes a gate, and never changes
release/fabrication/power-on state.

Unmatched `clears` links are not dropped. The API payload includes
`unmatched_links: [{evidence_id, finding_id}]`.

Invalid, simulated, or malformed measurement records are ignored for
emission and surfaced as one `traceability_issue` with kind `unknown`,
basis `malformed or non-qualifying measurement record ignored`, and
`source_ref` `physicalValidation`.

## Persisted ledger

Deterministic producers write `snapshot["engineeringFindings"]` at persist
time. The projection never invents a `deterministic` kind for these rows.
A persisted row is trusted only when `validate_ledger_entry` accepts it
(same function used at write time).

**Trust limit.** The ledger is trusted exactly as far as whoever can write
snapshots is trusted. `PUT /v1/projects/{id}/snapshot` is a legitimate
full-snapshot write and may store client-supplied `engineeringFindings`;
those rows are not rewritten on PUT. They are validated on read. A plan
or other request-built snapshot constructor must never copy ledger rows
from untrusted plan input — only from the previously persisted snapshot.

| Field | Meaning |
|-------|---------|
| `finding_id` | Same function as the projection (`finding-` + 16 hex of SHA-256 over `[category, object_id or "", text, source_ref or ""]`) |
| `category` | `failed_check`, `object_blocker`, or `release_blocker` |
| `object_id` | Canonical object, or `null` |
| `text` | Non-empty, at most `MAX_FINDING_TEXT` (1000) characters |
| `producer` | Allowlisted writer |
| `producer_run` | Non-empty action id or deterministic run label such as `assess_release@rev<N>` |
| `provenance` | `{kind: "deterministic", basis, source_ref, authority_ceiling: "observed"}` — no extra keys |
| `recorded_at` | ISO UTC only: must end in `Z` or `+00:00`. Other offsets and naive timestamps are rejected |

Replace-per-producer: `replace_producer_findings` deep-copies the snapshot,
leaves other producers untouched, and replaces **all** previous rows of
this producer with the new run. A producer's findings represent its latest
run. Earlier runs live on earlier immutable revisions. An empty replacement
clears that producer (a fixed design quality gate writes `[]`).

Writers:

| Producer | When | Category | `source_ref` |
|----------|------|----------|--------------|
| `design_quality_gate` | The tool executor persists an executed action whose `tool_result` carries a design-quality gate (including a failed compose that still recorded a gate) | `failed_check` | `action_id` |
| `release_assessment` | `save_engineering_plan` recomputes `MachineProject.assess_release` over the persisted `machineProject` (the project's stored `requested_release_state`). Caller-supplied `scoped_release_assessment` is ignored | `release_blocker` | `blocker.code` |

`validate_ledger_entry` rejects unknown category, empty or over-long text,
`kind != "deterministic"`, producer outside the allowlist, empty
`producer_run`, missing or non-UTC `recorded_at`,
`authority_ceiling != "observed"`, `finding_id` that does not match the
recomputed id, and unknown extra keys. A malformed persisted row, a
non-list `engineeringFindings` value, or a non-mapping list element is
ignored and surfaced as exactly one finding: category
`traceability_issue`, kind `unknown`, basis
`malformed persisted finding entry ignored`, `source_ref`
`engineeringFindings`. Nothing is dropped silently.

Over-long blocker text is not clipped. Hooks call `bound_finding_text`,
which truncates to 999 characters plus `…` and appends
` (message truncated)` to `basis`.

## Malformed ledgers

A non-list `engineeringFindings` value (`None`, a string, a dict, …) is
malformed, not absent. Plan-save copies that key unchanged whenever it is
present on the previous snapshot so the read projection can still emit the
single malformed-entry finding. A producer's next run **replaces** a
malformed ledger (self-healing). Other producers' rows are kept only when
the existing value is a well-formed list. The malformed value remains
visible on the earlier immutable revision until that next producer run.

`engineering_snapshot` / `save_engineering_plan` carry
`engineeringFindings` **only** from the previous persisted snapshot.
A plan-supplied `engineeringFindings` key is ignored and not echoed onto
`engineeringPlan`. The executor writes gate findings from an executed
`tool_result`, not from the request. Pre-fab request bodies cannot
include the ledger (`extra=forbid`) and quarantine does **not** treat it
as a generated plan surface.

## Authority

`authority_ceiling` is the constant `observed` from
`engineering_review_identity.AUTHORITY_CEILING`. A finding can describe how it
was established. It cannot carry or imply a higher engineering authority.
