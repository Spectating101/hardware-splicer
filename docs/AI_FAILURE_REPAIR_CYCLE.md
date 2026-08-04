# AI Failure Repair Cycle

The AI Failure Repair Cycle adds one bounded model turn after a persisted software preview fails. It is the first Hardware Splicer loop that can observe deterministic failure evidence and propose a successor candidate without rewriting history.

It is not an autonomous retry loop.

## Eligible failures

Repair is available only when:

- the parent action type is `run_guided_plan` or `run_compose`;
- the parent action has persisted status `failed`;
- the attached tool result also has status `failed`;
- session and action identities match the tool result;
- the tool result preserves the nonautomatic, fail-closed authority boundary;
- the request names the exact current project revision.

A successful preview, accepted-but-not-run proposal, missing tool result, mismatched identity, or authority-elevating result is refused.

## Repair context

The model receives a bounded context containing:

- project and current revision identity;
- original mission and constraints;
- parent requirements, open questions, and architecture candidates;
- failed action identity, rationale, inputs, and source IDs;
- persisted failure summary and error;
- project-relative artifact identity, SHA-256, and byte count;
- registered and parsed source descriptors from the parent session context;
- explicit repair and physical-authority policy.

The repair path does not read the failed artifact bytes or registered raw source bytes. Raw-content fields are omitted recursively. Large contexts drop parser runs and then nonessential parent details before refusing the request.

## Model contract

The `design_repair` model profile runs once and must return:

- one repair summary;
- proposed corrected or additional requirements;
- unresolved questions;
- exactly one successor architecture candidate;
- at least one proposed action;
- a `revise_candidate` proposal.

A later `run_guided_plan` or `run_compose` may also be proposed. It remains unaccepted and cannot execute until a human records a fresh decision.

The successor candidate records lineage to:

- the parent AI session;
- the failed action;
- the failure digest;
- the repair iteration.

## Persistence

`POST /v1/projects/{project_id}/ai-sessions/{session_id}/actions/{action_id}/repair`

creates a new AI session and one optimistic project revision. The failed parent action and tool result remain unchanged. The parent action receives only a repair-session reference and status indicating that a successor was proposed.

Repeating the request for the same parent action returns the existing repair session without another model call or project revision.

## Schema

`GET /v1/engineering/ai/repair/schema`

reports the repairable actions, one-turn/one-successor contract, preservation rule, fresh-decision requirement, and closed physical-authority state.

## Authority boundary

Every repair session and action remains `proposed` and preserves:

- `automatic_execution: false`;
- `physical_authority_unchanged: true`;
- fabrication authority false;
- firmware flashing authority false;
- power-on authority false;
- motion authority false;
- operational authority false;
- release authority false.

A repair hypothesis is not evidence that the failure is resolved. Only a later deterministic preview can produce new software evidence, and even a passing preview cannot grant physical authority.

## Current limitations

- One repair session per failed action.
- No automatic model/tool retry chain.
- No multi-model voting or repair comparison.
- No ERC-only or DRC-only repair adapter.
- No preview artifact byte ingestion.
- No repair button or lineage view in AI Studio in this backend tranche.
- No multi-user reviewer identity or RBAC.
- No green or deployability claim until exact-head CI completes.
