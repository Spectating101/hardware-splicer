# AI Studio Preview Results

AI Project Studio now exposes the first complete review-to-preview product loop on top of the proposal and tool-executor contracts.

## User flow

1. Load one revisioned project.
2. Create or reload a project-bound AI session.
3. Inspect proposed requirements, architecture candidates, and typed actions.
4. Accept or reject one proposal.
5. For an eligible accepted action, run one separate software preview.
6. Inspect the resulting status, summary, and hashed project artifact identity.

Proposal acceptance and preview execution remain separate optimistic project revisions.

## Eligible previews

The interface offers **Run software preview** only when all of the following are true:

- action status is `accepted`;
- the action type is `run_guided_plan` or `run_compose`;
- no tool result is already present.

Accepted non-executable actions remain visible and explicitly state that their action type is outside the current preview boundary.

## Result cards

A persisted tool result is rendered inside its action card with:

- succeeded or failed status;
- bounded structured summary;
- project-relative artifact path;
- server-computed SHA-256;
- artifact byte count;
- explicit software-evidence-only label.

The UI does not expose an arbitrary absolute server path or raw artifact bytes.

## Proxy boundary

The authenticated Next.js proxy forwards:

`POST /v1/projects/{project_id}/ai-sessions/{session_id}/actions/{action_id}/execute-preview`

The request includes the exact current project revision. Stale requests are refused by the backend before tool execution.

## Authority boundary

The interface keeps the distinction visible:

- accepting a proposal is not executing it;
- a software preview is not fabrication;
- a successful compose result is not physical verification;
- no preview grants flashing, power-on, motion, operational, or release authority.

Physical gates remain displayed separately from AI action state.

## Current limitations

- No browser-level test against a running backend.
- No artifact download route in this tranche.
- No side-by-side result comparison yet.
- No failure-fed repair turn yet.
- No ERC-only or DRC-only preview button.
- No multi-user reviewer presentation or RBAC.
- Frontend contract, strict TypeScript, and production build remain subject to exact-head CI.
