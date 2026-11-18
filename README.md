# Hardware Splicer

**Integrated GitHub features:** [available functionality, entry points and combined validation, November 16, 2026](docs/GITHUB_FEATURE_INTEGRATION_2026-11-16.md).

**Broader engineering-agent mission and operating contract:** [`docs/HARDWARE_SPLICER_MISSION_FREEZE.md`](docs/HARDWARE_SPLICER_MISSION_FREEZE.md). The bounded SPI adapter demonstration below is evidence of a particular current capability, not the full intended product scope.

**Software that runs the checks a hardware engineer would run before a circuit board is built, and packages the result so anyone can rebuild and verify it.**

![SPI flash adapter reference design, top copper layer](docs/product/media/spi_flash_adapter_v1-top.svg)

*The SPI flash adapter reference design: a routed two-layer board with 18 test points, produced and checked through the workflow.*

Hardware Splicer takes a board design through KiCad electrical and design-rule checks, a bill of materials and fabrication-file check, and a staged list of what must pass before bench work begins. An AI agent can do parts of the engineering, but only through those same checks: a model's suggestion never becomes a physical instruction on its own say-so.

| | |
|---|---|
| **Checks** | KiCad ERC and DRC, schematic-to-PCB parity, BOM and fabrication outputs, staged bench gates |
| **Interfaces** | Web UI, REST API, MCP server and CLI |
| **Reproducibility** | A packaged design rebuilds from its frozen source revision to the same published checksum |
| **Agent use** | External models work through the MCP gateway; runs are traced and audited against a fixed test set |
| **Status** | Software and design-review layer complete for the SPI reference design. **No board has been fabricated or measured yet**, and nothing here claims physical correctness |

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-splice-v1.txt -e '.[digital]'
.venv/bin/hs-digital cases
```

**Engineering operator pilot:** `python3 scripts/hs_workshop_operator.py --list` exposes
reviewed, bounded workflows that reuse the existing native verification and
repair/salvage engines. The [two real work-order runs](examples/workshop_operator/README.md)
show a successful SPI design check and a correctly blocked donor repair. This is
software-level engineering evidence, **not** an autonomous physical repair or
fabrication approval.

**Headless digital engine:** `hs-digital` and `hardware_splicer.sdk.digital_engine`
create/resume studies, change requirements, execute native CAD/physics jobs,
compare revisions, audit their evidence and export verified packages. Registered
cases include the HS-3G-B drone, [Fielddeck 7 cyberdeck](projects/cyberdeck-real-trial-20261020/digital_v1/README.md),
[Fielddeck 5 display revision](docs/status/generated/fielddeck-5-registered-20261118.json)
and [Ender-3 reference-donor pen plotter](projects/ender3-penplotter-digital/README.md).
`hs-digital cases` lists their supported requirements. Failed
requirements retain their artifacts. The current focus is the backend engine;
frontend work is deferred. See the [engine guide](docs/ENGINE.md#headless-digital-engine).
No HTTP server, browser, physical parts or model-service key is required.
See the [backend install and deployment guide](docs/PACKAGING_AND_DEPLOYMENT.md#current-headless-backend)
for the native dependencies, optional HTTP service and persistent state setup.

**Native source splicing:** uploaded KiCad boards can become editable project
revisions with their original footprints, pad/net identities and supplied project
rules. Engineering actions can import those sources and propose native edits;
reviews retain their original base, and native ZIP exports include the rule
companions. Source changes invalidate inherited verification results. See the
[native editing workflow](docs/ENGINE.md#native-source-editing-and-splicing).

**Part substitution:** compare a supplied replacement against the whole declared
assembly. HS reports electrical and mechanical conflicts, required adapters and
missing donor specifications, then exports the revised BOM, connection plan and
optional nominal STEP/STL. See the [substitution workflow](docs/ENGINE.md#part-substitution-across-a-declared-assembly).

**Robot donor example.** Can the passive servo from a SO-ARM102 leader drive the
follower shoulder? Run `hs-digital so102-drive shoulder --passive-leader`.
The result identifies the required motor, shared printed mount, bus wiring and
simulation joint, and explains which requirement the donor fails. Supply your
own servo profile or check a target joint angle using the [worked example](docs/ENGINE.md#so-arm102-follower-drive).

The [unseen Sweep keyboard challenge](eval/unseen_sweep/README.md) records what
HS got right, missed, and left open when assessing a previously unused split
keyboard. It includes donor decisions sealed before scoring, a reproducible
switch-to-controller map, and a PCB/schematic disagreement on both controllers.

The [five-device challenge](eval/unseen_devices/README.md) tests whether a tray
fits a printer, a robot joint can reach an angle, and parts of a handheld,
sensor logger and stereo amplifier can be reused. It includes an editable tray
model, the sealed decisions, the manufacturers' answers and board trace checks.

The [HS PCB inspection nest](projects/pcb-inspection-nest/README.md) is an
HS-authored digital hardware release candidate. One common dock accepts
three board-specific carriers. Its package includes editable CAD, print meshes,
source, and nominal fit checks.

Design principles and the full authority model: [`docs/DESIGN_PRINCIPLES.md`](docs/DESIGN_PRINCIPLES.md).

## Evaluators / competitions / research reviewers

**Current product front door:** [`docs/product/README.md`](docs/product/README.md)

The current product package is bound to frozen release commit
`f892facd67c5124e2362860ebc999625afedc5d5`, tag
`gauntlet-spi-flash-adapter-v1-20260916`, and the explicit
`PACKAGED_NOT_PHYSICAL` boundary.

The older Q3 assessment directory remains the deeper evidence and historical submission layer:

[`docs/external_assessment/SUBMISSION_PACKAGE_2026Q3.md`](docs/external_assessment/SUBMISSION_PACKAGE_2026Q3.md)

Then use:

- [`PROJECT_IDENTITY.md`](docs/external_assessment/PROJECT_IDENTITY.md) — bounded project identity;
- [`CLAIMS_AND_NONCLAIMS.md`](docs/external_assessment/CLAIMS_AND_NONCLAIMS.md) — exact claim boundary;
- [`EVIDENCE_LEDGER.md`](docs/external_assessment/EVIDENCE_LEDGER.md) — what evidence supports each claim;
- [`MASTER_DECK_12_SLIDES.md`](docs/external_assessment/MASTER_DECK_12_SLIDES.md) — canonical external narrative;
- [`SOLO_ROUTING_2026.md`](docs/external_assessment/SOLO_ROUTING_2026.md) — current solo-first submission routing;
- [`demos/DEMO_3_MINUTES.md`](docs/external_assessment/demos/DEMO_3_MINUTES.md) — canonical short demonstration.

## Current state

**SOFTWARE ARCHITECTURE FROZEN / EXTERNAL PROOF + PHYSICAL REFERENCE DESIGN ACTIVE**

| Evidence layer | State |
|---|---|
| frozen software architecture | **PROVEN** |
| deterministic adversarial cleanroom | **PROVEN** |
| frozen ten-case unseen SPI corpus | **PROVEN AS CORPUS/PROTOCOL** |
| canonical MCP gateway | **PROVEN** |
| external-agent runner / trace audit | **PROVEN AS INFRASTRUCTURE** |
| live external-model bounded engineering run | **PROVEN AS EXISTENCE DEMONSTRATION** |
| hash-bound primary-source Astra run | **PROVEN AS ONE PREREGISTERED RUN** |
| SPI KiCad schematic/PCB internal consistency | **PROVEN: ERC/DRC/PARITY CLEAN** |
| fresh revision-bound SPI physical correctness | **PENDING** |
| independent human operator | **PENDING** |
| production / industrial deployment readiness | **NOT CLAIMED** |

The project is now **physical-evidence-blocked, not CAD- or agent-feature-blocked**. The SPI
reference design closes the missing schematic/PCB/package layer without claiming that software
checks replace independent review, fabrication inspection, or bench measurement.

## Architecture

```text
General-purpose AI / agent
          │
          ▼
       MCP / API
          │
          ▼
