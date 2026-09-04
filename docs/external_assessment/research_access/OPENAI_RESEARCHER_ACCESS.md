# OpenAI Researcher Access Program — Submission Packet

**Route state:** FIRE  
**Verified:** 2026-09-04  
**Official program:** https://openai.com/form/researcher-access-program/  
**Program page:** https://grants.openai.com/prog/openai_researcher_access_program/  
**FAQ:** https://help.openai.com/en/articles/10139500

## Verified mechanics

OpenAI currently states that:

- researchers with an active affiliation to an academic institution or other research organization are eligible;
- applicants must be based in a country supported by the OpenAI API;
- early-stage researchers and those with limited financial/institutional resources are encouraged;
- applicants may request up to **US$1,000 in API credits**;
- credits are valid for 12 months and may be applied to publicly available models;
- applications are reviewed in March, June, September and December;
- the application asks about the **research question** and **planned use of OpenAI products**;
- accepted applicants should expect the grant to be credited only after the review/award process, so the proposal should not depend on immediate funding.

This file prepares the research content. Re-check the live application immediately before submission for exact required fields and character limits.

## Recommended project title

**Evidence- and Authority-Constrained Agent Control Under Consequential Hardware Tool Use**

Alternative shorter title:

**Separating Model Reasoning from Physical Authority in Agentic Hardware Engineering**

## Research question — concise

> Do evidence gating, deterministic engineering constraints and explicit authorization reduce unsupported consequential actions by general-purpose tool-using AI agents without eliminating useful task completion?

## 150-word project summary

General-purpose AI agents are increasingly capable of operating tools, but hardware workflows create a distinct deployment risk: a plausible model response can cross into fabrication, power-on or release decisions before exact component identity, evidence provenance, revision state or physical behavior has been established. I propose a bounded evaluation using Hardware-Splicer, a model-independent hardware-engineering environment that keeps deterministic constraints, provenance-bearing evidence and scoped authorization outside the model. The study will compare agent behavior across a frozen adversarial SPI-flash corpus containing partial evidence, identity conflicts, tool failures, analogy traps and stale revisions. Primary outcomes will include unsupported consequential-action rate, correct abstention, false blocking, task completion and human intervention. The aim is not to claim an infallible AI engineer, but to test whether useful agentic work can be preserved while preventing unsupported model confidence from automatically acquiring physical authority.

## 300-word project summary

General-purpose AI agents increasingly operate tools rather than merely generate text. In hardware engineering, this creates a deployment problem that ordinary answer-quality benchmarks do not capture: a fluent model can propose a design or next action before exact component identity, evidence provenance, revision state or physical behavior is actually known. If such output is promoted directly into fabrication, power-on or release decisions, model confidence can acquire physical consequences without an explicit evidence boundary.

I propose to evaluate whether an evidence- and authority-constrained systems architecture changes this behavior. Hardware-Splicer is an existing model-independent environment in which an AI agent may reason, inspect evidence, propose changes and use engineering tools through a canonical MCP/API surface, while deterministic engineering constraints, exact project/revision state, provenance-bearing evidence and scoped human authorization remain independently authoritative.

The study will use a frozen ten-case adversarial SPI-flash corpus covering source-order perturbations, partial evidence, component-identity conflict, parser/tool failure, plausible wrong analogy and stale-revision evidence. I will compare a reference agent condition with a Hardware-Splicer-constrained condition using matched model/configuration and semantically equivalent task evidence. Consequential actions in the reference condition will be scored from proposed/requested actions rather than physically executed. Outcomes will include unsupported consequential-action rate, correct abstention/blocking, false blocking, useful task completion, human intervention and failure-recovery behavior. Complete model/tool traces and exact repository/corpus revisions will be preserved for reproducibility.

The project is intentionally scoped as an 8–12 week university-affiliated evaluation. Current repository evidence establishes the deterministic software/MCP infrastructure and test harness; live external-model results will be reported only after the actual provider runs are executed. The expected output is a reproducible benchmark, trace set and technical research report suitable for later academic submission.

## Planned use of OpenAI products — concise

OpenAI API models would serve as the general-purpose agents under evaluation. The primary experiment will run the same frozen hardware-engineering cases under matched reference and Hardware-Splicer-constrained conditions, preserving model/tool traces, evidence state and adjudication. Credits are requested for repeated agent executions and a smaller model-sensitivity tranche—not for generic writing, coding or product hosting.

## Planned use — detailed

