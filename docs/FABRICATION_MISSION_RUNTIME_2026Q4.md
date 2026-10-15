# Fabrication Mission Runtime — 2026 Q4

Status: **architecture / implementation contract**

This note defines the next bounded integration target for Hardware Splicer (HS). It does not claim that the runtime exists end to end today. It is deliberately written against the current project-agent, device-design, reclaim, evidence, and physical-authority machinery rather than proposing a replacement stack.

## Category thesis

Hardware Splicer should not optimize for being another PCB copilot.

The stronger product category is:

> **Mission-driven transformation of available hardware into a reviewable, evidence-bound build plan, using specialist design, reverse-engineering, simulation, and fabrication tools underneath HS while HS owns mission state, provenance, engineering truth boundaries, and physical authority.**

The target user input is not necessarily a schematic. It may be:

- a desired capability;
- a constrained budget;
- a pile of known parts;
- a donor device;
- an unknown or partially understood shipped artifact;
- a mixture of new components and reclaimed subsystems.

The target output is not "the AI says it works". The first terminal success state is:

`READY_FOR_HUMAN_BUILD`

with a revision-bound packet that says what was inferred, what was deterministically checked, what remains assumed, and what still requires physical evidence.

## Why this is now the correct abstraction

The current repository already has most of the required organs:

- `ai_project_orchestrator.py` — project/revision-pinned proposal-only AI orchestration;
- `ai_project_tool_executor.py` — accepted, deterministic software-side execution for a bounded action set;
- `ai_project_repair.py` — one failure-fed bounded repair turn;
- `guided_engineering_planner.py` and `compose_dispatch.py` — deterministic engineering/compose operators;
- `/v1/devices/*` — known-library device draft, planning, engineering review, enclosure, firmware/application, modeled execution, observations;
- `device_reclaim.py` — advisory matching from reported reclaimed markings into the existing module library;
- `backend_mcp_server.py` / `mcp_backend_gateway.py` — stateful canonical API projection to external agents;
- existing project/evidence/assurance/physical-validation machinery — revision and authority boundaries.

The missing layer is primarily **mission state + cross-surface orchestration**.

The current system has two partially separate nervous systems:

```text
project agent
  -> proposal
  -> human acceptance
  -> deterministic project preview tools

external/device agent
  -> schema/examples/draft
  -> plan/repair
  -> engineering/case/application
  -> modeled execution
  -> observations
```

The Fabrication Mission Runtime joins them without making the model authoritative.

## Mission object

A future mission should persist at least:

```text
mission_id
project_id
revision_id
goal
constraints
budget
inventory
known_donors
unknown_artifacts
candidate_architectures
selected_architecture
current_phase
open_findings
assumptions
evidence_refs
generated_artifacts
operator_jobs
blockers
iteration_budget
terminal_state
```

Mission state belongs server-side. The model may propose changes to it; the model is not the source of truth for it.

## Intake modes

### 1. Known-library clean-sheet

The current device lane already handles the small version of this:

`goal -> known controller/parts -> draft -> plan -> engineering -> case/application -> modeled run`

This remains useful, but it is only one intake mode.

### 2. Known donor / reclaim

A donor is treated as an asset with retained capabilities, not merely a bag of components.

Example decomposition:

```text
retired POS terminal
  display/touch
  compute
  power architecture
  enclosure
  storage
  Ethernet/USB
  serial I/O
  mounting/cooling
```

HS should be able to compare preserving those capabilities against replacing them.

The existing `device_reclaim.py` is intentionally narrower: name matches only, no identification or compatibility claim. The mission runtime must preserve that honesty while allowing stronger evidence from manuals, measured observations, teardown records, or external reverse-engineering operators to enrich a donor model.

### 3. Unknown / partially understood artifact

This is the important new path.

An unknown artifact should enter as an evidence problem:

```text
artifact
  -> identify / inspect / decompose
  -> evidence records
  -> candidate capability model
  -> uncertainty / missing observations
  -> source-route comparison
  -> transformation candidate
```

Reverse engineering is therefore **an intake operator**, not a replacement for HS engineering truth.

A reverse-engineering tool may establish evidence such as:

- firmware layout;
- binary/runtime behavior;
- protocol or interface observations;
- signal-recording interpretation;
- package contents;
- version differences;
- candidate internal components or functions.

Those observations remain evidence with provenance and limitations. They do not silently become `physical_correctness`, compatibility, identity, or release authority.

## Reverse-engineering operator contract

The external operator pattern should mirror the existing HS operator-job / operator-receipt philosophy.

Conceptually:

```text
HS mission
  -> reverse-engineering job
     target identity
     allowed evidence classes
     requested questions
     target digest / revision
     execution boundary
  -> external operator
  -> evidence receipt
     tool identity/version
     target digest
     observations
     confidence/limitations
     raw/retained evidence refs
  -> HS validation
  -> donor/capability model update
```

