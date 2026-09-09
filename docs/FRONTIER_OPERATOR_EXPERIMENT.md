# Frontier Operator Experiment — zero-spend staging

## Purpose

Prepare Hardware-Splicer to test a frontier multimodal/agent operator without turning
model novelty into an automatic API bill or weakening HS's evidence hierarchy.

This lane is **exploratory only**. The frozen external-proof core remains separate.

## Resource boundary for this experiment

The practical live target is now **GPT-6 Astra through ChatGPT-authenticated Codex**.
The usable resource is the existing Work/Codex allowance, not a separate provider API
budget.

This distinction is mandatory:

- signing in to Codex with ChatGPT consumes the plan's Work/Codex allowance;
- running `gpt-6-astra` through an OpenAI API key uses separate API billing;
- therefore the OpenAI Responses request template in this branch is compatibility and
  protocol-staging code only, **not the intended live execution path**;
- no script in this branch should silently convert a Codex experiment into an API call.

Current OpenAI guidance also requires Codex CLI 0.153.0 or newer for Astra.

### Fable status

`claude-fable-5` remains only as a dormant, zero-network compatibility adapter and trace
normalizer. There is **no planned live Fable run**, no Anthropic spending allocation, and
no requirement to obtain Anthropic credentials. Keeping the adapter costs nothing and
preserves the option to compare providers later if an external credit or research-access
budget appears.

## Current provider targets

Verified against provider documentation on 2026-09-10:

| Provider | API model id | Experiment status | Remote MCP | Image input |
|---|---|---|---|---|
| OpenAI | `gpt-6-astra` | **live candidate via ChatGPT-authenticated Codex** | yes | yes |
| Anthropic | `claude-fable-5` | **dormant adapter only; no live budget** | yes | yes |

Provider references:

- OpenAI Astra model page: https://developers.openai.com/api/docs/models/gpt-6-astra
- OpenAI Work/Codex usage: https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- OpenAI Codex plan sign-in: https://help.openai.com/en/articles/11369540/
- Anthropic MCP connector: https://docs.anthropic.com/en/docs/agents-and-tools/mcp-connector

Do not infer future aliases from product naming. The current public Anthropic API target
used by the dormant adapter is `claude-fable-5`.

## Why the model belongs above HS rather than inside its truth core

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

- provider request-shape metadata for the exploratory adapters;
- conservative API text-token estimates, useful only as a warning for accidental API use;
- explicit paid-API policy validation;
- OpenAI Responses/MCP request templates;
- dormant Anthropic Messages/MCP request templates;
- Anthropic MCP trace normalization into the existing HS audit shape.

`scripts/plan_frontier_operator_experiment.py` also performs no network I/O and does not
read provider credentials.

The API cost planner is deliberately retained as a **tripwire**: if somebody later tries
to run the API path, the branch can show that this would be separate billable usage.
Those dollar estimates do not describe the user's Codex allowance.

## Intended Astra live path

A later Astra experiment should run from Codex while Codex is authenticated with the
user's ChatGPT account and Astra is available in that Codex surface.

Preflight requirements:

1. Codex CLI >= 0.153.0;
2. authenticated using ChatGPT, not an API key;
3. `gpt-6-astra` visible/usable in Codex;
4. HS's canonical MCP server registered with Codex;
5. only the four canonical HS gateway tools exposed for the experiment;
6. one frozen case first;
7. inspect Work/Codex usage after that case before expanding;
8. no automatic fallback to Responses API if Codex/Astra is unavailable.

The intended first live comparison is therefore **current HS operator vs Astra-in-Codex**,
not a three-provider benchmark.

## API live-run policy remains fail-closed

Any future paid API runner must call `validate_live_policy` before provider I/O and
preserve the explicit budget/charge acknowledgement. That mechanism exists to prevent
accidental API spend; it is not the preferred Astra path for this experiment.

## Stage 1 — one frozen Astra case

Once the Codex path is ready, start with a single frozen SPI case. Compare against the
existing HS baseline on:

- completion;
- hard-truth contract failures;
- tool-path efficiency;
- evidence identity;
- authority discipline;
- unresolved-state discipline;
- equivalent-case trace structure where applicable.

Do not immediately fire the ten-case corpus. Astra can consume the shared Codex allowance
substantially faster than lower-cost models, so expansion should follow observed usage.

## Stage 2 — visual geometry loop

The more interesting later experiment is not prettier rendering. It is whether Astra can
use render feedback to steer HS's exact engineering substrate:

`candidate -> render -> visual inspection -> pose/anchor action -> synthesis -> exact BREP check -> render`

The image can guide the model. It cannot upgrade geometry authority. Exact OCCT/CadQuery
results remain independently authoritative.

Candidate demonstration: the reuse-first cyberdeck workbench, where Astra must resolve one
real mechanical interface and drive bounded adapter synthesis while keeping material,
retention, tolerance, fabrication and release claims unresolved unless separately proven.

## Current nonclaims

This staging work does not prove:

- Astra has successfully operated HS;
- Astra is better than the current operator;
- Fable has been or will be run;
- live unseen competence;
- visual-to-geometry correctness;
- physical correctness;
- cost savings;
- physical authority.

No provider request is required to develop or test this layer.
