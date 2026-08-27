# AI Project Conversation

AI Project Conversation is Hardware Splicer's revision-aware engineering interface. It lets a user continue a project session with ordinary questions while keeping answers grounded in the exact current project revision and keeping every suggested change inside the existing proposal/review/preview workflow.

Conversation is not an alternative project database.

## Turn boundary

A turn is created through:

`POST /v1/projects/{project_id}/ai-sessions/{session_id}/turns`

The request includes:

- the exact expected project revision;
- one user message;
- an optional client request identity for idempotence;
- an optional model override;
- a bounded number of additional proposals.

The server loads the latest revision, resolves the named AI session, compiles a bounded current context, invokes the configured text model once, validates the response, appends the turn and any typed proposals to the session, and creates one optimistic project revision.

Repeating the same nonempty client request identity returns the existing turn without another model call or revision.

## Grounded context

The turn context includes:

- current project and revision identity;
- registered and parsed source descriptors;
- bounded parser results;
- session mission, constraints, requirements, candidates, and open questions;
- action status and human decisions;
- bounded tool-result summaries, errors, and artifact identities;
- repair lineage;
- up to twelve prior conversation turns;
- an explicit registry of evidence IDs the model may cite.

Registered raw file content is not included. Context reduction first drops parser runs, then reduces turn history, then reduces tool summaries before refusing an oversized request.

## Response contract

The model returns one JSON object containing:

- a direct answer;
- an answer kind: `technical_answer`, `decision_briefing`, or `clarification_request`;
- one or more evidence references;
- blockers or missing evidence;
- zero or one recommended action;
- a bounded list of additional proposed actions.

Evidence references use a typed `{kind, id, reason}` structure. Supported kinds are:

- `source`;
- `requirement`;
- `candidate`;
- `action`;
- `tool_result`;
- `session`;
- `project_revision`.

Every cited ID is checked against the current context registry. Unknown sources, invented action IDs, and unsupported evidence kinds are rejected before persistence.

## Project-changing suggestions

A conversational recommendation cannot modify project state directly. Any change is converted into the same typed AI action used elsewhere in Hardware Splicer:

- stable action identity;
- exact project revision;
- allowed action type;
- rationale and bounded inputs;
- validated source identities;
- `origin_turn_id`;
- status `proposed`;
- no tool result;
- no automatic execution;
- no authority effect.

The proposed action is appended to the session action list. It must receive a fresh human accept/reject decision and, where eligible, a separate software preview.

## Conversation history

Persisted turns record:

- user message and assistant answer;
- exact project revision;
- provider and model;
- prompt, context, and response hashes;
- usage/cache metadata;
- evidence references;
- blockers;
- recommended action identity;
- all proposed actions;
- physical-authority closure.

Only a bounded tail of prior turns enters later model context. The complete persisted history remains in the project snapshot.

## Schema

`GET /v1/engineering/ai/conversation/schema`

reports the turn schema, allowed evidence kinds, typed-proposal rule, fresh-decision requirement, and closed physical-authority state.

## Authority boundary

Conversation answers may explain, compare, recommend, or request clarification. They may not establish engineering truth or grant permission.

Every turn preserves:

- `conversation_is_project_truth: false`;
- `automatic_execution: false`;
- `physical_authority_unchanged: true`;
- fabrication authority false;
- firmware flashing authority false;
- power-on authority false;
- motion authority false;
- operational authority false;
- release authority false.

A conversational answer is guidance tied to cited project evidence. A typed action, deterministic result, physical observation, and authorization remain separate objects.

## Current limitations

- No token streaming.
- No semantic search over an unbounded conversation archive.
- No automatic project-wide briefing export.
- No multi-user identity or RBAC for turns.
- No voice interface.
- No browser-level product test in this backend tranche.
- No green or deployability claim until exact-head CI completes.