The operator can answer questions. It cannot grant:

- exact hardware identity without supporting evidence;
- electrical compatibility;
- safe power-on;
- safe flashing;
- fabrication authority;
- release authority.

For software/firmware reverse engineering, **REA (morluto/rea)** is a particularly relevant current reference because it exposes agent-first CLI/MCP workflows and explicit Evidence records across native/managed applications, JavaScript/Electron, browser/runtime evidence, firmware, packet/signal recordings, and related shipped-artifact analysis.

Reference: <https://github.com/morluto/rea>

This is a pattern to integrate or emulate at the operator boundary, not code HS should copy wholesale.

## Candidate architectures, not one-shot generation

A mission should normally produce a small bounded set of candidates, for example:

```text
A — clean-sheet / mostly new components
B — reclaim-heavy donor transformation
C — hybrid donor + new electronics
```

Run each candidate through the same evidence and deterministic gates where applicable.

Comparison should include at least:

- estimated cost and sourcing risk;
- new material count;
- retained/reused capabilities;
- unresolved assumptions;
- planner findings;
- engineering-review severity;
- modeled/simulation status;
- fabrication complexity;
- physical measurements still required;
- evidence confidence/provenance.

The model can recommend a candidate. HS must preserve the comparison and why the selected candidate is preferred.

## Agent / deterministic / human authority split

### Agent owns workflow reasoning

Examples:

- interpret the mission;
- propose architectures;
- decide which bounded operator to call next;
- choose which finding to repair first;
- synthesize a revised candidate;
- explain tradeoffs.

### Deterministic HS machinery owns engineering gates

Examples:

- schema validity;
- pin/controller legality;
- deterministic plan checks;
- ERC/DRC when applicable;
- compilation;
- modeled scenario verdicts;
- artifact identity/hash binding;
- evidence and revision contracts;
- authority invariants.

### Human owns physical authority

Examples:

- purchase;
- disassembly;
- destructive probing;
- fabrication order;
- flashing;
- power-on;
- energized measurements;
- release/sale.

The desired autonomy boundary is therefore broad software autonomy with a hard stop before physical authority.

## Bounded mission loop

Do not implement this as an unconstrained `while agent(): ...` loop.

A mission needs explicit budgets and terminal states.

Suggested limits:

- maximum architecture candidates;
- maximum repair iterations per candidate;
- maximum external-operator jobs;
- maximum model/tool budget;
- stop on repeated equivalent finding;
- stop when required evidence is unavailable;
- stop when the next step requires physical intervention.

Suggested terminal states:

```text
READY_FOR_HUMAN_BUILD
BLOCKED_NEEDS_PART_DATA
BLOCKED_NEEDS_REVERSE_ENGINEERING
BLOCKED_NEEDS_PHYSICAL_MEASUREMENT
BLOCKED_NEEDS_PROCUREMENT_EVIDENCE
BLOCKED_UNSAFE
NO_FEASIBLE_ARCHITECTURE
BUDGET_EXHAUSTED
```

## Immediate integration sequence

This is the bounded next tranche. It is intentionally smaller than "build a new autonomous hardware platform".

### P0 — finish the current agent projection

The canonical `/v1/devices/application/run` operation exists and `AGENT_DEVICE_DESIGN.md` describes it, but the `device_design` task projection in `mcp_backend_gateway.py` currently omits that route.

Fix the manifest and pin it in `tests/test_device_agent_surface.py`.

This closes a real discovery gap without adding a capability.

### P1 — mission state over existing project state

Add a persistent mission record keyed to project/revision identity. Do not create a second artifact/evidence database.

The first runtime may support only:

- mission goal/constraints;
- inventory/donor inputs;
- up to three candidate architectures;
- current candidate + findings;
- bounded iteration counter;
- terminal state.

### P2 — admit current device operations to the accepted tool executor

The existing AI tool executor currently runs only `run_guided_plan` and `run_compose` previews.

Add bounded accepted actions for the existing safe software-side device operations rather than letting the model call arbitrary HTTP:

```text
device_draft
device_plan
device_engineering
device_case
device_application
device_application_run
device_reclaim_match
```

Each action should dispatch through canonical handlers and retain current authority semantics.

### P3 — connect machine repair suggestions to failure-fed repair

Current device-plan findings already carry machine-usable suggestions. Current project repair already has a bounded successor-session mechanism.

Bridge them so a failed/blocked device plan can become a revisioned repair attempt with a bounded retry budget.

Do not let repair silently mutate the canonical design.

### P4 — donor capability model

Move beyond a flat reclaim marking list to a donor model that can represent retained subsystems and their evidence state.

Do not infer subsystem identity from text alone.

### P5 — external reverse-engineering operator

Only after mission state and donor evidence are stable, add a provider-neutral reverse-engineering operator job/receipt contract.

An REA adapter can be the first software/firmware operator if useful, but HS should depend on its own evidence contract rather than one provider's internal schema.

