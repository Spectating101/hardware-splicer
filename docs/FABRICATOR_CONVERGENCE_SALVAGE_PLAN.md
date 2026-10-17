# Fabricator convergence and salvage-agent execution plan

Status: implementation plan, not a claim that the converged fabricator already exists.

Current anchors (2026-10-17):

- Fabricator / lab stack head: `f2d06767f71520a01f07c57d44f988f8f94e9494` (`agent/fabricator-lab-orchestration-v0`, PR #131).
- Donor / RE / native-donor firmware head: `450ad27ee35c34ae30069715dc9f40cfab90939a` (`agent/mission-donor-firmware`).
- Common hardened mission-runtime ancestor: `fa83196e8ffe339f6e26d823dbf328972868440d`.

The two lines now contain complementary halves of the intended product. The next phase is convergence and end-to-end execution, not broad feature accumulation.

## North-star product test

The real product test is not test count or whether a known ESP32/BME280 example can compile. The north-star is a **salvage / dumpster-dive fabrication mission**:

> Given a pile of discarded or partially understood hardware, a goal or a budget, and bounded access to research, measurement, design and fabrication tools, an agent should discover reusable capabilities, preserve uncertainty, compare clean-sheet/reclaim/hybrid architectures, fabricate only what is missing, validate the resulting object, and revise when reality disagrees.

A person may initially provide the hands: move a camera, remove screws, probe requested points, connect fixtures, perform explicitly approved physical actions. The agent is the diver and investigator. HS is the mission state, evidence ledger, capability/resource graph, tool workbench, authority boundary, scheduler and revision system.

Success is therefore measured by useful capabilities recovered, unsupported claims refused, purchased-parts burden, destructive mistakes, human interventions, time-to-working-artifact and reproducibility — not by pytest count alone.

## Product responsibility split

### Agent

The agent may:

- inspect images, markings, board descriptions and retained observations;
- research likely identities and datasheets;
- propose hypotheses and the next measurement/teardown step;
- request bounded observations and human measurements;
- compare candidate architectures;
- ask specialist tools to generate/check artifacts;
- diagnose failures and propose revisions;
- schedule work through server-owned capabilities.

The agent does not get to turn hypotheses into persisted physical facts, redefine the accepted mission, create human authority, invent supplier quotes, or submit raw machine commands.

### Hardware Splicer

HS owns:

- immutable mission intent and structured requirements;
- donor/resource identity and evidence grades;
- capability/resource graph;
- artifact identity and cross-tool provenance;
- deterministic checks and frozen validation criteria;
- architecture-candidate state;
- physical execution plans and human approval binding;
- observations/evidence and terminal truth;
- resource scheduling and leases;
- revision lineage.

### Human / physical operator

Initially the human supplies hands and high-risk authority:

- physical teardown;
- positioning/camera capture when automation is unavailable;
- requested measurements;
- fixture changes and assembly;
- approval of exact physical actuation plans.

Robots/workcells may later replace some human manipulation without changing the mission/evidence architecture.

## What already exists on the two live lines

### Donor / RE line

The donor line now provides the foundations required for salvage:

- P4 donor intake and project-scoped contract resolution;
- frozen donor readings before mission acceptance;
- evidence grades and weakest-fact capability grading;
- P5 reverse-engineering findings as non-promoting re-observations;
- human donor measurements that remain separate from frozen contracts;
- native donor placement/wiring/geometry for the first bounded donor family;
- case/enclosure participation and assembly proposals;
- passive switch/button donor firmware proposals bound to frozen contacts and planned GPIOs;
- modeled donor-input runtime scenarios and deterministic mission packaging.

### Fabricator / lab line

The fabricator line now provides:

- generic physical operator/action model and immutable execution plans;
- exact-plan human physical approval and one-shot grants;
- printers, slicers, programmer/debug adapters and read-first instruments;
- raw physical observations, camera/serial intake and explicit evidence promotion;
- KiCad, ngspice, OpenSCAD, FreeCAD and manufacturing bridges;
- non-executable engineering-artifact storage and digital-thread provenance;
- MTConnect / OPC UA / ROS2 read-only observation paths;
- CNC/laser and motion-plan dry-run analyzers;
- procurement quote snapshots and clean/reclaim/hybrid Pareto comparison;
- frozen requirement-linked validation;
- capability-driven lab scheduling and resource leases.

These are complementary systems. The next work should make them one runtime.

# Convergence sequence

## C0 — Freeze interfaces and inventory overlap

Before semantic merging, record the exact current heads and identify every overlapping concept:

- mission event/state and candidate revision;
- donor/resource identity;
- physical evidence;
- engineering artifact vs executable physical artifact;
- mission delivery/package;
- agent/MCP surface;
- revision proposal / staged review;
- capability registries.

Do not introduce a second donor store, evidence ledger, project-revision system, mission runtime or physical-authority system merely because one exists on each side.

Acceptance:

- one written mapping of source-of-truth ownership for every overlapping concept;
- duplicates marked for reuse, adaptation or deletion before implementation proceeds.

## C1 — Create the convergence branch

Create `agent/fabricator-convergence-v0` from the fabricator head and merge/replay the donor lineage from `450ad27e`.

Resolve conflicts in favor of existing canonical ownership:

- mission truth remains in the mission store/event model;
- project revisions remain in the existing reviewed revision workflow;
- donor contracts/readings remain evidence inputs, not an alternate project truth;
- physical execution authority remains the #125 plan/grant path;
- raw observations/evidence remain the feedback-plane path;
- engineering artifacts and executable artifacts remain separate classes.

No new features in the first convergence commit beyond compatibility shims and contract normalization.

Acceptance:

- donor and fabricator focused suites can execute on one branch;
- legacy known-part examples preserve their existing canonical hashes where expected;
- no authority flag becomes more permissive merely because stacks were merged.

## C2 — One resource/capability graph

Connect P4/P5 donor capability truth to the fabricator capability/tradeoff layer.

Introduce a vendor-neutral resource record that can represent:

- known catalog components;
- donor electrical capabilities;
- donor mechanical capabilities;
- material/stock resources;
- tools/machines;
- human-provided capabilities.

Minimum fields:

- stable resource identity;
- resource kind;
- capability IDs;
- geometry/interface constraints where known;
- evidence references and weakest supporting grade;
- uncertainty / unresolved facts;
- destructive-recovery cost or restriction;
- availability / quantity;
- optional procurement replacement.

Do not collapse evidence grade into a magic scalar confidence score.

Acceptance:

- a frozen donor capability can be consumed by architecture search without being copied into a new truth store;
- missing/uncertain donor facts remain visible blockers or costs;
- clean-sheet, reclaim-heavy and hybrid candidates can reference the same resource graph.

## C3 — Salvage-agent mission loop

Add a top-level bounded mission projection for salvage work. Working name: `salvage_fabrication`.

The agent workflow should support:

1. inspect current resources and retained observations;
2. propose donor hypotheses/findings;
3. request next observation, teardown or measurement;
4. update candidate capability use from HS-grounded donor readings;
5. generate multiple architecture candidates;
6. compare clean/reclaim/hybrid options;
7. select/stage a reviewed candidate;
8. generate missing electrical/mechanical/firmware artifacts;
9. schedule required lab capabilities;
10. request exact physical approvals where needed;
11. ingest observations and frozen validation results;
12. propose a revision when evidence fails.

Agent-visible operations should use stable IDs and bounded schemas. No raw filesystem paths, arbitrary shell, raw SCPI/G-code, endpoint credentials, contract promotion or human approval operations.

Acceptance:

- a single agent can advance one salvage mission across multiple turns without reconstructing project state from chat;
- every hypothesis can be traced to evidence or remains explicitly unsupported;
- the agent can stop at an evidence need instead of forcing a buildable conclusion.

## C4 — Automated visual/object intake

Upgrade the old person-described donor-board path into an agent-assisted intake flow:

camera/image observation
→ model-derived draft extraction
→ candidate board outline / packages / markings / connectors / screw locations
→ explicit uncertainty
→ human confirm/correct where required
→ donor capture / P5 findings

Vision output remains `model_inference`; it must not silently become measured geometry, identity or physical validation.

First supported inputs:

- PCB top/bottom photographs;
- enclosure/subassembly photographs;
- connector/marking closeups;
- ruler/reference-assisted geometry images.

Acceptance:

- an agent can prefill a donor capture from retained images;
- each extracted fact records source image and whether it is inferred, human-confirmed or measured;
- marking text is never equivalent to part identity without supporting evidence.

## C5 — Expand donor capability families by salvage value

Do not build a huge component catalog. Build reusable capability families commonly recovered from e-waste.

Priority order:

1. passive controls: switches, buttons, encoders;
2. indicators: LEDs, simple lamps, buzzers/speakers;
3. fans and simple DC motors;
4. steppers and end-stops from printers/scanners;
5. regulated power modules and known external adapters;
6. USB peripherals / UVC cameras / HID devices;
7. keypads and simple displays;
8. known sensor modules;
9. rails, belts, pulleys, gears, bearings and reusable enclosures;
10. more complex controller/subassembly interfaces only after their evidence contracts are clear.

Each family must define:

- minimum evidence needed to claim the capability;
- optional evidence that improves usability;
- measurements/tests the agent may request;
- planner interface contract;
- firmware/driver/mechanical adapter, if any;
- known hazards and refusal conditions;
- what remains unknown after successful qualification.

Battery packs, mains circuits and high-energy power electronics should remain quarantined/inspection-required resources until separately designed safety policy exists.

Acceptance:

- new families plug into the same resource graph and architecture search;
- no family gets a bespoke parallel mission flow;
- unsupported mystery hardware can remain partially useful rather than requiring full identification.

## C6 — Mission artifacts flow directly into the fabrication plane

Remove manual file shuffling between mission delivery and physical execution.

Expected paths:

- enclosure source → render → retained geometry → slicer receipt → exact G-code physical artifact;
- firmware proposal → compiled firmware artifact → registered programmer target → exact flash plan;
- KiCad project → ERC/DRC → Gerber/drill/BOM/positions → vendor-neutral fab request;
- validation procedure → measurement/observation recipes → retained evidence.

The mission/revision ID and source artifact hashes must be preserved across every transform.

Acceptance:

- changing a revision invalidates stale downstream executable artifacts;
- physical approval always binds the exact artifact and target, never just a mission name;
- successful tool execution does not establish physical correctness.

## C7 — Close evidence → revision → regeneration

Unify the fabricator physical-failure proposal with the existing reviewed project-revision flow.

Required loop:

physical observation
→ promoted evidence
→ frozen validation failure
→ grounded revision proposal
→ human-reviewed project revision
→ regenerate only affected downstream artifacts
→ new execution plan / new approval
→ retest

No automatic silent mutation of an accepted revision.

Acceptance:

- a failed physical criterion can result in a second candidate revision with explicit provenance;
- old physical evidence remains attached to the old revision;
- stale approvals/artifacts cannot be replayed against the new revision.

## C8 — Lab orchestration becomes mission-driven

Connect the #131 capability scheduler to mission artifact dependencies.

A mission asks for capabilities, not machine names, for example:

- additive fabrication with required material/build envelope;
- firmware programming for target family;
- voltage/current measurement;
- camera observation;
- PCB assembly simulation or later live PnP.

The scheduler should build a dependency DAG from artifact prerequisites and validation steps, allocate registered resources, and retain plan-bound leases. Resource reservation still never equals actuation authority.

Acceptance:

- independent tasks run in parallel where valid;
- shared resources serialize;
- a blocked upstream task prevents misleading downstream execution;
- physical tasks separately pass through exact-plan approval.

# Dumpster-Dive Mission benchmark

This becomes the primary HS product benchmark after convergence.

## Input

A deliberately messy fixed resource box, e.g.:

- retired router or modem PCB;
- discarded printer/scanner mechanism;
- old USB webcam;
- buttons/switches/LEDs;
- one or more unknown small PCBs;
- cables/connectors;
- mechanical enclosure/stock;
- small budget for missing components.

The benchmark may begin with photographs and rough human inventory only.

## Agent objective

Either:

- satisfy a stated useful goal; or
- propose 3–5 useful build goals achievable from the resources, then proceed after human selection.

## Required behaviors

The agent must demonstrate:

- inventory and visual inspection;
- uncertainty-preserving hypotheses;
- targeted research;
- bounded teardown/measurement requests;
- P4/P5 capability accumulation;
- rejection/quarantine of unsafe or unsupported resources;
- clean-sheet/reclaim/hybrid architecture candidates;
- explicit tradeoffs and donor dependencies;
- generation of missing CAD/EDA/firmware;
- reproducible artifact graph;
- physical/lab scheduling;
- evidence-based validation;
- at least one grounded revision cycle in the benchmark harness, whether simulated or later physical.

## Scoring

Primary metrics:

- useful donor capabilities recovered;
- fraction of final architecture satisfied by reclaimed resources;
- purchased-parts cost and number of newly purchased components;
- unresolved facts correctly left unresolved;
- false persisted capability claims (target: zero);
- destructive actions later shown unnecessary;
- human interventions / measurements requested;
- number of revision cycles;
- time/steps to a reproducible build package;
- validation coverage against frozen requirements.

Software test counts are supporting quality metrics only.

## Progressive benchmark levels

### S0 — synthetic salvage box

All observations are retained fixtures. The whole agent loop must work through real HS APIs and stores.

Purpose: prove orchestration, evidence, architecture search, artifact generation, validation and revision without hardware dependency.

### S1 — photographed real e-waste, human hands

Real donor photos, markings and requested measurements. The human performs teardown and bench actions. HS/agent performs reasoning, planning and artifact generation.

Purpose: test whether HS can actually investigate messy objects rather than pre-labeled fixtures.

### S2 — real salvage build

At least two reclaimed capabilities must appear in the finished device, with purchased missing pieces and fabricated custom parts.

Purpose: prove the core product proposition.

### S3 — multi-machine / semi-automated salvage cell

Printers/programmers/instruments/workcell operators execute bounded tasks under the same mission. Robots may replace selected human manipulation.

Purpose: advance toward the general fabricator without changing the trust model.

# Immediate implementation order

The next code work should follow this order:

1. create `agent/fabricator-convergence-v0` and reconcile the two heads;
2. write the canonical ownership/duplicate map while resolving conflicts;
3. expose donor capabilities through one resource graph consumed by tradeoff search;
4. add `salvage_fabrication` bounded agent workflow;
5. wire mission-generated artifacts to the digital/physical thread;
6. wire failed frozen validation into reviewed revision/regeneration;
7. build S0 as an executable end-to-end benchmark;
8. add visual donor prefill;
9. expand donor families based on S0/S1 failures, not connector-count goals;
10. prepare S1/S2 real-e-waste trials when physical resources are available.

# Explicit do-not-do list

Until the converged runtime and S0 benchmark work:

- do not add broad live CNC/laser/robot actuation merely for coverage;
- do not create another mission/evidence/revision store;
- do not build a giant donor catalog;
- do not let vision inference become physical truth automatically;
- do not let donor marking text become identity automatically;
- do not let successful simulation/tool execution become physical correctness;
- do not let lab reservation become physical authority;
- do not collapse clean/reclaim/hybrid tradeoffs into an unexplained scalar score;
- do not optimize for test-count headlines instead of salvage mission behavior.

# Exit criterion for this phase

This phase is complete when one converged HS branch can run the S0 salvage mission end to end and produce:

- retained donor observations/findings;
- evidence-graded reusable capabilities;
- clean/reclaim/hybrid architecture candidates;
- a reviewed selected revision;
- generated electrical/mechanical/firmware artifacts;
- a reproducible digital thread and handoff package;
- a scheduled lab plan;
- bounded physical execution plans where applicable;
- frozen validation;
- a grounded revision and regenerated artifact set after an injected failure;
- zero false persisted physical/capability truth in the benchmark trace.

Only after that should donor breadth and physical automation become the main expansion axes.
