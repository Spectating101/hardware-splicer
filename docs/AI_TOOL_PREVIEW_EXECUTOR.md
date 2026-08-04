# AI Tool Preview Executor

The AI Tool Preview Executor is the first execution layer beneath Hardware Splicer's project-bound AI sessions. It converts an explicitly accepted proposal into one bounded software-side preview and appends the result to the same revisioned session trace.

It is not a general agent runtime.

## Executable boundary

Only two AI action types are executable in this tranche:

- `run_guided_plan`
- `run_compose`

All other proposal types remain non-executable.

A preview requires:

- the current exact project revision;
- an existing project-bound AI session;
- an action pinned to an existing project revision;
- `status: accepted`;
- a persisted human decision record with reviewer, decision time, and `executed: false`;
- no prior tool result.

Changing an action status without the persisted decision record is insufficient.

## Guided-plan preview

`run_guided_plan` loads the original pinned project revision, derives a bounded intake from the session mission, constraints, and project summary, combines registered and parsed source descriptors, and calls the deterministic guided engineering planner with vision skipped.

The complete result is written as a bounded project-local JSON artifact. The session receives a summary of readiness, status, manufacturing closure, software execution preview, missing information, and ordered-step count.

This preview does not overwrite the project's current guided plan.

## Compose preview

`run_compose` calls the existing compose dispatcher inside a project-local run directory.

The executor forces:

- `allow_llm_first: false`;
- `export_gerber: false`;
- no arbitrary shell operation;
- no device access;
- no physical action.

The full compose result or bounded failure record is written as a project-local JSON artifact. The session receives a summary of build mode, build identity, selected modules, design-quality gate, warnings, and failure state.

## API

- `GET /v1/engineering/ai/tools/schema`
- `POST /v1/projects/{project_id}/ai-sessions/{session_id}/actions/{action_id}/execute-preview`

A successful or failed preview creates one optimistic project revision containing the tool result. Repeating the same request after the result is stored returns the existing result without another tool call or project revision.

## Artifact boundary

Artifacts are stored beneath:

`ai_tool_runs/{session_id}/{action_id}/`

Each stored JSON artifact has a server-computed SHA-256 and byte count. Result JSON is capped at 16 MiB and published atomically.

The executor returns project-relative artifact identities. It does not expose arbitrary server paths through this API.

## Authority boundary

Every result explicitly preserves:

- `automatic_execution: false`;
- `physical_authority_unchanged: true`;
- fabrication authority false;
- firmware flashing authority false;
- power-on authority false;
- motion authority false;
- operational authority false;
- release authority false.

A passed planner or compose preview is software evidence only. It cannot authorize fabrication or physical operation.

## Current limitations

- Only guided planning and deterministic compose are executable.
- Registered structured robot source blobs are not rematerialized by this executor; it uses persisted source and parser descriptors.
- No ERC-only or DRC-only action yet.
- No model-driven repair round yet.
- No UI execution button yet.
- No session/action lock for concurrent operators.
- No deployment quota for generated preview artifacts.
- No browser-level test against a running backend.
- Real planner and compose behavior remains subject to exact-head CI and installed-tool availability.