┌─────────────────────────────────────────┐
│            HARDWARE-SPLICER             │
│                                         │
│ project + exact revision state          │
│ source/evidence provenance              │
│ semantic engineering planning           │
│ deterministic interface constraints     │
│ engineering artifacts / package         │
│ revision-bound physical evidence        │
│ authorization ledger                    │
└─────────────────────────────────────────┘
          │
          ▼
      candidate / package
          │
      evidence gates
          │
          ▼
     human authorization
          │
          ▼
       physical world
```

### Model independence

The current external-agent path exposes the canonical product backend through a four-tool MCP discovery/dispatch gateway rather than duplicating engineering logic in the adapter.

At the current external-proof checkpoint, exact-head CI has exercised:

- a real MCP stdio client;
- a real MCP Streamable HTTP client;
- canonical stateful project write → read → delete through MCP;
- the installed canonical MCP entry point;
- frozen ten-case external corpus inventory;
- the non-golden external trace audit;
- every canonical backend operation in the generated OpenAPI catalog (the live count is
  `backend_contract()["operation_count"]`; it changes as the API grows, so it is not restated here);
- `physical_authority_granted = false` at the MCP boundary.

This proves the engineering surface and proof harness exist. Separate durable Astra evidence now
also establishes successful bounded operation on the primary-source SPI case; it does not establish
distributional reliability across the entire frozen corpus.

## Primary bounded application

The clean external application is **semiconductor test and validation support hardware**, including:

- adapter boards;
- carrier boards;
- validation fixtures;
- lab/NPI support hardware;
- related electromechanical preparation.

Hardware-Splicer is not presented as:

- chip design;
- wafer-process automation;
- autonomous production certification;
- universal EDA replacement;
- a system that treats model confidence as verification.

## What makes the system different

A generic AI assistant can propose an answer. Hardware-Splicer additionally preserves independent structures for:

- exact or unresolved component identity;
- evidence provenance;
- deterministic electrical/interface constraints;
- exact project/revision/artifact state;
- stale-evidence invalidation;
- explicit real-vs-simulated physical evidence;
- scoped human authorization;
- replayable adversarial agent traces.

The system therefore evaluates not only **whether the AI is right**, but also **what happens when it is wrong**.

## Adversarial external proof

The frozen unseen SPI-flash corpus contains ten cases:

1. baseline;
2. source reverse;
3. source rotate;
4. neutral labels;
5. mission paraphrase;
6. partial evidence;
7. identity conflict;
8. parser failure;
9. analogy trap;
10. stale revision.

The external-agent runner can preserve model requests/responses, MCP calls, case-scoped state and replay material while the trace audit checks for incomplete calls, foreign project scope, unsupported evidence identity and attempts to open physical authority.

The published live provider result is an existence demonstration, not a completed reliability
matrix. Frozen cases and historical result bundles must not be rewritten after results are visible.

## Physical evidence and authority

Software success is not physical success.

Real physical evidence must explicitly identify itself as real (`simulated: false`) and remain tied to the relevant project revision/artifact boundary. Missing or ambiguous simulation state is blocking. Authorization is an explicit human-scoped decision and does not automatically survive relevant revision or artifact changes.

A prior golden-real bench path demonstrates that the evidence/authority machinery can consume explicitly real evidence. It does not close the fresh adversarial SPI physical proof chain.

## Product surfaces

Hardware-Splicer contains Web UI, HTTP API, MCP and CLI surfaces around the same engineering truth core.

The repository also retains earlier Splice/Circuit/mechanical lineage and internal engineering documentation. Those materials are useful for development history but are **not the recommended evaluator entry point**.

## Developer quick start

```bash
.venv/bin/python -m pip install -e '.[dev]'
make verify-headless-backend
```

See the [headless backend verification scope](docs/PACKAGING_AND_DEPLOYMENT.md#headless-backend-verification) and [developer navigation](docs/GITHUB_START_HERE.md).

## Canonical generated artifacts

Representative durable outputs include:

- `PROJECT_PACKAGE.json`;
- KiCad carrier / DRC evidence;
- `SPLICE_PLAN.json`;
- `SPLICE_BENCH_SESSION.json`;
- `COMPILE_CASEFILE.json` on failure;
- revision-bound evidence and authorization records;
- external-agent trace/replay artifacts when a live run is executed.

## Submission doctrine

> **One evidence core → multiple external verdicts.**

Competitions, papers, grants and partner reviews may receive different emphasis and formatting. They may not receive different truth states.

See [`docs/external_assessment/`](docs/external_assessment/) for the controlled external package.

## License

Software license: **MIT** — see [`LICENSE`](LICENSE).

The system assists engineering and evidence workflows; **physical authorization remains explicitly bounded and human-scoped.**
