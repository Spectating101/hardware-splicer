# Competitive interface acceptance — Hardware Splicer vNext

**Status:** active product rule for `frontend/evidence-workbench-vnext`  
**Scope:** frontend / product shell only. The frozen evidence and authority core remains unchanged.

## Rule

Hardware Splicer interface work is not accepted merely because it looks cleaner than the previous HS interface.

Every material UI tranche must be evaluated against the strongest relevant external products and must answer four questions:

1. **Parity** — which interaction is already table stakes elsewhere and must be at least as easy here?
2. **Differentiation** — what can HS make legible that the comparison product does not center?
3. **Integration** — which external capability should HS consume or deep-link instead of rebuilding?
4. **Restraint** — which attractive competitor feature should HS deliberately not copy because it dilutes the evidence / release-assurance position?

A tranche fails review if it adds visual complexity without improving one of those four dimensions.

## Standing comparison set

Refresh this set when Refinery or a new market scan finds a materially stronger reference product.

| Reference | Interaction to benchmark | HS requirement |
|---|---|---|
| **Flux** | artifact-first schematic / PCB workspace; contextual inspection; low-friction project navigation | HS artifact viewport must feel equally immediate. Do not rebuild a full ECAD editor; deep-link or adapt external/native editing instead. |
| **AllSpice / DRCY** | review findings attached to the design and inspectable supporting evidence | HS findings must attach to the affected engineering object/artifact and expose evidence/revision consequences with no report-hunting. |
| **Circuitly** | current state vs proposed change; agent work remains reviewable before merge | HS Compare must make current/proposed/evidence-invalidated/re-check-required state clearer than a generic code-review metaphor. |
| **Schematik** | extremely obvious first-use path and low cognitive load | A new user must understand what the project is, what is wrong, and what to do next without learning HS vocabulary first. |
| **Cadence-class EDA** | dense professional engineering information without dashboard theatrics | HS must look like an engineering instrument, not an AI SaaS landing page. |
| **Groundrun / hardware-in-loop tools** | real physical-device validation loop | HS Bring-up must distinguish exact artifact revision, real measurement evidence, gate state and human authorization rather than merely showing test execution. |
| **MHS / MCP ecosystem** | standardized agent/tool/device access | Treat connectivity as infrastructure. HS UI differentiates above transport: evidence validity, stale-state handling and release authority. |

## Competitive acceptance axes

Score each material surface qualitatively as **behind / parity / ahead / intentionally out of scope**. Do not publish a fake numeric score.

### 1. Ten-second comprehension

A first-time engineer should be able to answer, without opening documentation:

- What artifact am I looking at?
- Which revision is this?
- What is wrong or unresolved?
- What is actually verified?
- Is fabrication / power-on / release currently permitted?
- What is the next sensible review action?

**Benchmark pressure:** Schematik simplicity; Flux workspace legibility.

### 2. Artifact primacy

The engineering artifact should dominate the screen. Project chrome, AI controls and explanatory prose are secondary.

**Benchmark pressure:** Flux / mature EDA tools.

Acceptance:

- schematic/PCB/physical artifact occupies the primary visual area;
- object selection persists into findings/evidence/history;
- artifact can be swapped through an adapter/viewer contract;
- editing remains in the source tool unless HS has a justified, bounded mutation path.

### 3. Findings in context

A blocker must be reachable from the affected object and artifact position, not only from a report list.

**Benchmark pressure:** AllSpice.

HS must additionally expose:

- exact project revision;
- evidence identity;
- whether the finding is deterministic, model-derived, physical or human;
- what downstream evidence/authority it blocks or invalidates.

### 4. Change review

Proposals are never silently treated as project truth.

**Benchmark pressure:** Circuitly / modern source-control review.

HS must make visible:

- current state;
- proposed successor;
- semantic delta;
- evidence carried forward;
- evidence invalidated;
- deterministic / physical checks that must be repeated;
- explicit human decision boundary.

### 5. Evidence inspection

Evidence should be close to the claim it supports.

HS should avoid evidence walls or prose-heavy dashboards. Prefer compact source chips, exact references, drill-down panels, overlays and timelines.

The differentiated HS question is not merely **"what source did the AI use?"** but **"what claim does this evidence support for this exact revision, and is it still valid?"**

### 6. Physical bring-up

This is a primary differentiation surface, not an appendix.

The interface should behave like a lab / release instrument:

`identity -> cold checks -> controlled power -> functional test -> release`

Each stage should distinguish:

- required evidence;
- captured real measurement;
- simulated / missing evidence;
- exact artifact revision;
- invalidated prior evidence;
- operator/human decision;
- resulting authority state.

**Benchmark pressure:** hardware-in-loop products.  
**HS exceed condition:** test execution does not automatically equal physical/release authority.

### 7. Revision continuity

The timeline must show engineering state through time, including failures and evidence invalidation. Do not flatten history into the latest green state.

A user should be able to see:

`proposal -> deterministic check -> failure -> successor -> re-check -> fabrication -> measurement -> authorization`

### 8. Visual discipline

Default language:

- neutral white / stone / graphite surfaces;
- color only for meaningful state;
- green = established/passed;
- amber = attention/review;
- red = failed/blocked;
- gray = unavailable/not established;
- blue only for ordinary interaction/selection when needed.

Avoid:

- AI gradients;
- decorative blue/cyan/violet taxonomies;
- excessive rounded cards;
- glowing panels;
- marketing phrases in operator UI;
- paragraphs where an object, state, icon, timeline or overlay communicates the same thing faster.

## Build / integrate / ignore test

When Refinery detects a competitor release, classify the response before creating a feature ticket.

| Class | Response |
|---|---|
| **Presentation** | Copy the useful interaction principle if it improves clarity. Core untouched. |
| **Workflow** | Implement when current HS evidence semantics already support it. |
| **Integration** | Add adapter/deep link/import rather than duplicating a mature external capability. |
| **Core semantic gap** | Do not change the frozen core from competitive pressure alone. Require a real unseen/live/physical artifact demonstrating the missing truth state. |
| **Commodity capability** | Stop marketing it as differentiation. Keep only what is needed for interoperability. |
| **Strategic distraction** | Explicitly decline it. |

## Per-PR checklist

Every major HS frontend PR should state:

- **Reference interfaces checked:** which current products/patterns were used as comparison;
- **Parity target:** which interaction must no longer feel inferior;
- **HS delta:** what evidence/authority behavior should be visibly stronger or different;
- **What we refused to rebuild:** external/native capability kept outside HS;
- **Frozen-core impact:** normally `none`;
- **10-second test:** what a first-time user can identify immediately;
- **Artifact-first check:** percentage/qualitative dominance of actual engineering artifact vs chrome/prose;
- **Physical-boundary check:** confirm software/viewer/model state cannot visually imply physical authority.

## Current vNext target

The current interface tranche should converge toward one consistent shell:

```text
project / revision / compact authority state
-----------------------------------------------------------
objects/findings |     engineering artifact     | inspector
                 | schematic / PCB / compare   | evidence
                 | or physical bring-up view    | finding
-----------------------------------------------------------
revision / evidence / physical-validation timeline
```

Modes such as Review, Compare, Verify and Bring-up should increasingly change the center viewport and inspector rather than create unrelated dashboard pages.

## Strategic test

A competitive UI change is worthwhile only when it does at least one of the following:

- makes HS as easy to understand as the best adjacent product;
- makes an HS-specific evidence/authority distinction obvious without explanatory prose;
- converts a competitor into an upstream/downstream integration instead of a feature race;
- reduces the time from opening a project to a defensible engineering decision.

If it does none of these, do not build it.
