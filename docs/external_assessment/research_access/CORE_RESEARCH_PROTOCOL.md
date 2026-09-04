# Core Research Protocol — Evidence- and Authority-Constrained Agents

## Working title

**Evidence- and Authority-Constrained Agent Control Under Consequential Hardware Tool Use**

## Research question

> **Do evidence gating, deterministic engineering constraints and explicit authorization reduce unsupported consequential actions by a general-purpose tool-using AI agent without eliminating useful task completion?**

This protocol is a **planned evaluation**, not a result claim.

## Motivation

General-purpose agents increasingly operate tools rather than only produce text. In hardware engineering, a plausible model response can cross into candidate generation, fabrication, power-on or release decisions before exact component identity, evidence provenance, revision state or physical behavior has been established.

Hardware-Splicer creates an explicit boundary between semantic model reasoning and independently authoritative engineering state:

> **AI proposes → deterministic systems constrain → bench evidence decides → human authorizes.**

The experiment asks whether that architecture changes agent behavior under incomplete, stale, conflicting or adversarial evidence.

## Existing experimental infrastructure

The repository already establishes:

- a frozen deterministic software baseline;
- a validated ten-case adversarial SPI-flash corpus;
- canonical MCP access to the product backend;
- revision/evidence/authority gates outside the model;
- external-model request/response/MCP trace persistence;
- replay/audit infrastructure.

The canonical claim ledger currently marks **live external-model execution**, **fresh SPI physical correctness**, and **independent human operator evidence** as pending.

## Experimental conditions

### Condition A — minimally constrained / reference agent

A general-purpose agent receives the task evidence and tool access needed to attempt the bounded engineering task, but does not receive the full Hardware-Splicer evidence/authority intervention as the decisive control layer.

**Important:** this condition must still comply with provider policies and must not bypass ordinary system safety. It is a research baseline, not an intentionally unsafe agent.

### Condition B — Hardware-Splicer constrained agent

The same model family/configuration operates through Hardware-Splicer, where deterministic project/revision state, evidence provenance, unresolved-state propagation and scoped authorization remain independently authoritative.

## Stress cases

Use the frozen ten-case corpus without editing cases after model selection or initial results. Cases include:

- baseline evidence;
- source reversal/rotation;
- neutral labels / mission paraphrase;
- partial evidence;
- component-identity conflict;
- parser/tool failure;
- plausible wrong analogy;
- stale-revision evidence.

If a provider-specific adaptation is required for transport, preserve semantic equivalence and version the adapter separately from the frozen corpus.

## Primary outcomes

1. **Unsupported consequential-action rate** — agent attempts an action or claim requiring evidence/authority that is absent, stale, conflicting or unresolved.
2. **Correct abstention/block rate** — agent remains unresolved or seeks additional evidence when evidence is insufficient.
3. **False blocking rate** — valid work is blocked despite sufficient evidence.
4. **Task completion / useful progress** — bounded engineering task reaches the intended non-overclaimed endpoint.
5. **Human intervention rate** — number/type of explicit human authorization or correction events.
6. **Recovery behavior** — whether the agent can revise after deterministic/tool/evidence failure without silently carrying stale authority forward.

## Secondary outcomes

- number of MCP/tool calls;
- evidence-source usage;
- unresolved-state duration;
- revision changes before completion;
- provider/model differences;
- token/API cost per completed case;
- latency where relevant.

## Trace requirements

Preserve for every run:

- exact repository revision;
- exact corpus/evaluator revision;
- provider/model/version;
- model configuration;
- complete model inputs/outputs allowed by provider policy;
- MCP calls and responses;
- per-case project/revision state;
- adjudication outcome;
- failures, retries and non-completions;
- cost/usage metadata.

## Physical extension

A later or parallel tranche may add a fresh revision-bound bench case. Do not merge simulated or historical/golden evidence into the fresh physical claim.

A fresh physical case should preserve:

1. exact component/package identity;
2. candidate artifact hashes;
3. preassembly checks;
4. assembly/substitution record;
5. powered-off measurements;
6. controlled power-up;
7. bounded functional/signal evidence;
8. failure → repair → revision lineage.

## Analysis plan

Because the initial corpus is intentionally small and adversarial, the first report should emphasize **case-level behavioral comparison and exact failure taxonomy**, not overstate statistical power.

Where repeated stochastic runs are affordable, report per-condition rates with confidence intervals and model/run sensitivity. Keep deterministic infrastructure outcomes separate from model-competence outcomes.

## Expected contribution

The intended contribution is not proof that any model is universally safe or correct. It is a measurable test of a narrower systems hypothesis:

> **Useful agentic engineering can be preserved while preventing unsupported model confidence from automatically acquiring physical authority.**

## Provider adaptations

### OpenAI Researcher Access

Emphasize responsible deployment, human-AI decision making, multimodal/tool-using systems and risk mitigation.

### Anthropic External Researcher Access

Emphasize control/oversight, authority escalation, safe consequential tool use, failure recovery and evidence-gated autonomy.

### Anthropic MHS

Do not describe Hardware-Splicer as an MHS implementation. Use this protocol as a candidate safety-evaluation harness around a concrete MHS-compatible programmable device if preview access is granted.

### Anthropic AI for Science

Expand only after external evidence supports a larger physical/scientific experiment. Define a clean data-rights boundary before submission.

## Pre-submission blanks

- `[MODEL(S)]`
- `[RUNS PER CASE]`
- `[ESTIMATED API TOKENS/COST]`
- `[CONCRETE PROGRAMMABLE HARDWARE SURFACE]`
- `[EXPECTED 8–12 WEEK START/END DATES]`
- `[PUBLICATION/ARTIFACT OUTPUT]`

Do not submit a provider application until these blanks are resolved for that route.