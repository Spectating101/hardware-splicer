# Hardware Splicer — Product Convergence RC

## One sentence

**Hardware Splicer turns available physical resources into defensible machine build candidates.**

It starts from what physically exists — owned parts, salvaged hardware, procurable components and designed parts — then helps move from inventory to a goal, candidate architectures, concrete evidence gaps, engineering verification and a build package.

## The product loop

> **Inventory → Goal → Candidates → Resolve → Verify → Build**

This is the canonical product grammar. Advanced CAD/BREP, evidence and authority tooling are implementation layers underneath this loop, not separate products the user must understand first.

### Inventory

- photo-derived donor observations;
- owned / salvaged / procurable / designed resources;
- registered STEP and project sources;
- explicit confidence, provenance and unknowns;
- provisional observations remain provisional.

### Goal

A mission is a machine-level objective plus constraints such as:

- maximum additional spend;
- maximum reuse;
- minimum integration risk;
- required capabilities;
- size / portability / service constraints.

### Candidates

HS compares architectures rather than returning one unqualified LLM answer. Candidate state can expose:

- capability coverage;
- reused resources;
- missing capabilities;
- procurement cost;
- blockers / evidence gates;
- scenario risk.

### Resolve

Generic blockers become operator actions:

- identify a donor item or revision;
- photograph labels / connectors;
- upload a manual / CAD source;
- measure a dimension;
- capture voltage / resistance / current with provenance;
- resolve exact spatial geometry.

### Verify

Current sovereign engineering substrate includes:

- declared rigid placement;
- live 3D move / rotate tools with deterministic precision nudges;
- STEP identity + content hashes;
- exact CadQuery 2.8 / OCCT render meshes;
- exact surface anchors;
- anchor mating geometry;
- sampled mating / insertion paths;
- adaptive transition refinement;
- exact pair distance / intersection checks;
- operator claims separated from calibrated bench measurements;
- evidence / authority boundaries.

### Build

Build output should converge toward:

- selected architecture;
- resource BOM grouped into reuse / buy / fabricate / substitute;
- generated or imported CAD;
- adapter files;
- wiring / interface plan;
- assembly sequence;
- required measurements;
- unresolved risks;
- evidence provenance;
- cost and procurement state;
- test procedure;
- explicit human verification remaining.

## Sovereign adapter synthesis v0

The current bounded synthesis family is `bridge_block_v0`.

Two distinct, common-frame, approximately opposed planar exact BREP anchors can define a generated bridge candidate. The worker:

1. validates source hash + declared parent pose;
2. validates exact anchor dependency identity;
3. generates a real CadQuery solid;
4. exports real STEP;
5. hashes the generated STEP;
6. tessellates it for workbench preview;
7. computes exact OCCT minimum distance to both parents;
8. computes exact intersection volume with both parents;
9. returns pass / rejection / unknown state.

A geometric pass **does not** establish material, mounting, retention, tolerance, strength, manufacturability, electrical compatibility, fabrication or release authority.

## Primary canonical demo: cyberdeck

### Input pile

- donor display;
- SBC / mini-PC / x86 board;
- keyboard;
- battery / power bank;
- hub / storage;
- cooling fan;
- enclosure or donor chassis hardware;
- miscellaneous fasteners / brackets.

### Mission

> Build a portable Linux cyberdeck using as much existing hardware as possible, with a bounded additional budget and externally accessible power / storage / I/O.

### What the demo must prove

1. donor / parts-bin resources enter Inventory;
2. HS proposes multiple architectures;
3. one candidate wins on the selected objective;
4. HS identifies a real unresolved mechanical interface;
5. the operator resolves exact surfaces / measurements;
6. HS synthesizes the missing adapter;
7. the adapter appears in the 3D assembly as a generated geometric candidate;
8. parent contact / penetration checks are visible;
9. generated STEP can be exported;
10. unresolved material / retention / fabrication claims remain visible rather than being hidden.

### Why cyberdeck first

It exercises resource composition, power, display, compute, thermal and mechanical integration without making motion control or high structural loads dominate the demonstration.

## Secondary demo: inspection rover

Use salvaged motors + camera + controller / SBC + chassis resources under a spending limit. This demonstrates a broader mechatronics case and makes resource substitution / rejection more visible.

