# Competitive category shift — physical capability transformation

Snapshot: **2026-09-24**

This note records a bounded strategic hypothesis opened by Product Factory work. It does not replace the canonical claims boundary and it does not assert that Hardware-Splicer has already demonstrated a commercial or physical moat.

## Observed competitor center of gravity

As of the snapshot date, the public product surfaces of the main comparison set remain concentrated primarily inside the **new-design and design-release pipeline**:

| Product | Publicly marketed center of gravity | Source |
|---|---|---|
| Flux | requirements/idea -> component research -> schematic/BOM -> PCB layout -> manufacture | https://www.flux.ai/p |
| Circuit Mind | requirements/architecture -> optimized component selection -> verified schematic/BOM and engineering analysis | https://www.circuitmind.io/product |
| CELUS | requirements -> trusted reference designs -> schematic/BOM -> native EDA handoff | https://www.celus.io/ |
| JITX | requirements/rules expressed in code -> generated/optimized electronics, routing/analysis and simulation loops | https://www.jitx.com/ |
| Quilter | physics-driven automated PCB layout, routing and increasing board-complexity automation | https://www.quilter.ai/newsroom/quilter-bga-fanout-automation-2026-releases |
| AllSpice | hardware design review, revision collaboration and release/manufacturing handoff | https://learn.allspice.io/docs/create-a-release |

This table describes each product's public center of gravity. It is **not** a claim that those products cannot support adjacent reuse, modification, integration or custom workflows.

## HS category hypothesis

Hardware-Splicer should not win by rebuilding every feature above.

Its stronger system boundary is:

```text
physical capability requirement
            |
            v
  capability-source decision
   /       |        |       \
new     modify    reuse    hybrid/splice
design  existing  module   donor + new
   \       |        |       /
            v
  engineering transformation
            |
            v
 deterministic verification
            |
            v
 revision-bound physical evidence
            |
            v
 explicit human release authority
```

The core question becomes larger than "How should this PCB be designed?"

> **What is the cheapest defensible route from a capability requirement to an exact verified physical artifact?**

The answer may use:
- newly purchased components;
- an existing board or product;
- an intact reusable module;
- a qualified donor device;
- recovered subassemblies;
- a hybrid architecture;
- external EDA/design tools.

## Architectural invariant: external tools are operators, not identity

If an outside system becomes substantially better at a commodity engineering operation, HS should integrate it where the evidence/authority boundary can be preserved.

Examples:

```text
architecture generation -> Circuit Mind / CELUS / another provider
schematic/PCB editing    -> Flux / KiCad / Altium / another provider
automated layout         -> Quilter / JITX / another provider
design review            -> AllSpice / another provider
```

Those names are examples, not required dependencies or endorsements.

HS remains responsible for the higher-order state:

```text
requirement
-> source/build/reuse decision
-> exact artifact/revision identity
-> transformation plan
-> evidence provenance
-> deterministic checks
-> physical evidence
-> scoped human authority
```

This preserves strategic value even if individual EDA primitives commoditize.

## Product Factory as an empirical competitive benchmark

Product Factory is not merely a hardware-revenue experiment. It is a way to test whether this category hypothesis is real.

Current runs exercise materially different capability classes:

- **PF-001 / ProofPod** — clean-sheet product creation.
- **PF-002 / BenchHMI** — donor remanufacture: preserve integrated POS subsystems and add a new automation layer.
- **PF-003 / FieldDeck** — deeper splicing: preserve an industrial tablet and add keyboard/dock plus protected field I/O.

The competitive claim ceiling rises only with physical results.

### Evidence ladder

**Level 0 — architecture only**

HS has software/data structures for build-vs-reuse-vs-splice decisions.

Allowed claim: the workflow exists.

**Level 1 — one revision-bound physical transformation**

One donor/new-build run reaches a working artifact with measured COGS and exact evidence.

Allowed claim: HS has demonstrated one transformation.

**Level 2 — heterogeneous repeatability**

Several materially different donor/product classes reach physical proof using the same core workflow.

Allowed claim: evidence supports a more general transformation capability.

**Level 3 — commercial repeatability**

Multiple runs include real acquisition cost, yield, rework, warranty/return behavior and paid customer outcomes.

Allowed claim: HS has evidence for repeatable economic value creation.

Until those levels are reached, terms such as "moat", "defensible transformation engine" or "general hardware factory" remain hypotheses rather than proven claims.

## Why donor transformation could become defensible

A mature system may accumulate data that ordinary EDA and marketplace layers do not naturally join:

```text
exact donor/product identity
-> revision variance
-> acquisition cost
-> measured usable yield
-> retained subsystem capability
-> common failure modes
-> transformation architecture
-> rework time
-> new-material cost
-> physical QA
-> final COGS
-> benchmark
-> commercial outcome
```

The possible defensibility is therefore not "we know how to refurbish old electronics."

It is the accumulated mapping:

> **existing physical artifact -> reusable capability -> verified transformation -> economic outcome**

That claim remains prospective until the Product Factory produces enough external and physical evidence.

## Non-goals

This strategy does not authorize:

- a generic e-waste marketplace;
- importing regulated waste without proper classification/authorization;
- unsafe battery or mains modification;
- claiming industrial certification after an unqualified modification;
- replacing specialist EDA/CAE tools merely to own more code;
- treating listed secondary-market inventory as qualified supply;
- treating attractive paper COGS as product-market fit;
- treating one successful splice as proof of generality.

## Decision rule

A new competitive feature or external-tool release should be evaluated against this hierarchy:

1. **Does it expose a defect in HS's evidence/authority/transformation model?** Investigate the core.
2. **Does it provide a better commodity engineering primitive?** Integrate rather than duplicate.
3. **Does it improve a real Product Factory or customer transformation?** Add a bounded adapter/workflow.
4. **Is it merely another feature race inside EDA?** Do not build by default.

The intended competitive posture is therefore not "HS versus every EDA vendor."

It is:

> **HS orchestrates the route from physical requirement to verified artifact, while specialist tools may execute individual engineering operations underneath that authority/evidence layer.**
