# AI Project Orchestrator

Hardware Splicer's first project-bound AI orchestration layer creates revision-pinned engineering proposals from one persisted project boundary. It is deliberately narrower than a general autonomous agent.

## Contract

A session is pinned to:

- one project ID;
- one exact project revision;
- the registered source descriptors in that revision;
- persisted parser outputs in that revision;
- a mission and bounded constraint object;
- one model profile, provider, model, prompt version, and context digest.

The model may return:

- proposed requirements;
- open questions;
- at most three architecture candidates;
- a bounded list of typed proposed actions.

The initial action vocabulary is:

- `clarify_requirement`
- `identify_missing_evidence`
- `propose_architecture`
- `compare_architectures`
- `propose_components`
- `propose_interfaces`
- `generate_netlist_candidate`
- `run_guided_plan`
- `run_compose`
- `run_erc`
- `run_drc`
- `revise_candidate`
- `prepare_verification`
- `prepare_engineering_package`

No action is executed in this tranche. Accepting an action records a human decision only.

## API

- `GET /v1/engineering/ai/schema`
- `POST /v1/projects/{project_id}/ai-sessions`
- `GET /v1/projects/{project_id}/ai-sessions/{session_id}`
- `POST /v1/projects/{project_id}/ai-sessions/{session_id}/actions/{action_id}/decision`

Creating a session and recording a decision each use optimistic project revisions.

## AI Project Studio

`/engineering/ai-studio` is the first ordinary-user surface for the orchestrator.

A user can:

- load one revisioned project;
- inspect registered-source and parser-run counts;
- enter a plain-language engineering mission;
- provide structured constraints;
- choose a bounded model profile;
- create or reload an AI proposal session;
- inspect proposed requirements, open questions, and architecture candidates;
- inspect provider and model identity;
- accept or reject individual proposed actions;
- verify that every decision is recorded without tool execution.

Authenticated Next.js proxies preserve the project/session/action route boundary. Engineering navigation exposes AI Studio as the first product-facing workspace while the existing source, storage, planning, and inspector pages remain available as specialist surfaces.

## Context boundary

Registered raw file bytes are never sent through this project-context assembler. The model receives:

- source identity, hash, type, parser route, and authority ceiling;
- bounded parser output;
- selected project-plan summaries;
- mission and constraints;
- explicit fail-closed authority policy.

Fields used for raw content or binary bytes are removed recursively. Authority-bearing fields are forced false in model context.

The session persists the sanitized context, prompt/context/response digests, parsed proposals, provider/model identity, cache identity, and usage metadata. It does not persist registered raw file content through this path.

## Authority boundary

All model results have `proposed` authority. The orchestrator cannot grant or imply:

- fabrication authority;
- firmware flashing authority;
- power-on authority;
- motion authority;
- operational authority;
- release authority.

The session and every action state that automatic execution is false and physical authority is unchanged.

## Current limitation

This tranche does not yet execute the guided planner, compose engine, ERC, DRC, simulation, fabrication, firmware, or bench tools. The interface is contract- and production-build tested but has no browser-level test against a running backend. The next separate tranche should add an allowlisted executor for read-only planning and candidate validation, with each tool result appended to the same session trace and no automatic project or physical authority elevation.