## Competitive positioning

### What HS is not

- not a replacement for all Fusion / Onshape authoring;
- not a complete PCB autorouter;
- not a new FEA / CFD stack;
- not a photorealistic rendering product;
- not a chatbot that declares hardware safe because a model said so.

### What HS owns

- resource understanding;
- reuse-first architecture synthesis;
- system-level candidate comparison;
- spatial / interface reasoning;
- evidence and uncertainty;
- compatibility / verification;
- simple missing-hardware synthesis;
- orchestration to specialist tools when the problem exceeds sovereign scope.

### Judge answer: “Why not Fusion?”

> Fusion is excellent at designing components and assemblies once you know what you are designing. Hardware Splicer starts earlier: given heterogeneous physical resources — including salvaged, undocumented and cross-vendor hardware — it asks what useful system can be built, what information is missing, what must be bought or fabricated, and which engineering claims are actually supported. Fusion can be one of the specialist tools HS hands work to.

## Evidence ladder

Do not collapse these classes:

1. AI / photo inference;
2. operator claim / observation;
3. document / source evidence;
4. exact computational geometry;
5. calibrated instrument measurement;
6. controlled physical result;
7. explicit human release authority.

The product is stronger when it visibly says **UNKNOWN** than when it manufactures false precision.

## Claims allowed in public / competition material

- reuse-first physical systems synthesis is the product thesis;
- mission UI exists and drives canonical workbench state;
- donor-photo observations can enter resource planning as provisional salvage resources;
- Resolve exposes concrete evidence actions;
- operator claims and instrument-backed measurement sessions are separated;
- exact BREP / OCCT geometry paths exist for bounded checks;
- direct 3D pose editing commits through the canonical placement path;
- geometry interrogation exposes source / pose / exact-mesh / anchor state;
- bounded exact-anchor adapter synthesis exports STEP and checks both parent solids.

## Claims that remain blocked until evidence exists

- metrology-grade dimensions from arbitrary STEP alone;
- arbitrary connector recognition / pinout authority;
- universal electrical compatibility;
- retention / mounting closure for generated adapters;
- structural / fatigue / thermal validation;
- continuous whole-machine swept collision closure;
- manufacturing / fabrication authorization;
- power-on / motion / production release;
- measured market adoption / time savings / waste diversion until external cases exist.

## Three-minute product demo spine

### 0:00–0:25 — Problem

Show the physical pile, not a CAD screenshot.

> “The world has excellent tools for designing new hardware. The harder problem is: what can I build from the hardware that already physically exists?”

### 0:25–0:55 — Inventory + goal

Photograph / identify donor resources, preserve provisional status, state the cyberdeck mission and budget.

### 0:55–1:25 — Candidate decision

Show multiple candidate strategies and why the selected one wins on reuse / cost / risk.

### 1:25–1:55 — Resolve

Open one real blocker. Show the concrete measurement / source / geometry task rather than an abstract warning.

### 1:55–2:30 — Engineering firepower

Open exact geometry, select the two relevant surfaces, synthesize the missing adapter and show exact parent checks.

### 2:30–2:50 — Build output

Show generated STEP / package / remaining evidence.

### 2:50–3:00 — Close

> “Hardware Splicer turns what you already have into what you can actually build — without hiding what still needs proof.”

## Product release gate

A deployable Gauntlet RC should not be called ready until all of these are satisfied on the exact packaged head:

- frontend typecheck;
- production frontend build;
- Machine Workbench Chromium suite;
- Exact BREP Kernel including adapter tests;
- Stored Source Parser / source durability paths;
- core API / package export paths relevant to the demo;
- root product page reachable;
- `/workbench/mission` reachable;
- `/workbench` reachable;
- no known product-breaking runtime error on the deployed preview;
- exact commit SHA recorded in the entry package.

## Immediate physical evidence backlog

Software closure is not the finish line. The next external-proof backlog is:

1. build the canonical cyberdeck;
2. record actual donor identities and measurements;
3. fabricate at least one HS-generated adapter;
4. record fit success / failure;
5. run the same workflow on the inspection rover;
6. persist successful / failed compatibility outcomes for reuse in future projects.

That transition — from model predictions to repeated observed build outcomes — is what can turn the current wedge into a defensible compatibility / evidence graph over time.
