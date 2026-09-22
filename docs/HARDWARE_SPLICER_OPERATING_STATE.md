# Hardware-Splicer Operating State

Status: **flagship / selectively active**  
Snapshot: **2026-09-23**  
Canonical machine state: `docs/HARDWARE_SPLICER_OPERATING_STATE.json`

Hardware-Splicer is not being wound down. It is being run as a **selectively invested flagship**: continue improving the parts that are native to physical-agent engineering, hardware evidence, revision-bound verification, physical bring-up, and release authority; integrate commodity/source-tool capability rather than rebuilding it; and force external proof before opening broad new product scope.

## Product identity

Hardware-Splicer is an **evidence and release-assurance system for AI-assisted hardware**.

Its strongest question is:

> What has actually been established about this exact hardware artifact and revision, what evidence remains valid, what remains unproven, and what physical action is authorized next?

The system is strongest when it binds:

`artifact/revision -> engineering evidence -> deterministic verification -> physical evidence -> explicit human authority`

The system is **not** trying to become a universal browser EDA suite, autonomous PCB generator, generic MCP/device-control framework, or substitute for KiCad/Altium/Cadence/Flux.

## Current priority stack

### P0 — close the physical-evidence gap

Tracking: `#105`  
Execution contract: PR `#106`

The frozen SPI reference design is already packaged and digitally verified but remains physically `UNPROVEN`. The active campaign is therefore:

`independent review -> fabrication decision -> assembly identity -> cold checks -> controlled power -> bounded 0x9F test -> evidence closure`

Until that chain exists, fabrication, power-on, functional-test, and release authority remain closed.

### P1 — complete the competitive product shell

Tracking: PR `#104`

The Review / Compare / Verify / Bring-up workspace is the current frontend closure candidate. It exists to bring HS to competitive usability while preserving the evidence/authority model.

After closure, frontend work reopens only when:

- rendered use exposes a concrete deficiency;
- an evaluator/user cannot complete an HS-native workflow;
- a source-bound competitor change exposes a specific native gap.

### P1 — external conversion

Gauntlet should actively use HS where the reason for the opportunity is hardware, physical agents, release assurance, consequential authority, or embodied-system evidence.

Current primary/conditional HS routes:

- SPI external physical/FCT proof;
- Anthropic MHS Research Preview;
- Anthropic External Researcher Access;
- DATE 2027 LBR after substantive physical/external proof;
- InnoServe Industrial AI if adviser/team/category gates clear without a broad product sprint;
- Anthropic AI for Science after physical/evidence and eligibility gates clear.

Generic research-access, cloud-credit, or compute opportunities may be led by Cite, Research Drive, YZUC, Refinery, or another portfolio asset when they are the more native fit. That is a route-allocation choice, **not** a reduction in HS capability.

## Competitive development rule

Competition is an input to improvement, not a stop signal and not an automatic build order.

Use four response classes:

| Competitor change | HS response |
|---|---|
| Presentation / comprehension | Improve the HS shell. |
| Workflow | Improve HS if the current evidence/authority model already supports it. |
| Integration / commodity source-tool capability | Integrate; do not rebuild the external tool. |
| Truth-model implication | Require an exact HS defect, evaluator finding, or physical failure before investigating the core. |

Current watch/decision producer: Refinery PR `Spectating101/refinery#24`.  
Current consumer/routing policy: Gauntlet PR `Spectating101/gauntlet-blowback#60`.

The current external comparison set includes Flux, AllSpice DRCY, Circuitly, Schematik, Cadence, Groundrun, Anthropic MHS, JITX, Quilter, DeepPCB, Circuit Mind, CELUS, and Boardera.

## What is frozen versus active

| Surface | State | Rule |
|---|---|---|
| Evidence / authority core | **Frozen by default** | Reopen only from an exact artifact/evaluator/physical defect. |
| SPI physical proof | **Active / P0** | Highest-leverage engineering campaign. |
| Competitive frontend | **Closure candidate / P1** | Finish coherent shell; reopen only from concrete gap. |
| Route-specific integrations | **Allowed / P1-P2** | Build only when native, source-bound, and useful to a real workflow/route. |
| Generic feature expansion | **Off by default** | No generic AI/EDA feature race. |
| Competitor-driven improvement | **Allowed and expected** | Improve HS where the gap is native and evidence-backed. |
| Gauntlet conversion | **Active** | Force external verdicts instead of manufacturing endless internal maturity. |

## What counts as useful HS progress now

A change is worth doing when at least one is true:

1. it closes a physical/evidence gap;
2. it materially improves an HS-native workflow versus credible competitors;
3. it unlocks or strengthens a real external route;
4. a user/evaluator/provider exposes a concrete problem;
5. it adds interoperability without duplicating an external tool;
6. it improves the paper or empirical evidence with a real result.

A change is **not** justified merely because a competitor announced a feature, a grant offers compute, or HS technically could implement it.

## Repricing events

The project should be reassessed after major external evidence, not mood or competitor-count alone.

Positive repricing events include:

- one complete revision-bound physical SPI evidence chain;
- an external design/evaluator board processed end to end;
- meaningful MHS or external-research engagement;
- paper acceptance or serious reviewer interest;
- a pilot/design partner asking to use the evidence/release layer;
- a competitor change that validates HS's release/evidence layer as a missing infrastructure category.

Negative repricing requires evidence too: repeated external non-interest after serious conversion attempts, an inability to demonstrate useful physical assurance, or direct subsumption of the exact HS-native evidence/authority function—not simply the existence of many adjacent competitors.

## Program map

```text
Refinery
  observe competitor / ecosystem change
        |
        v
  classify: shell / workflow / integration / truth-model
        |
        v
Gauntlet
  portfolio bake-off + priority + route ownership
        |
        +------------------------------+
        |                              |
        v                              v
Hardware-Splicer                  other portfolio asset
  bounded improvement             when route fit is better
  or physical proof
        |
        v
external verdict / physical evidence
        |
        v
update claims, paper, roadmap, and next investment decision
```

## Near-term closure sequence

1. Finish and review PR `#104` as the competitive frontend closure candidate.
2. Land PR `#106` as the physical-proof execution contract.
3. Execute `#105` through provider/reviewer contact and explicit fabrication decision.
4. Preserve every physical result—success or failure—against the exact board/revision.
5. Update the paper only after evidence exists.
6. Fire the strongest HS-native Gauntlet routes with the improved artifact/evidence package.
7. Reassess HS from external outcomes and physical evidence, not from generalized pessimism.

The intended state is **not smaller HS**. It is a stronger HS with a narrower definition of what deserves engineering time.