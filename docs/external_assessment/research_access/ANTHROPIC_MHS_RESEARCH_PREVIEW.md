# Anthropic Model Hardware Standard (MHS) Research Preview — Capability Packet

**Route state:** VERIFY APPLICANT CLASS → FIRE  
**Verified:** 2026-09-04  
**Official announcement:** https://www.anthropic.com/news/model-hardware-standard-research-preview

## Verified program context

Anthropic announced the Model Hardware Standard research preview on 2026-08-27 as a shared specification for AI agents to operate programmable physical devices. The first group includes scientific research labs and advanced manufacturers. Anthropic states that it is inviting additional stakeholders across science, robotics, electronics and manufacturing to help test MHS, build safety evaluations and develop best practices before the standard is open sourced.

Anthropic explicitly states that:

- MHS works with devices that have a **programmable interface**;
- the standard is model-agnostic;
- agent harnesses can access MHS through standard protocols such as MCP;
- a research-preview goal is to build additional **physical-safety evaluations** and deployment guidance.

The public page does not establish that an individual master's student is automatically an accepted applicant class. If the interest form requires a laboratory, institutional stakeholder or organization, route through an appropriate YZU faculty/lab sponsor rather than misrepresenting the applicant.

## Positioning rule

Do **not** claim that Hardware-Splicer implements MHS.

Preferred relationship:

> **Hardware-Splicer is an existing independent agentic hardware-engineering environment that could serve as an evaluation/control harness around an MHS-enabled programmable device.**

## One-line value to Anthropic

> Hardware-Splicer can contribute an adversarial safety-evaluation harness for testing whether an MHS-mediated physical agent remains below evidence and authorization boundaries when physical evidence is stale, ambiguous, conflicting or incomplete.

## 150-word capability summary

Hardware-Splicer is an existing model-independent environment for bounded agentic hardware engineering. A general-purpose agent can reason and use a canonical MCP/API engineering surface, while deterministic engineering constraints, exact project/revision state, provenance-bearing evidence and scoped human authorization remain independently authoritative. The repository includes a frozen adversarial corpus and trace/replay infrastructure designed to expose failures involving partial evidence, component-identity conflict, tool failure, plausible wrong analogy and stale revisions. If admitted to the MHS research preview, the project would connect a concrete programmable physical device through the MHS interface and use Hardware-Splicer as an independent evaluation harness around that control surface. The proposed contribution is not another device driver alone: it is a reproducible physical-agent safety evaluation focused on evidence sufficiency, authority escalation, failure recovery and the boundary between model reasoning and permitted physical action.

## Proposed preview contribution

### Work package 1 — integration

Connect one **real programmable device** through the preview MHS interface while preserving Hardware-Splicer's existing revision/evidence/authority state.

Required before submission:

- `[DEVICE NAME/MODEL]`
- `[PROGRAMMABLE INTERFACE: API / SDK / SERIAL / OTHER]`
- `[SAFE PHYSICAL ACTIONS AVAILABLE TO AGENT]`
- `[CURRENT HARDWARE ACCESS LOCATION]`

### Work package 2 — adversarial safety evaluation

Adapt the existing evidence-boundary test methodology to physical actions:

- incomplete evidence;
- stale revision state;
- conflicting component/device identity;
- tool/driver failure;
- plausible but physically wrong inference;
- attempted action beyond current authorization scope.

### Work package 3 — failure/recovery analysis

Measure whether the agent:

- blocks or asks for more evidence;
- attempts unauthorized action;
- recovers safely after device/tool failure;
- preserves stale evidence/authority incorrectly;
- requires human intervention;
- completes useful bounded work.

### Work package 4 — reusable output

Return:

- versioned test cases;
- device/integration notes where permitted;
- safety findings;
- failure taxonomy;
- recommended best practices for evidence/authorization boundaries around MHS-mediated physical action.

## Existing project evidence relevant to MHS

Already supported by the canonical package:

- model-independent MCP engineering surface;
- deterministic evidence/authority separation;
- exact project/revision state;
- explicit real-vs-simulated evidence treatment;
- frozen adversarial test corpus;
- external-agent trace/replay infrastructure.

Still pending and therefore not to be overstated:

- live external-model corpus competence;
- fresh revision-bound SPI physical correctness;
- independent operator usability;
- any MHS integration or MHS-specific result.

## Why this is a credible preview contribution

The project already asks a question adjacent to Anthropic's stated physical-safety concern:

> **What evidence and authority should be required before an AI-generated answer is allowed to become a physical action?**

MHS standardizes how an agent can communicate with programmable equipment. Hardware-Splicer can contribute a complementary evaluation of **when** model-derived intent should be allowed to cross that interface.

## Applicant identity — claim-safe framing

> University-affiliated researcher developing an existing physical/agentic engineering system with deterministic evidence and authority controls, seeking to contribute a concrete programmable-device integration and a reusable safety-evaluation protocol to the MHS preview.

Do not call the applicant a manufacturing lab if that is not true.

## Submission blocker

This application should **not** be fired with `[DEVICE NAME/MODEL]` unresolved.

A credible MHS submission needs a real programmable physical surface, not only a software architecture diagram.

## Pre-submit checklist

- [ ] inspect live MHS interest form and record exact applicant-class fields;
- [ ] determine whether self-application is accepted or faculty/lab routing is needed;
- [ ] name concrete programmable device and interface;
- [ ] confirm physical access to device during proposed preview period;
- [ ] define bounded safe actions available to agent;
- [ ] link canonical architecture/evidence package;
- [ ] avoid claiming prior MHS implementation;
- [ ] avoid claiming pending physical/live-model results;
- [ ] preserve any submission/acceptance receipt.
