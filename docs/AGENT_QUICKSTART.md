# Agent quickstart: one salvage mission

Your job is useful engineering from admitted resources: investigate the donor,
compare reuse options, propose designs and ask HS to check them. You are not
the operator, a measuring instrument or a physical-approval authority.

## Connection and starting packet

The host prepares the project and mission, obtains human acceptance of its
software-check budget, and gives you:

- the goal and source-backed donor material;
- the exact project ID and mission ID;
- the canonical backend MCP connection.

No human operator token belongs in the agent packet. An unaccepted mission is
an onboarding dependency, not permission to accept it yourself.

Host setup uses Python 3.12+ and a dedicated environment. The canonical MCP SDK
and historical compile-only SDK are different major versions; do not upgrade an
existing legacy environment in place or combine both optional extras:

```bash
python3 -m venv .cache/hardware-splicer/backend-mcp
.cache/hardware-splicer/backend-mcp/bin/python -m pip install -e '.[dev,backend-mcp]'
PYTHONPATH=src .cache/hardware-splicer/backend-mcp/bin/python -m hardware_splicer.backend_mcp_server
```

Configure `HARDWARE_SPLICER_PROJECT_ROOT` to the prepared project store before
starting the MCP process. Stdio serves the canonical backend in that process;
starting a separate HTTP API is unnecessary. Keep demo stores isolated from
ordinary projects. This is **not** the historical `hardware_splicer.mcp_server`
compile-only surface.

## Discover only what you need

1. Call `hs_backend_status({})`.
2. Call `hs_backend_task_manifest({"task": "salvage_fabrication"})`.
3. Call `hs_backend_call` with the returned `start_here.operation_id` and the
   provided `project_id`/`mission_id` in `path_params`.

The compact manifest indexes all supported workflow operations. Do not list
the entire backend or request all schemas just to start. For an unfamiliar
operation, call `hs_backend_describe_operation({"operation_id": "<returned ID>"})`.
The full manifest remains available with `include_schemas: true`.
For document admission/page-addressed claims or evidence-dependency review, use
the related task manifests named in this index; they share the same canonical
backend. Admitting a document does not rewrite an accepted mission's frozen donor
contract or establish a physical measurement.

## Work from canonical context

The context includes the inventory, HS's inventory reading, structured
requirements, donor uncertainties, investigation queue, candidate/check
summaries, budgets, evidence needs and `next_state`.

- Unknown junk stays unknown. Use parts-reading, documents and bounded findings;
  do not turn a visual analogy into a catalog part or inherit its pinout.
- Drafting/spec discovery are available in this same manifest. A catalog draft
  is only a starting point and is not an arbitrary-donor design engine.
- Before proposing an event, describe the events operation. It supplies a
  discriminated schema and examples for candidates, repairs, findings, evidence
  needs and terminal proposals. Replace placeholder content with your actual
  design/observations; an empty example spec is not a working design.
- Candidate specs must omit backend-owned authority keys entirely, including
  `physical_correctness`, even when its proposed value is `UNPROVEN`. State
  limitations in ordinary proposal text; HS supplies its own authority labels.
- Send `json_body` containing `event`, `author: {"kind":"agent","id":"<your ID>"}`
  and `expected_event_seq` from a fresh context. Supply only the path parameters
  named in the operation's path, not every ID you have.
- Run candidate checks through the mission's `/run` operation. Its schema lists
  the supported checks. For readiness, HS needs a clean plan and a subsequent
  engineering review. Read hashed run output for findings and repair suggestions.
- Visual drafts remain pending human confirmation. Continue independent
  software work; do not promote the draft to donor or measured truth.

After interruption, reload context. Read the full mission when you need a
candidate's stored spec and its hashed run artifact when you need check details.
`recorded_checks` summarizes recorded results. Its `current` flag uses HS's
canonical repair/evidence boundary; a current check is still **not** a readiness
verdict or physical authority.

## Current document and design limits

Source admission can retain a Markdown evidence packet, but page-addressed
document inspection/claim registration currently requires an actual PDF by
signature. Do not rename a packet to `.pdf` or present host paraphrases as
manufacturer-document extraction.

The device planner accepts its catalog module schema, not arbitrary intact
consumer electronics or mechanical-only reuse designs. If that domain does
not fit, use the related bounded pre-fabrication workflow to persist the actual
alternatives, design constraints and next actions. Do not substitute a catalog
development board just to make a check pass. A bounded plan is not an executable
adapter, CAD or a validated build package.

Read the bounded plan's `assessment.blockers` as well as existing snapshot
`engineeringBlockers`. The plan response's `engineering_blockers` currently
reports the latter; an empty list does not mean the proposal has no blockers.

## Errors, waiting and delivery

- **409:** reload context; handle a stale event sequence or wait for a busy
  operation. Never blindly replay a mutation.
- **422:** use the error message and exact schema/example to correct the
  request. Do not retry the same invalid payload.
- **403:** respect the human boundary; do not seek or impersonate an operator.
- Ask for specific missing evidence. If you intend to resume after a person
  answers, leave the mission waiting rather than proposing a terminal blocker.
  Research and independent design work should not stop merely because one
  physical fact is unavailable.
- A terminal state is recorded only if the backend accepts its grounding.
  After READY, build and download the deterministic package through the
  manifest's package operations; staging opens a review, never approves it.

Software/model/CAD success does not prove physical correctness.

Deeper semantics: [AGENT_MISSION.md](AGENT_MISSION.md).
Cold-trial acceptance: [SALVAGE_AGENT_TRIAL.md](SALVAGE_AGENT_TRIAL.md).
Historical compose examples: [legacy quickstart](LEGACY_COMPOSE_AGENT_QUICKSTART.md).
