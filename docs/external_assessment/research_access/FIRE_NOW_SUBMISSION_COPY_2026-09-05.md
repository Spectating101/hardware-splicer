# FIRE NOW — Final Submission Copy (2026-09-07 voice audit)

This file is the **paste-ready firing layer** for the current high-value routes. It intentionally excludes HOLD/dependency routes.

Canonical engineering truth remains in the existing evidence package. Nothing below upgrades pending live-model, fresh physical, or independent-operator evidence.

## Submission voice rule

The portal copy should read like a researcher describing work they actually built, not like an internal control document or a generic grant template.

- Prefer concrete observations, examples, and verbs over stacked abstractions.
- Use first person where it makes the work easier to understand.
- Keep internal words such as `FIRE`, `bounded`, `authority gate`, `evidence-governed`, and `claim boundary` out of outward copy unless they are genuinely the clearest technical term.
- Do not repeat the same conceptual slogan in the title, abstract, takeaways, and bio.
- Preserve method detail and limitations, but do not turn every sentence into a disclaimer.
- Never invent AWS integration, provider endorsement, completed model results, physical proof, collaborators, or institutional sponsorship.

Applicant identity used where relevant:

- **Christopher Ongko**
- **Yuan Ze University**
- **Master of Finance and Accounting**
- **Taiwan**
- **ORCID:** 0009-0007-9339-9098
- **Institutional email:** s1133958@mail.yzu.edu.tw
- Plain positioning: **university-affiliated researcher and engineer building AI-assisted research and engineering systems**

---

# 1. AWS Community Day Taiwan 2026 — Call for Speakers

**Priority:** P0 — submit before 2026-09-07  
**Primary topic:** Agentic AI  
**Language:** English  
**Suggested level:** intermediate / advanced practical session

## Final title

**When an AI Agent Can Touch Hardware: Designing the Checks Between the Model and the Machine**

## One-line session summary

A practical look at the checks I put between an AI agent and real hardware work, and how they behave when the evidence is stale, conflicting, or incomplete.

## Final abstract

When I started letting an AI agent work inside a hardware-engineering environment, model accuracy turned out to be only half the problem. The harder question was what to do with a plausible answer when the evidence behind it was incomplete, stale, or tied to the wrong board revision.

In Hardware-Splicer, the model can inspect sources, plan work, and call engineering tools, but it cannot decide by itself that a component has been identified, that a revision is current, or that a physical action is approved. Those checks live in deterministic project state and a separate human approval step.

This talk walks through the design and the failures that shaped it: partial evidence, conflicting component identity, parser failure, attractive but wrong analogies, and stale revisions. I will show what the system blocks, what it allows to continue, and why I now evaluate agents with metrics such as abstention, recovery, false blocking, and task completion instead of only asking whether the final answer was correct.

Hardware-Splicer is the concrete test case, but the pattern applies to other tool-using agents that can change real state rather than merely answer a question. The goal is not to make the model infallible. It is to keep a model mistake from automatically becoming permission to act.

## Three audience takeaways

1. **Keep the model's proposal separate from system state and permission to act.** A good-looking answer is still only a proposal until the rest of the system can support it.
2. **Tie evidence to the exact object and revision it describes.** Old or conflicting evidence should not quietly survive a change in the underlying work.
3. **Test how the agent fails, not only whether it finishes.** Abstention, recovery, false blocking, and intervention are useful production metrics alongside task completion.

## Speaker bio — preferred

Christopher Ongko is a master's student at Yuan Ze University in Taiwan. He builds AI-assisted research and engineering systems, including Hardware-Splicer, a hardware-engineering environment that keeps model suggestions separate from deterministic checks and human approval. His broader work includes research-data infrastructure and tools for tracking sources, revisions, and reproducibility.

## Short bio

Christopher Ongko is a master's student at Yuan Ze University in Taiwan building AI-assisted research and engineering systems. His current work includes Hardware-Splicer and research-data tools focused on reproducibility and traceable evidence.

## Suggested session flow

1. The problem I ran into when the agent could do more than answer questions.
2. Hardware-Splicer as the concrete system.
3. What stays outside the model: project state, checks, evidence, and approval.
4. Five failure cases and what the system does with them.
5. What I measure now besides answer accuracy.
6. Where the same pattern is useful outside hardware.

## Final claim restraint

Do not claim:

- AWS services are currently part of Hardware-Splicer unless that becomes true;
- a live external model has already passed the frozen corpus;
- fresh physical correctness is already closed;
- the talk presents a universally safe agent.

