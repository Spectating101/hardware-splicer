# AI Studio Repair Lineage

AI Studio now exposes the bounded failure-repair cycle as part of the same project workspace used for proposal review and software previews.

## Visible state machine

The interface presents four separate project states:

1. `proposed` — the model suggests an action;
2. `accepted` or `rejected` — a human records a decision;
3. `completed` or `failed` — an eligible accepted software preview returns evidence;
4. `failure_repair` — one separate successor session is proposed from a persisted failure.

No state transition automatically advances to the next.

## Repair control

**Propose bounded repair** appears only when:

- the action status is `failed`;
- the persisted tool result status is `failed`;
- the action type is `run_guided_plan` or `run_compose`.

If the backend already has a repair session for that action, the same control is labeled **Open repair successor** and the idempotent backend response loads the existing child session.

There is no automatic retry control.

## Child session presentation

After repair creation, AI Studio loads the child session and shows:

- `failure_repair` session identity;
- design-repair provider/model identity;
- repair summary;
- proposed corrected requirements;
- exactly one successor candidate;
- candidate lineage to the failed action and failure digest;
- fresh proposed actions requiring ordinary accept/reject decisions;
- repair iteration and parent session identity.

**Open failed parent** reloads the immutable parent session so the user can inspect the original action and tool result.

## Proxy boundary

The Next.js route forwards authenticated requests to:

`POST /v1/projects/{project_id}/ai-sessions/{session_id}/actions/{action_id}/repair`

The browser supplies the exact current project revision and a bounded maximum action count. Structured backend failures are preserved.

## Authority boundary

The UI states that proposal, decision, preview, and repair are separate revisions. It does not expose:

- automatic execution;
- automatic retries;
- LLM-first compose execution;
- Gerber export;
- fabrication authorization;
- firmware flashing authorization;
- power-on authorization;
- motion authorization;
- operational or release authorization.

A successor remains a proposal until reviewed, and its later preview remains software evidence only.

## Current limitations

- No side-by-side visual diff of parent and successor artifacts.
- No comparison across multiple repair hypotheses.
- No automatic navigation history beyond explicit parent-session loading.
- No browser-level test against a running backend.
- No green production-build claim until exact-head CI completes.
