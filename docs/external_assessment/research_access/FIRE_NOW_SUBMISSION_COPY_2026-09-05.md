# FIRE NOW — Final Submission Copy (2026-09-05)

This file is the **paste-ready firing layer** for the current high-value routes. It intentionally excludes HOLD/dependency routes.

Canonical engineering truth remains in the existing evidence package. Nothing below upgrades pending live-model, fresh physical, or independent-operator evidence.

Applicant identity used where relevant:

- **Christopher Ongko**
- **Yuan Ze University**
- **Master of Finance and Accounting**
- **Taiwan**
- **ORCID:** 0009-0007-9339-9098
- **Institutional email:** s1133958@mail.yzu.edu.tw
- Positioning: **independent university-affiliated researcher and engineer working on evidence-governed agentic systems**

---

# 1. AWS Community Day Taiwan 2026 — Call for Speakers

**Priority:** P0 — submit before 2026-09-07  
**Primary topic:** Agentic AI  
**Language:** English  
**Suggested level:** intermediate / advanced practical session

## Final title

**From Model Output to Physical Action: Evidence and Authority Gates for Agentic AI**

## One-line session summary

A practical systems pattern for keeping tool-using AI agents useful without letting unsupported model confidence silently become consequential action.

## Final abstract

Agentic AI becomes a different engineering problem once model output can modify state, operate tools, or trigger physical work. In those settings, the most important failure is not simply a wrong answer: it is a plausible answer acquiring authority it has not earned.

This session presents a practical systems pattern developed through Hardware-Splicer, an agentic hardware-engineering environment built around a strict separation between model reasoning and independently authoritative state. The agent can inspect evidence, reason, propose changes, and use engineering tools, while deterministic constraints, exact revision state, provenance-bearing evidence, and scoped human authorization remain outside the model.

Using adversarial hardware cases involving partial evidence, component-identity conflict, tool failure, plausible wrong analogy, and stale revisions, the talk shows how to design for failure instead of assuming perfect model behavior. The focus is on reusable production principles: fail closed on unresolved evidence, invalidate authority when revisions change, distinguish reasoning from verified state, preserve traceability, and measure abstention, recovery, false blocking, intervention, and useful task completion—not only successful answers.

Hardware-Splicer is the concrete case study, but the architecture generalizes to other consequential agent workflows where an AI system can act rather than merely advise.

## Three audience takeaways

1. **Reasoning and authority should be separate system concepts.** A model proposal should not automatically become verified state or permission to act.
2. **Evidence must be bound to identity and revision.** Stale, conflicting, or incomplete evidence should invalidate authority rather than silently carry forward.
3. **Production agent evaluation needs failure metrics.** Abstention, recovery, false blocking, intervention, and unauthorized action attempts matter as much as task completion.

## Speaker bio — preferred

Christopher Ongko is a master's researcher at Yuan Ze University working on evidence-governed agentic systems, research-data infrastructure, and empirical research. His current technical work includes Hardware-Splicer, a model-independent environment for bounded AI-assisted hardware engineering, and research systems focused on provenance and reproducibility. His recurring research interest is how AI systems can remain useful while maintaining explicit boundaries between model inference, evidence, verified state, and consequential authority.

## Short bio

Christopher Ongko is a Yuan Ze University master's researcher building evidence-governed agentic and research-data systems. His work focuses on keeping model inference, evidence, revision state, and consequential authority explicitly separated in real AI workflows.

## Suggested session flow

1. Why tool-using agents create a new failure boundary.
2. Hardware-Splicer as a concrete case study.
3. Four-layer pattern: model reasoning → deterministic constraints → provenance/revision evidence → human authority.
4. Adversarial cases and what goes wrong.
5. Metrics for abstention, recovery, false blocking, intervention, and useful completion.
6. Generalization to production agentic systems beyond hardware.

## Final claim restraint

Do not claim:

- AWS services are currently part of Hardware-Splicer unless that becomes true;
- a live external model has already passed the frozen corpus;
- fresh physical correctness is already closed;
- the talk presents a universally safe agent.

The value proposition is **practical agentic-AI systems design**, not an AWS product pitch.

---

# 2. OpenAI Researcher Access Program — Hardware-Splicer Evaluation

**Priority:** P1 — FIRE NOW  
**Program fit:** responsible deployment, risk mitigation, human-AI decision making, multimodal/tool-using systems

## Final project title

**Evidence- and Authority-Constrained Agent Control Under Consequential Hardware Tool Use**

## Research question