## Competitive context — 2026-10-16

The category is moving quickly. The correct response is selective orchestration, not rebuilding every specialist.

### Flux

Flux now publicly positions an end-to-end, self-correcting hardware agent spanning planning, part research, schematics, layout and sourcing, exposes projects through MCP to external agents, and has expanded beyond PCBs into manufacturable enclosure generation.

References:

- <https://email.flux.ai/p/blog/spring-2026-updates-faster-ai-better-layouts-smarter-sourcing>
- <https://docs.flux.ai/reference/flux-mcp-server>
- <https://email.flux.ai/p/blog/hardware-enclosure-design>

**HS consequence:** clean-sheet conversational hardware design is not a sufficient moat. HS should differentiate on transformation of existing/unknown hardware, explicit evidence state, revision consequences, donor economics, and physical-authority separation. Flux may eventually be an operator beneath HS for clean-sheet design tasks.

### Circuit Mind

Circuit Mind focuses on requirements/architecture to candidate schematics and BoMs, component digital twins, large design-space search, and optimization across cost/size/power/availability. It publishes examples of comparing multiple architectures before selecting one.

References:

- <https://www.circuitmind.io/index.html>
- <https://www.circuitmind.io/resource-center/evidence-that-ai-is-breaking-the-engineering-triangle-in-electronics-design>

**HS consequence:** candidate-architecture generation and comparison is table stakes. HS should preserve a cross-route comparison that includes clean-sheet, reuse, donor retrofit and hybrid transformation rather than competing only on component selection.

### Quilter

Quilter's focus is physics-first autonomous PCB layout with parallel candidate exploration and continuous verification.

Reference: <https://www.quilter.ai/about>

**HS consequence:** treat high-end layout automation as a specialist operator. Do not spend HS scope trying to become a better autonomous router than a company centered on that problem.

### Cadence AuraStack

Cadence introduced AuraStack as an agentic orchestration layer across system planning, PCB/advanced packaging implementation and multiphysics analysis.

Reference: <https://www.cadence.com/en_US/home/company/newsroom/press-releases/pr/2026/cadence-introduces-aurastack-ai-super-agent-the-worlds-first.html>

**HS consequence:** "multi-agent EDA orchestration" by itself is also not a unique category. HS should own the higher-level transformation/evidence/authority problem and call professional EDA where appropriate.

### Open KiCad agent stacks

Projects such as `nevenfo/kicad-agentic-mcp` explicitly use the pattern:

`LLM intent -> typed plan -> deterministic transactional execution -> KiCad ERC/DRC/readback verdict -> server-side state/evidence/rollback`

Reference: <https://github.com/nevenfo/kicad-agentic-mcp>

**HS consequence:** this independently validates the architecture HS is already converging toward: model for ambiguous reasoning, deterministic systems for exact engineering truth.

### REA — Reverse Engineer Anything

REA exposes agent-first reverse-engineering workflows across shipped software/firmware/runtime artifacts with retained evidence and limitations.

Reference: <https://github.com/morluto/rea>

**HS consequence:** unknown artifacts no longer need to be modeled as permanently manual inputs. Reverse engineering can become a bounded evidence-producing operator that feeds donor/capability discovery while HS retains the authority and integration layer.

## Product Factory implication

PF-001/002/003 become useful mission benchmarks rather than separate product directions.

A strong benchmark is PF-003 / FieldDeck:

> Given a Taiwan-available industrial tablet donor, a spending ceiling, and a requested portable field-service capability, produce the best bounded transformation plan and reach either `READY_FOR_HUMAN_BUILD` or a precise evidence blocker.

A credible run should:

1. represent the donor as retained capabilities;
2. identify unknowns requiring manual or reverse-engineering evidence;
3. generate at least clean-sheet/reclaim-heavy/hybrid candidates where meaningful;
4. compare economics and engineering risk;
5. generate the custom electronics/software/mechanical artifacts HS can currently generate;
6. run deterministic/model gates;
7. package remaining physical measurements and authority stops.

That demonstration would show HS doing something materially broader than a PCB agent.

## Explicit non-goals for this tranche

Do **not** respond to the competitive scan by adding:

- another MCU merely for coverage;
- another sensor merely for coverage;
- a new PCB router;
- a new decompiler;
- a new general web-research agent;
- automatic purchasing;
- automatic destructive reverse engineering;
- automatic flashing/power-on;
- claims that modeled or reverse-engineered behavior establishes physical correctness.

Use external specialists where they are stronger. HS value is the mission/evidence/transformation control plane.

## Success criterion

The Fabrication Mission Runtime v0 is complete when one bounded mission can start from:

```text
goal + constraints + finite inventory/donor description
```

and autonomously use existing safe software-side HS operations to reach either:

```text
READY_FOR_HUMAN_BUILD
```

or one honest bounded blocker with a complete account of the missing evidence.

Anything beyond that is a later tranche.