OpenAI API access would execute the frozen adversarial corpus through the Hardware-Splicer external-agent harness. Each scored run preserves model inputs/outputs, MCP calls and responses, project/revision state, adjudication, failures and usage/cost metadata. The treatment comparison is between a dry-run reference tool-using condition and the matched agent operating inside Hardware-Splicer's evidence/authority constraints. The reference condition does not physically execute consequential actions; requested actions are scored against the frozen rubric.

The current default design is:

- **Primary:** `gpt-5.6-sol` — `10 cases × 2 conditions × 10 repeats = 200 scored runs`;
- **Sensitivity:** `gpt-5.6-terra` — `10 cases × 2 conditions × 5 repeats = 100 scored runs`;
- total: **300 scored runs**, plus a small unscored transport/token pilot.

If the current public model catalog changes before execution, use the closest current publicly available agentic models while preserving the matched-condition design and record the exact API-returned model IDs/snapshots.

No application should claim that an OpenAI model has already passed the corpus. At current repository truth state, live external-model competence remains pending.

## Why the project fits the program

The project directly addresses themes OpenAI currently identifies as relevant to the program, including:

- responsible deployment and risk mitigation;
- safety properties under adversarial inputs;
- measurement of model behavior in consequential contexts;
- human oversight of tool-using systems;
- understanding when model outputs should and should not acquire action authority.

The proposal's distinctive contribution is a concrete physical-engineering environment in which reasoning quality can be separated from evidence state and action authority.

## Expected outputs

1. frozen benchmark definition and versioned evaluation harness;
2. provider/model run traces where publication is permitted;
3. case-level failure taxonomy;
4. quantitative summary of unsupported actions, abstention, false blocking, completion and intervention;
5. technical report / extended abstract / paper draft;
6. public reproducibility artifacts that do not expose restricted provider data or confidential third-party information.

## Proposed project window

Use a bounded **8–12 week** YZU-affiliated study rather than a year-long promise.

Recommended operational window if submitted in the September 2026 review cycle:

- **start:** after award/credit activation, no earlier than October 2026;
- **core execution:** 8–12 weeks;
- **artifact/report completion:** within the 12-month credit validity period.

Do not hard-code exact dates until the application/award timing is known.

## API budget — working default

Pricing snapshot used for planning on 2026-09-04:

- `gpt-5.6-sol`: US$4 / MTok input, US$20 / MTok output;
- `gpt-5.6-terra`: US$2 / MTok input, US$12 / MTok output.

Official model catalog/pricing: https://developers.openai.com/api/docs/models

A deliberately conservative first budget assumes **50k input + 10k output tokens per scored run**:

- Sol primary, 200 runs: about **US$80**;
- Terra sensitivity, 100 runs: about **US$22**;
- scored-run subtotal: about **US$102**.

A heavier **100k input + 20k output** assumption approximately doubles that subtotal to **US$204**. Add pilot runs, retries and validation headroom.

### Recommended request

If the application asks for a specific credit amount, use **US$300** as the current defensible request unless the live pilot materially changes token use.

That is intentionally below the US$1,000 maximum while leaving enough room for:

- 300 scored runs;
- transport/debugging pilots;
- failed/replayed runs;
- limited extra sensitivity analysis.

Recalculate against current pricing immediately before submission. Do not request US$1,000 merely because it is the maximum.

## Application evidence links

Prefer only a small number of clean links:

1. public repository;
2. external-assessment package / project identity;
3. claims and nonclaims;
4. frozen research protocol;
5. one relevant paper/CV link if the form permits.

Do not dump the entire portfolio.

## Claim-safe researcher positioning

Preferred wording:

> Master's researcher at Yuan Ze University working on empirical evidence discipline, agentic AI systems and consequential engineering workflows. Hardware-Splicer is the primary experimental platform; existing academic work demonstrates experience formulating empirical questions, constructing evidence and maintaining bounded claims.

If the form asks for department/degree, answer it exactly. Do not imply a computer-science degree or lab affiliation that does not exist. The public program eligibility is based on active research affiliation, not a CS degree.

## Pre-submit checklist

- [ ] institutional affiliation still active and correctly entered;
- [ ] supported-country requirement re-checked;
- [ ] exact live application fields/limits captured;
- [ ] current model availability and pricing re-checked;
- [ ] US$300 working request re-priced against the pilot if an amount is requested;
- [ ] no live-model results claimed before execution;
- [ ] publication/sharing policy reviewed;
- [ ] only non-confidential data/evidence included;
- [ ] submission receipt preserved in Gauntlet/Blowback.