**Do evidence gating, deterministic engineering constraints, and explicit authorization reduce unsupported consequential actions by tool-using AI agents without eliminating useful task completion?**

## Final project summary

Most agent evaluations ask whether a model can produce a correct answer. This project asks a different deployment question: **when should a model-generated answer be allowed to acquire authority to act?**

Hardware engineering provides a consequential test environment because a plausible but unsupported model response can become a fabricated artifact, power-on decision, or released change before component identity, evidence provenance, revision state, or physical behavior has actually been established.

I will evaluate this problem using Hardware-Splicer, an existing model-independent agentic hardware-engineering environment that keeps deterministic constraints, provenance-bearing evidence, exact project/revision state, and scoped human authorization outside the model. A frozen ten-case adversarial corpus includes partial evidence, identity conflicts, parser/tool failure, plausible wrong analogies, and stale-revision evidence.

The study uses matched reference and constrained conditions. Consequential reference actions remain advisory/dry-run rather than being physically executed. The primary outcomes are unsupported consequential-action attempts, correct abstention, false blocking, useful task completion, human intervention, stale-authority carryover, and recovery after evidence/tool failure.

The planned core consists of 300 scored runs: 200 runs using GPT-5.6 Sol and 100 sensitivity runs using GPT-5.6 Terra, with protocol, corpus, evaluator, prompts, model configuration, and adjudication rules frozen before scored execution. The intended output is a reproducible benchmark, trace-level failure taxonomy, and technical research report suitable for later academic submission.

## Planned use of OpenAI products

OpenAI API models are the **experimental agents under evaluation**, not generic writing or coding assistants for the project. GPT-5.6 Sol will serve as the primary model and GPT-5.6 Terra as a lower-cost sensitivity model. Each model will receive the same bounded engineering cases and operate through controlled MCP/tool interfaces.

API access will support repeated matched-condition runs, preservation of model/tool traces, and sensitivity analysis while keeping the underlying corpus fixed after the experiment begins. The design specifically measures whether external evidence/authority constraints change behavior under incomplete, stale, conflicting, or tool-failure conditions.

## Experimental plan — compact

- 10 frozen adversarial cases.
- 2 matched conditions: reference vs Hardware-Splicer constrained.
- GPT-5.6 Sol: 10 repeats per case/condition = 200 scored runs.
- GPT-5.6 Terra: 5 repeats per case/condition = 100 scored runs.
- 300 scored runs total plus a small unscored transport/token pilot.
- Consequential reference actions scored in advisory/dry-run mode.
- Exact repository/corpus/evaluator/model/prompt revisions preserved.
- Human adjudication for ambiguous traces; evaluated model is not its own sole judge.
- Case-level and cluster-aware analysis so stochastic repeats are not treated as 300 independent cases.

## Why the work matters

Tool-using agents increasingly operate in environments where model output can affect real state. A system can therefore fail even when its model is generally capable: unsupported confidence may silently become action authority. The project tests whether a narrow architectural intervention—keeping evidence, revision state, deterministic constraints, and authorization independently authoritative—reduces that failure mode while preserving useful agent progress.

## Expected outputs

- reproducible frozen evaluation protocol;
- versioned benchmark and evaluator;
- provider/model run traces where publication policy permits;
- machine-readable failure/control taxonomy;
- quantitative and case-level analysis of unsupported actions, abstention, false blocking, intervention, completion, and recovery;
- technical research report / paper draft;
- public reproducibility artifacts that do not expose restricted or confidential material.

## Funding / credit justification

**Working request if the application asks for an amount: US$300 in API credits.**

The request is deliberately below the program maximum. It is intended to cover the 300-run matched-condition experiment plus transport pilots, retries, and limited validation/ablation headroom. Recalculate immediately before submission against current model pricing and the pilot's measured token/tool-use profile.

## Researcher positioning

I am a university-affiliated master's researcher at Yuan Ze University working on evidence-governed agentic systems and empirical research. My formal degree is in Finance and Accounting; my current research/engineering work is interdisciplinary and includes agentic hardware systems, reproducible research-data infrastructure, and evidence-grounded research tooling. Existing academic work provides experience in empirical question formulation, evidence construction, and bounded claims, while Hardware-Splicer supplies the concrete experimental system for this study.

## Why subsidized access is useful

The project is independently developed in a university research context without a large institutional AI-compute budget. Subsidized API access would make it practical to run repeated matched-condition evaluations rather than relying on anecdotal one-off demonstrations, while keeping the study small enough to complete within the current university affiliation window.

