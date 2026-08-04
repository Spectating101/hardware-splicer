# JARVIS Engineering Console

The JARVIS Engineering Console is the ordinary-user conversational surface for Hardware Splicer's revision-aware AI sessions. It sits above the same project, source, action, preview, and repair records used by AI Project Studio.

JARVIS is an interface to governed engineering state, not a second source of truth.

## Workspace loading

The console loads:

- one project ID;
- one AI session ID;
- the latest project revision;
- the persisted session at that revision;
- registered-source and parser-run counts;
- requirements, architecture candidates, actions, and prior conversation turns;
- current project physical-authority fields.

The console does not keep a private browser-only engineering history.

## Asking a question

Each question sends:

- the exact current project revision;
- the current project and session identities;
- one user message;
- a client-generated request identity;
- a bounded proposal count.

The backend returns the updated revisioned session. The console replaces its local session view with that persisted response and advances to the returned project revision.

A turn is therefore visible again after reloading the session; it is not merely transient chat UI.

## Conversation timeline

Every persisted turn displays:

- user question;
- revision used for the turn;
- JARVIS answer and answer kind;
- typed evidence references with reasons;
- declared blockers and missing evidence;
- recommended proposal identity, when present.

The timeline comes from `conversationTurns` in the revisioned AI session.

## Proposal queue

Any project-changing recommendation produced by a turn is already converted by the backend into a typed `proposed` action. The console shows pending actions with:

- action type;
- title and rationale;
- originating turn identity;
- explicit awaiting-review state.

The console links to AI Project Studio for accept/reject decisions and eligible deterministic previews. JARVIS itself does not silently accept or execute the proposal.

## Project and physical boundary

The console keeps visible:

- project revision;
- source and parser counts;
- session kind and model identity;
- requirement/candidate/action counts;
- fabrication, flashing, power-on, motion, and release gates.

The interface states that JARVIS is guidance rather than project truth. Human review, deterministic preview, physical evidence, and authority are separate stages.

## Navigation

`/engineering/jarvis`

is promoted in the shared engineering navigation alongside AI Studio. AI Studio remains the review and execution workspace; Source Lab, planning, storage, and inspection remain specialist surfaces.

## Proxy boundary

The Next.js proxy forwards authenticated requests to:

`POST /v1/projects/{project_id}/ai-sessions/{session_id}/turns`

It preserves the exact request body and structured backend failures.

## Authority boundary

The console contains no control for:

- automatic execution;
- automatic retry chains;
- LLM-first compose execution;
- Gerber export;
- fabrication authorization;
- firmware flashing authorization;
- power-on authorization;
- motion authorization;
- operational or release authorization.

A JARVIS recommendation may create a proposal awaiting review. It cannot create verified evidence or authorize the physical system.

## Current limitations

- Project and session identities are entered manually rather than deep-linked from AI Studio.
- No token streaming.
- No voice input/output.
- No browser-level test against a running backend.
- No automatic Engineering Package briefing export.
- No multi-user identity/RBAC display.
- No green production-build claim until exact-head CI completes.