The talk should feel like an engineering case study with reusable lessons, not an AWS product pitch or a universal safety claim.

---

# 2. OpenAI Researcher Access Program — Hardware-Splicer Evaluation

**Priority:** P1 — FIRE NOW  
**Program fit:** responsible deployment, risk mitigation, human-AI decision making, multimodal/tool-using systems

## Final project title

**Testing Whether Evidence Checks Reduce Unsupported Actions in Tool-Using AI Agents**

## Research question

**When an AI agent can call tools, do explicit evidence, revision, and approval checks reduce unsupported action attempts without making the agent too conservative to be useful?**

## Final project summary

I built Hardware-Splicer to explore a practical problem that appeared once an AI agent could do more than give advice. In hardware work, a plausible answer can quickly turn into a changed artifact, a power-on recommendation, or a proposed physical action even when the component identity, source evidence, or board revision is still uncertain.

The study will compare the same ten adversarial hardware cases in two conditions: a reference tool-using setup and a setup where Hardware-Splicer keeps key checks outside the model. The cases include partial evidence, conflicting component identity, parser/tool failure, an attractive but wrong analogy, and stale evidence from an earlier revision. The reference condition remains advisory/dry-run, so the experiment does not require unsafe physical execution.

The main question is whether those external checks reduce unsupported action attempts while still allowing the agent to make useful progress. I will measure unsupported actions, correct abstention, false blocking, task completion, human intervention, stale-state carryover, and recovery after evidence or tool failure.

The planned core is 300 scored runs: 200 with GPT-5.6 Sol and 100 sensitivity runs with GPT-5.6 Terra. The cases, prompts, evaluator, model settings, and scoring rules will be frozen before scored execution. The intended output is a reproducible benchmark, a trace-level failure taxonomy, and a technical research report suitable for later academic submission.

## Planned use of OpenAI products

OpenAI API models will be the agents being evaluated in the experiment, rather than general writing or coding assistants for the project. GPT-5.6 Sol will be the primary model and GPT-5.6 Terra will provide a lower-cost sensitivity check.

Each model will receive the same cases and the same controlled tool interface. API access will be used for repeated matched runs and for preserving model/tool traces so I can compare behavior when the underlying task is unchanged but the external checks differ. A small unscored pilot will be used only to estimate transport and token costs before the scored protocol is frozen.

## Experimental plan — compact

- 10 frozen adversarial cases.
- 2 matched conditions: reference vs Hardware-Splicer checks enabled.
- GPT-5.6 Sol: 10 repeats per case/condition = 200 scored runs.
- GPT-5.6 Terra: 5 repeats per case/condition = 100 scored runs.
- 300 scored runs total plus a small unscored transport/token pilot.
- Reference actions stay advisory/dry-run when they could otherwise affect hardware.
- Repository, corpus, evaluator, prompts, and model configuration are versioned and frozen before scoring.
- Ambiguous traces receive human adjudication; the evaluated model is not its own only judge.
- Analysis is reported by case as well as across repeats so the 300 runs are not treated as 300 independent problems.

## Why the work matters

Tool-using agents can fail in a way that ordinary answer-quality benchmarks do not capture: a confident but weakly supported answer can become a real change simply because the surrounding system accepts it. This project tests a fairly narrow engineering intervention—keeping a few important checks outside the model—and asks whether that changes agent behavior without making the workflow unusably conservative.

## Expected outputs

- a frozen, reproducible evaluation protocol;
- a versioned benchmark and evaluator;
- model/tool traces where publication policy permits;
- a machine-readable failure taxonomy;
- quantitative and case-level analysis of unsupported actions, abstention, false blocking, intervention, completion, and recovery;
- a technical report / paper draft;
- public reproducibility artifacts that do not expose restricted or confidential material.

## Funding / credit justification

**Working request if the application asks for an amount: US$300 in API credits.**

This is a working budget for the 300-run experiment, a small pilot, retries, and limited validation headroom. Recalculate it immediately before submission using current API pricing and the pilot's measured token/tool-use profile; do not ask for more merely because the program maximum is higher.

## Researcher positioning

I am a master's researcher at Yuan Ze University. My formal degree is in Finance and Accounting, but much of my current research work is technical: I build agentic hardware systems, research-data infrastructure, and research tools that preserve source and revision information. My academic work has also made me fairly conservative about what a result actually supports. Hardware-Splicer gives me a concrete system in which to test that same question for tool-using AI agents.

## Why subsidized access is useful

