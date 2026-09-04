# OpenAI Researcher Access Program — Submission Packet

**Route state:** FIRE  
**Verified:** 2026-09-04  
**Official program:** https://openai.com/form/researcher-access-program/  
**FAQ:** https://help.openai.com/en/articles/10139500

## Verified mechanics

OpenAI currently states that:

- researchers with an active affiliation to an academic institution or other research organization are eligible;
- applicants must be based in a country supported by the OpenAI API;
- early-stage researchers and those with limited financial/institutional resources are encouraged;
- applicants may request up to **US$1,000 in API credits**;
- credits are valid for 12 months;
- applications are reviewed in March, June, September and December;
- the application asks about the **research question** and **planned use of OpenAI products**.

This file prepares the research content. Re-check the live SurveyMonkey Apply form immediately before submission for exact required fields and character limits.

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

The study will use a frozen ten-case adversarial SPI-flash corpus covering source-order perturbations, partial evidence, component-identity conflict, parser/tool failure, plausible wrong analogy and stale-revision evidence. I will compare a reference agent condition with a Hardware-Splicer-constrained condition using the same model family/configuration wherever possible. Outcomes will include unsupported consequential-action rate, correct abstention/blocking, false blocking, task completion, human intervention and failure-recovery behavior. Complete model/tool traces and exact repository/corpus revisions will be preserved for reproducibility.

The project is intentionally scoped as an 8–12 week university-affiliated evaluation. Current repository evidence establishes the deterministic software/MCP infrastructure and test harness; live external-model results will be reported only after the actual provider runs are executed. The expected output is a reproducible benchmark, trace set and technical research report suitable for later academic submission.

## Planned use of OpenAI products — concise

OpenAI API models would serve as the general-purpose agent under evaluation. The models would receive the same bounded hardware-engineering cases and operate through controlled tool/MCP interfaces. API credits would support repeated runs across the frozen corpus, model/configuration comparisons where useful, and preservation of model/tool traces for reproducible analysis. OpenAI products are not being requested as generic writing or coding assistance; they are the experimental agent whose behavior under evidence/authority constraints is being measured.

## Planned use — detailed

OpenAI API access would be used to execute the frozen adversarial corpus through the Hardware-Splicer external-agent harness. Each run would preserve model inputs/outputs, MCP calls and responses, project/revision state, adjudication, failures and usage/cost metadata. The principal comparison is between a reference tool-using agent and the same or closely matched model operating inside Hardware-Splicer's evidence/authority constraints. Credits would enable enough repeated runs to distinguish one-off stochastic behavior from persistent patterns without changing the underlying cases after results are observed.

No application should claim that an OpenAI model has already passed the corpus. At current repository truth state, live external-model competence remains pending.

## Why the project fits the program

The project directly addresses themes OpenAI currently identifies as relevant to the program, including:

- responsible deployment and risk mitigation;
- human-AI collaboration in decision making;
- reliable safety properties under adversarial inputs;
- multimodal/specialized-domain model behavior;
- measurement of model behavior in consequential contexts.

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

Before submission fill:

- `[START DATE]`
- `[END DATE]`
- `[MODEL(S)]`
- `[RUNS PER CASE]`
- `[ESTIMATED TOTAL API COST]`

## API budget method

Budget from the experiment, not from the program maximum:

`cases × conditions × repeated runs × estimated input/output tokens × model price`

Add a modest allowance for failed/replayed runs and analysis validation. Do not request US$1,000 merely because US$1,000 is available if the benchmark reasonably costs less.

## Application evidence links

Prefer only a small number of clean links:

1. public repository;
2. external-assessment package / project identity;
3. claims and nonclaims;
4. research protocol or evaluation artifact;
5. one relevant paper/CV link if the form permits.

Do not dump the entire portfolio.

## Claim-safe researcher positioning

> University-affiliated master's researcher working at the intersection of empirical evidence discipline, agentic AI systems and consequential engineering workflows. Hardware-Splicer is the primary experimental platform; existing academic work demonstrates experience formulating empirical questions, constructing evidence and maintaining bounded claims.

Do not represent the formal degree as computer science. The program's public eligibility is based on active research affiliation, not a CS degree.

## Pre-submit checklist

- [ ] institutional affiliation still active and correctly entered;
- [ ] supported-country requirement re-checked;
- [ ] exact SurveyMonkey fields copied into this packet if they changed;
- [ ] 8–12 week dates finalized;
- [ ] API model and budget finalized;
- [ ] no live-model results claimed before execution;
- [ ] publication/sharing policy reviewed;
- [ ] only non-confidential data/evidence included;
- [ ] submission receipt preserved in Gauntlet/Blowback.
