# Hardware Splicer

[![Splice Agent v1](https://github.com/Spectating101/hardware-splicer/actions/workflows/hardware-splicer.yml/badge.svg)](https://github.com/Spectating101/hardware-splicer/actions/workflows/hardware-splicer.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Reuse-first physical systems synthesis under bounded engineering authority.**

> **What can I build with what I already have?**

Hardware Splicer starts from physical resources — owned parts, salvaged hardware, procurable components and designed parts — and helps turn them into defensible machine build candidates.

The canonical product loop is:

> **Inventory → Goal → Candidates → Resolve → Verify → Build**

Underneath that product flow, the governing engineering invariant remains:

> **AI proposes → deterministic systems constrain → bench evidence decides → human authorizes.**

Hardware Splicer is not presented as an LLM replacing a hardware engineer, and it is not attempting to clone every Fusion, Onshape, KiCad or Altium feature. It owns the subset of systems engineering, spatial reasoning, evidence and simple missing-hardware synthesis required to answer a different starting question: given the hardware that physically exists, what useful system can be built, what is missing, and what can actually be proven?

## Evaluators / competitions / product reviewers

**Start here:** [`docs/gauntlet/HARDWARE_SPLICER_PRODUCT_RC.md`](docs/gauntlet/HARDWARE_SPLICER_PRODUCT_RC.md)

For InnoServe 2026 packaging:

- [`docs/gauntlet/INNOSERVE_2026_ENTRY_RC.md`](docs/gauntlet/INNOSERVE_2026_ENTRY_RC.md)

For the older controlled evidence / research package:

- [`docs/external_assessment/`](docs/external_assessment/) remains available as supporting audit history and evidence discipline;
- it is **not** the canonical product positioning for this reuse-first RC.

## Current product state

The current convergence RC packages the previously separate engineering capabilities into one user journey.

### 1. Inventory

- donor-photo observations can enter planning as provisional salvage resources;
- owned / salvaged / procurable / designed resources share one resource strategy model;
- registered project sources preserve content hashes and occurrence bindings;
- uncertain identity remains uncertain rather than being silently promoted.

### 2. Goal

The user can begin with a machine objective and constraints such as:

- maximize reuse;
- cap additional spending;
- reduce integration risk;
- require specific capabilities;
- preserve portability / service constraints.

### 3. Candidates

Hardware Splicer compares multiple resource-aware architectures instead of returning one unqualified design answer. Candidate state can expose:

- capability coverage;
- selected / rejected resources;
- procurement gaps;
- additional cost;
- unresolved evidence gates;
- strategy trade-offs.

### 4. Resolve

Generic blockers become concrete operator actions such as:

- identify a donor revision;
- photograph a label / connector;
- upload a manual / CAD source;
- measure a dimension;
- record power / resistance / current evidence;
- resolve exact spatial geometry.

### 5. Verify

Current sovereign engineering substrate includes:

- declared rigid assembly placement;
- live 3D Select / Move / Rotate controls with deterministic precision nudges;
- bounded STEP parsing with source identity and SHA-256 provenance;
- project-bound registered STEP materialization and hash re-verification;
- isolated CadQuery 2.8 / OCCT exact BREP rendering;
- exact pair minimum-distance / intersection checks;
- exact surface anchors;
- anchor mating geometry;
- bounded sampled mating / insertion paths;
- adaptive transition refinement;
- operator claims separated from calibrated bench measurement sessions;
- explicit evidence / authority boundaries.

### 6. Build

The system is converging toward a build package that groups:

- reused resources;
- purchased resources;
- fabricated resources;
- substitutions;
- generated / imported CAD;
- wiring / interface plan;
- remaining measurements;
- evidence provenance;
- cost / procurement state;
- unresolved risks and required human verification.

## Sovereign adapter synthesis v0

The bounded `bridge_block_v0` path is the first missing-hardware synthesis family.

Two distinct, common-frame, approximately opposed planar **exact BREP anchors** can define a generated bridge candidate. Hardware Splicer then:

1. validates the two parent source hashes and declared poses;
2. validates the exact anchor dependencies;
3. generates a real CadQuery solid;
4. exports real STEP;
5. hashes the generated STEP;
6. tessellates it for the workbench;
7. checks exact OCCT minimum distance to both parents;
8. checks exact intersection volume against both parents;
9. returns PASS / REJECT / UNKNOWN without raising fabrication authority.

A geometry pass does **not** establish material, mounting, retention, tolerance, strength, manufacturability, electrical compatibility, fabrication or release authority.

## Canonical demonstration

### Cyberdeck

The first physical reference build should start with resources such as:

- donor display;
- SBC / mini-PC / x86 board;
- keyboard;
- battery / power bank;
- storage / hub;
- cooling hardware;
- donor enclosure / chassis parts;
- miscellaneous fasteners and brackets.

Mission example:

> **Build a portable Linux cyberdeck using as much existing hardware as possible under a bounded additional budget.**

The demo should show:

**physical pile → inventory → candidate architectures → concrete blocker → exact geometry → generated adapter → build output.**

The inspection rover is the broader mechatronics follow-up.

## Competitive boundary

Hardware Splicer does not need to beat specialist tools at every specialist task.

- Fusion / Onshape can remain advanced mechanical authoring backends.
- KiCad / Flux / Altium can remain ECAD backends.
- SPICE / robotics / FEA tooling can remain specialist solvers.

Hardware Splicer should be strong enough to finish ordinary resource-to-machine work itself and escalate specialist work when necessary.

The product distinction is upstream of conventional CAD:

> **“Here are the real parts I physically have. What can they become?”**

rather than only:

> “Design this already-specified component or assembly.”

## Evidence ladder

Do not collapse these evidence classes:

1. AI / photo inference;
2. operator claim / observation;
3. document / source evidence;
4. exact computational geometry;
5. calibrated instrument measurement;
6. controlled physical result;
7. explicit human release authority.

The system is intentionally allowed to return **UNKNOWN** when the evidence does not support a stronger claim.

## Current nonclaims

The current RC does **not** claim:

- metrology-grade dimensions merely because STEP exists;
- automatic semantic recognition of arbitrary connector pinouts;
- universal electrical / protocol compatibility;
- retention closure for generated adapters;
- structural / stress / fatigue / thermal validation;
- continuous whole-machine swept-volume proof;
- cable / service ergonomics closure;
- fabrication, power-on, motion or production release authority;
- measured market adoption, time savings or waste diversion before external physical cases exist.

## Product surfaces

- Web product entry: `/`
- Reuse mission: `/workbench/mission`
- Engineering workbench: `/workbench`
- HTTP API
- MCP
- CLI

All are intended to sit around the same evidence / engineering truth core.

## Developer quick start

```bash
git clone https://github.com/Spectating101/hardware-splicer.git
cd hardware-splicer
bash scripts/install_splice_v1.sh
source .venv/bin/activate
hs-doctor
make splice-ui-serve
```

For internal developer navigation, see [`docs/GITHUB_START_HERE.md`](docs/GITHUB_START_HERE.md) and the broader [`docs/`](docs/) tree.

## External proof backlog

Software closure is not physical proof. The next important evidence work is:

1. build the canonical cyberdeck;
2. fabricate at least one HS-generated adapter;
3. record actual fit success / failure;
4. record donor identity and measurement evidence;
5. repeat the workflow on an inspection rover or unrelated build;
6. persist successful and failed compatibility outcomes.

That observed compatibility history — not the current UI or generator alone — is what can become a durable moat over time.

## Submission doctrine

> **One evidence core → multiple external verdicts.**

Competition, research, partner and commercial material may change emphasis. They may not claim different truth states.

## License

Software license: **MIT** — see [`LICENSE`](LICENSE).

The system assists engineering and evidence workflows; **physical authorization remains explicitly bounded and human-scoped.**