I am developing the project in a university research setting without a large dedicated AI-compute or API budget. Credits would let me run repeated matched evaluations instead of drawing conclusions from a few demonstrations, while keeping the experiment small enough to complete during my current university affiliation.

## Claim boundary

Do not state that an OpenAI model has already passed this benchmark. Live external-model results remain a planned experiment until executed and archived.

---

# 3. Anthropic External Researcher Access Program — Agent-Control Study

**Priority:** P1 — FIRE NOW  
**Program fit:** AI safety/control, oversight, safe consequential tool use

## Final project title

**Testing Evidence and Authorization Checks for Tool-Using Agents**

## Final research summary

I am interested in a narrow safety question that comes up once an AI agent can call tools: what should happen when the model has a plausible plan but the evidence behind it is incomplete, stale, or contradictory?

I will study this using Hardware-Splicer, a hardware-engineering environment I built where the model can inspect evidence, plan work, and use tools, but several decisions remain outside the model. The system separately tracks component identity, project revision, deterministic engineering checks, and human approval. Hardware is useful here because a weakly supported answer can have an obvious downstream consequence, while the experiment can still keep the reference condition in advisory/dry-run mode.

Claude will be evaluated on a frozen ten-case corpus that includes partial evidence, identity conflict, parser/tool failure, a plausible but wrong analogy, and stale revision evidence. I will compare a reference tool-using condition with the same tasks when the external checks are enabled.

The main outcomes are unsupported action attempts, correct abstention, false blocking, useful task completion, human intervention, stale-state carryover, and recovery after evidence or tool failure. The core design uses 200 Claude Sonnet 5 runs and 100 Claude Opus 5 confirmatory runs. The goal is not to claim a general solution to alignment; it is to test whether a specific control design helps an agent stop at the right boundary without making it unable to do useful work.

## Why this is AI safety research

The safety claim I want to test is deliberately small. When the model says something that the surrounding evidence does not support, does the system prevent that assertion from escalating into an action? And when the evidence is sufficient, can the agent still complete the task without unnecessary blocking?

The experiment therefore looks at:

- unsupported assertions that move toward action;
- whether missing or conflicting evidence causes appropriate abstention;
- whether a revision change invalidates stale state;
- whether deterministic checks provide a useful control layer outside the model;
- how the agent recovers after tool or evidence failures;
- how much useful task completion is lost, if any, when those checks are present.

Hardware is the test environment, not the funding objective. The object of study is tool-using agent behavior under explicit control and review mechanisms.

## Planned use of Claude API

- Claude Sonnet 5 primary: 10 cases × 2 conditions × 10 repeats = 200 scored runs.
- Claude Opus 5 confirmatory: 10 cases × 2 conditions × 5 repeats = 100 scored runs.
- Small unscored pilot before freezing transport/token assumptions.
- Same frozen corpus, evaluator, protocol, and adjudication rules across conditions.
- Preserve tool calls, revision state, outcome labels, failures, retries, and usage metadata where policy permits.

Claude Fable 5.1 is not part of the preregistered core. It may be added later only as a separately declared exploratory run if the core results justify it and the then-current retention/cost terms are acceptable.

## Team description

The study is led by Christopher Ongko, a master's researcher at Yuan Ze University. I developed the existing Hardware-Splicer system and evaluation harness and will run this as a small independent university-affiliated research project. Any faculty, laboratory, collaborator, or institutional sponsorship should be named only if it is actually part of the application.

## Expected outputs

1. matched-condition benchmark results;
2. a case-level failure/control taxonomy;
3. quantitative summaries of unsupported actions, abstention, false blocking, completion, intervention, stale-state carryover, and recovery;
4. versioned evaluation artifacts and traces where provider policy permits;
5. negative and failure results alongside successful cases;
6. a technical report / research-paper draft.

## Strongest one-sentence contribution

**The study asks whether simple checks outside the model can stop weakly supported agent decisions from turning into actions while still leaving the agent useful.**

## Claim boundary

Do not claim that Hardware-Splicer is a general alignment solution, that Claude has already passed the benchmark, or that the experiment proves universal agent safety.

---

# Firing order

1. **AWS Community Day Taiwan CFP** — transcribe and submit first because of the 2026-09-07 deadline.
2. **OpenAI Researcher Access** — map current SurveyMonkey Apply fields, reprice once from the current API catalog/pilot, then submit.
3. **Anthropic External Researcher Access** — map the current official application form fields and submit the safety/control version.

Do not dilute this queue with HOLD routes until these three have receipts.