## Claim boundary

Do not state that an OpenAI model has already passed this benchmark. Live external-model results remain a planned experiment until executed and archived.

---

# 3. Anthropic External Researcher Access Program — Agent-Control Study

**Priority:** P1 — FIRE NOW  
**Program fit:** AI safety/control, oversight, safe consequential tool use, authority gating

## Final project title

**Evidence- and Authority-Constrained Agent Control Under Consequential Tool Use**

## Final research summary

As AI agents gain tool access, the safety question is no longer only whether a model can reason correctly; it is also **what its reasoning is permitted to authorize**. In consequential environments, unsupported model confidence can become a real action even when the underlying evidence is stale, ambiguous, conflicting, or incomplete.

I propose a controlled evaluation using Hardware-Splicer, an existing model-independent hardware-engineering environment that separates semantic model reasoning from deterministic engineering state, provenance-bearing evidence, exact revision state, and scoped human authorization. The engineering domain is the test environment; the research question is agent control.

Claude will be evaluated on a frozen ten-case adversarial corpus covering partial evidence, component-identity conflict, tool/parser failure, plausible wrong analogies, and stale revisions. The study compares matched reference and evidence/authority-constrained conditions while keeping provider safety controls intact. Consequential reference actions remain advisory/dry-run rather than physically executed.

Primary outcomes include unsupported consequential-action attempts, correct abstention/blocking, false blocking, useful task completion, human intervention, stale-authority carryover, and recovery after tool/evidence failure. The core design uses 200 Claude Sonnet 5 scored runs and 100 Claude Opus 5 confirmatory runs. The intended contribution is an auditable safe-tool-use/control evaluation of whether explicit evidence and authority boundaries reduce unsupported action escalation without destroying useful agent behavior.

## Why this is AI safety research

The project is not asking Anthropic to fund generic hardware-product development. It tests a control intervention for tool-using agents:

- when unsupported assertions escalate toward action;
- whether explicit evidence gates improve safe abstention;
- whether revision changes invalidate stale authority;
- whether deterministic constraints preserve a meaningful control boundary outside the model;
- how the agent recovers after evidence/tool conflicts;
- whether useful task progress survives the additional controls.

The physical-engineering domain provides consequential semantics, but the primary object of study is **agent control and oversight**.

## Planned use of Claude API

- Claude Sonnet 5 primary: 10 cases × 2 conditions × 10 repeats = 200 scored runs.
- Claude Opus 5 confirmatory: 10 cases × 2 conditions × 5 repeats = 100 scored runs.
- Small unscored pilot before freezing transport/token assumptions.
- Same frozen corpus, evaluator, protocol, and adjudication rules across conditions.
- Full evidence state, MCP/tool calls, revision state, provider/model configuration, outcome labels, failures, retries, and usage metadata preserved where policy permits.

Claude Fable 5.1 should **not** be part of the preregistered core. It may be added later only as a separately declared exploratory escalation if the core results justify it and the then-current data-retention/cost terms are acceptable.

## Team description

The project is led by Christopher Ongko, a university-affiliated master's researcher at Yuan Ze University. It is a bounded independent research study using an existing agentic hardware-engineering platform and evaluation harness. Faculty/institutional context can be identified where relevant, but no laboratory, collaborator, or institutional sponsorship should be implied unless it is actually part of the submitted application.

## Expected outputs

1. controlled matched-condition benchmark results;
2. case-level agent-control/failure taxonomy;
3. quantitative summaries of unsupported actions, abstention, false blocking, useful completion, intervention, stale-authority carryover, and recovery;
4. versioned evaluation artifacts and traces where provider policy permits;
5. explicit negative/failure results rather than success-only reporting;
6. technical report / research-paper draft.

## Strongest one-sentence contribution

**This study tests whether keeping evidence and action authority independently authoritative can prevent a tool-using agent's unsupported confidence from silently becoming consequential action.**

## Claim boundary

Do not claim that Hardware-Splicer is a general alignment solution, that Claude has already passed the benchmark, or that the experiment proves universal agent safety.

---

# Firing order

1. **AWS Community Day Taiwan CFP** — transcribe and submit first because of the 2026-09-07 deadline.
2. **OpenAI Researcher Access** — map current SurveyMonkey Apply fields, reprice once from the current API catalog/pilot, then submit.
3. **Anthropic External Researcher Access** — map the current official application form fields and submit the safety/control version.

Do not dilute this queue with HOLD routes until these three have receipts.
