# Frontier Operator Experiment — zero-spend staging

## Purpose

Prepare Hardware-Splicer to compare frontier multimodal/agent models without turning
model novelty into an automatic API bill or weakening HS's evidence hierarchy.

This lane is **exploratory only**. The frozen external-proof core remains separate.

## Current provider targets

Verified against provider documentation on 2026-09-10:

| Provider | API model id | Text input | Text output | Remote MCP | Image input |
|---|---|---:|---:|---|---|
| OpenAI | `gpt-6-astra` | $10 / MTok | $50 / MTok | yes | yes |
| Anthropic | `claude-fable-5` | $10 / MTok | $50 / MTok | yes | yes |

Provider references:

- OpenAI Astra model page: https://developers.openai.com/api/docs/models/gpt-6-astra
- OpenAI Astra model guidance: https://developers.openai.com/api/docs/guides/latest-model
- Anthropic MCP connector: https://docs.anthropic.com/en/docs/agents-and-tools/mcp-connector
- Anthropic Fable migration/model guidance: https://docs.anthropic.com/en/docs/about-claude/models/migrating-to-claude-4

Do not infer future aliases from product naming. The current public Anthropic API target
used here is `claude-fable-5`.

## Why this belongs above HS rather than inside its truth core

The frontier model is an operator/reasoner. HS still owns:

- canonical project and revision state;
- deterministic electrical/interface constraints;
- exact geometry and BREP checks;
- evidence identity and provenance;
- stale-evidence invalidation;
- physical-evidence classification;
- scoped human authority.

A visually convincing assembly is not exact geometry. A model assertion is not physical
evidence. A successful tool trace is not physical correctness.

## Zero-spend staging

`src/hardware_splicer/frontier_operator_experiment.py` performs no network I/O. It owns:

- current model/price metadata for the two exploratory targets;
- conservative uncached text-token estimates;
- explicit live-run policy validation;
- OpenAI Responses/MCP request templates;
- Anthropic Messages/MCP request templates;
- Anthropic MCP trace normalization into the existing HS audit shape.

`scripts/plan_frontier_operator_experiment.py` also performs no network I/O and does not
read provider credentials.

Example cost planning only:

```bash
python scripts/plan_frontier_operator_experiment.py --model gpt-6-astra
python scripts/plan_frontier_operator_experiment.py --model claude-fable-5
```

At the default planning envelope of 40k input + 8k maximum output tokens per case, either
$10/$50 model is estimated at $0.80 per case or $8.00 across ten cases **before** any
extra provider/tool charges or token growth from MCP results.

That number is a planning envelope, **not a guaranteed provider billing ceiling**.

## Live-run policy

Any future paid runner must call `validate_live_policy` before provider I/O and preserve
all of these requirements:

1. positive explicit `max_usd`;
2. exact charge acknowledgement `I_ACCEPT_PROVIDER_CHARGES`;
3. one live case by default;
4. multi-case execution requires an additional explicit opt-in;
5. the estimated text-token envelope must fit inside the declared budget;
6. provider credentials are never persisted into proof artifacts;
7. failures and partial runs remain evidence.

The planner can validate and record an armed plan without spending anything:

```bash
python scripts/plan_frontier_operator_experiment.py \
  --model gpt-6-astra \
  --case-id spi-flash-adapter-baseline \
  --arm-live \
  --max-usd 1.00 \
  --confirm-charges I_ACCEPT_PROVIDER_CHARGES
```

Even `--arm-live` performs no model request.

## Provider shape

### OpenAI / Astra

Use the Responses API, low reasoning effort initially, `store=false`, and the same four
canonical HS MCP gateway tools. Do not silently replace the preregistered core model in
an existing experiment; record Astra as a separate exploratory tranche.

### Anthropic / Fable

Use the Messages API MCP connector beta `mcp-client-2025-11-20`. Configure one MCP
server and an allowlist-only `mcp_toolset`: all tools disabled by default, then explicitly
enable only the four canonical HS gateway operations.

Fable's current model guidance uses provider-managed adaptive thinking. Cost control
therefore comes from low effort, bounded output, small case count, and experiment-level
budget gates rather than a manual hidden-thinking token budget.

## Stage 1 — same frozen engineering cases

Run a small exploratory comparison only after the provider adapters and budget guards are
fully green:

- baseline current HS external operator;
- Astra;
- Fable.

Compare completion, hard-truth contract failures, tool-path efficiency, evidence identity,
authority discipline, unresolved-state discipline, and equivalent-case trace drift.

Start with **one case per provider**. Expand only after inspecting actual billed usage.

## Stage 2 — visual geometry loop

The more interesting later experiment is not prettier rendering. It is whether a frontier
multimodal operator can use render feedback to steer HS's exact engineering substrate:

`candidate -> render -> visual inspection -> pose/anchor action -> synthesis -> exact BREP check -> render`

The image can guide the model. It cannot upgrade geometry authority. Exact OCCT/CadQuery
results remain independently authoritative.

Candidate demonstration: the reuse-first cyberdeck workbench, where the model must resolve
one real mechanical interface and drive bounded adapter synthesis while keeping material,
retention, tolerance, fabrication and release claims unresolved unless separately proven.

## Current nonclaims

This staging work does not prove:

- Astra or Fable has successfully operated HS;
- either model is better than the current operator;
- live unseen competence;
- visual-to-geometry correctness;
- physical correctness;
- cost savings;
- physical authority.

No provider request is required to develop or test this layer.
