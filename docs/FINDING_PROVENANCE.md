# Finding provenance

Read-only projection of how each persisted finding was **established**. It does
not say whether a finding is correct, complete, or authorised. Authority is
never upgraded: every finding carries `authority_ceiling: "observed"`.

If stored fields do not record how a finding was produced, the kind is
`unknown`. Unknown is the default. Provenance is never guessed or flattering.

## Scope

This endpoint labels only findings derivable from persisted data:
`engineeringSystemGraph` node blockers, failed session actions, and
traceability issues computed from the stored machine project. A finding a
client derives some other way (for example a UI fallback graph) has no
entry here. Clients must treat that as provenance-not-recorded, never as
deterministic.

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
  ]
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
| `failed_check` | `engineeringAiSessions[].actions[]` with `status` equal to `failed` |
| `object_blocker` | `engineeringSystemGraph.nodes[].blockers` (the persisted field the UI reads onto a canonical object) |
| `traceability_issue` | `MachineProject.traceability_issues()` from `machineProject` / `machine_project`, or one validation finding when that stored object fails `MachineProject` validation |

Identical `(category, object_id, text)` rows are collapsed, keeping the first
`source_ref`. Order is `failed_check`, then `object_blocker`, then
`traceability_issue`, then `object_id`, then `text`.

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

### Reserved: `physical`

`physical` remains an allowed provenance kind, but no current persisted
field links a blocker or failed check to a specific bench measurement.
An object that cites non-simulated evidence can still carry an
analysis-derived blocker. Until bench capture records which finding a
measurement establishes, `physical` is unreachable. That is a known gap,
not a feature.

## Authority

`authority_ceiling` is the constant `observed` from
`engineering_review_identity.AUTHORITY_CEILING`. A finding can describe how it
was established. It cannot carry or imply a higher engineering authority.
