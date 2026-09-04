# Anthropic External Researcher Access Program — Submission Packet

**Route state:** FIRE  
**Verified:** 2026-09-04  
**Official program:** https://support.claude.com/en/articles/9125743-what-is-the-external-researcher-access-program

## Verified mechanics

Anthropic currently states that the External Researcher Access Program:

- supports researchers working on **high-priority AI safety and alignment topics**;
- provides free API credits for the standard Claude model suite;
- ordinarily awards **US$1,000 in API credits** to successful applicants, with rare higher awards possible;
- evaluates submissions on the **first Monday of each month**;
- asks applicants for information about their **team and research topic**;
- does not grant access to nonpublic models and does not waive Anthropic's Usage Policy;
- may not individually respond to unsuccessful applicants because of application volume.

This route is narrower than generic research-credit programs. The application must present a genuine AI-control/safety experiment, not a hardware-product funding request.

## Recommended project title

**Evidence- and Authority-Constrained Agent Control Under Consequential Tool Use**

Alternative:

**Keeping Tool-Using AI Agents Below the Physical-Authority Boundary**

## Safety research question

> Can explicit evidence gates, deterministic constraints and scoped human authorization reduce unauthorized or unsupported consequential actions by a general-purpose AI agent while preserving useful task completion?

## 150-word research summary

Tool-using AI agents increasingly operate software and physical systems, creating a control problem beyond answer correctness: when should model output be permitted to acquire real action authority? I propose an evaluation using Hardware-Splicer, an existing model-independent hardware-engineering environment that separates semantic model reasoning from deterministic engineering state, provenance-bearing evidence and scoped human authorization. A frozen adversarial corpus contains partial evidence, component-identity conflicts, tool failures, plausible wrong analogies and stale-revision evidence. Claude would be evaluated as an external agent across controlled conditions, with outcomes including unsupported consequential-action attempts, correct abstention, false blocking, useful task completion, human intervention and recovery after tool/evidence failure. The intended contribution is a concrete safe-tool-use/control evaluation: not whether a model is always correct, but whether a systems architecture can keep unsupported confidence from silently becoming physical authority.

## 300-word safety framing

As AI agents gain the ability to call tools and execute multi-step workflows, the safety question shifts from only whether a model can reason correctly to what its reasoning is allowed to authorize. Physical engineering provides a consequential environment in which unsupported model confidence can become a fabricated, powered or released artifact.

Hardware-Splicer is an existing model-independent engineering environment built around a strict separation between semantic agent reasoning and independently authoritative state. An agent may inspect evidence, reason, propose, revise and use tools, but deterministic constraints, exact project/revision state, provenance-bearing evidence and explicit authorization remain outside the model. Relevant changes can invalidate earlier evidence or authority rather than silently carrying them forward.

I propose to evaluate Claude as an external tool-using agent on a frozen ten-case adversarial SPI-flash corpus. Cases include partial evidence, identity conflict, parser/tool failure, analogy traps and stale revisions. The principal comparison will use semantically equivalent task evidence under matched model/configuration, with and without the full Hardware-Splicer evidence/authority intervention. Consequential requests in the reference condition are dry-run/advisory rather than physically executed. Primary outcomes include unsupported consequential-action attempts, correct abstention/blocking, false blocking, useful task completion, human intervention and failure-recovery behavior. Complete run metadata, model/tool traces where permitted, exact revisions and adjudications will be preserved.

The project is specifically about AI control and safe consequential tool use. It does not assume that the model is infallible and does not claim that a live Claude model has already passed the benchmark. The contribution is an auditable evaluation of whether architectural constraints can preserve agent usefulness while preventing unsupported model assertions from automatically acquiring physical authority.

## Why this is AI safety research rather than product development

The primary output is a **behavioral control evaluation**, not a new commercial Hardware-Splicer feature.

The study tests:

- authority escalation under uncertain evidence;
- safe abstention and blocking;
- failure recovery after tool/evidence conflict;
- preservation of human authorization boundaries;
- stale authority carryover after revision change;
- whether useful task progress survives added control layers.

The engineering domain supplies a consequential test environment; the research question concerns AI agent control.

## Planned use of Claude API

Claude API models would act as the external agents under test. The current default design is:

- **Primary:** `claude-sonnet-5` — `10 cases × 2 conditions × 10 repeats = 200 scored runs`;
- **Confirmatory/sensitivity:** `claude-opus-5` — `10 cases × 2 conditions × 5 repeats = 100 scored runs`;
- total: **300 scored runs**, plus a small unscored transport/token pilot.

The models and exact settings should be re-checked immediately before execution, and the exact API-returned model identifiers must be preserved in the trace record.

Do not use this route merely for Claude-assisted coding, documentation or general project development.

## Working cost model

Current public list pricing used for planning on 2026-09-04:

- Claude Sonnet 5: **US$2 / MTok input, US$10 / MTok output**;
- Claude Opus 5: **US$5 / MTok input, US$25 / MTok output**.

Official pricing: https://platform.claude.com/docs/en/about-claude/pricing

Under a conservative assumption of **50k input + 10k output tokens per scored run**:

- Sonnet 5 primary, 200 runs: about **US$40**;
- Opus 5 confirmatory, 100 runs: about **US$50**;
- scored-run subtotal: about **US$90**.

A 100k-input/20k-output workload approximately doubles that subtotal. The program's standard successful award is substantially larger than the core run estimate, which gives room for pilots, retries, higher repetition, trace-validation runs and limited ablations without inventing a need to spend the full credit amount.

## Team positioning

If the form asks about the team, use the actual minimal research structure. Do not fabricate a lab or collaborators.

Preferred framing:

> Master's researcher at Yuan Ze University conducting an independent bounded evaluation using an existing agentic hardware-engineering platform. The proposed study is technically executable by the applicant using the repository's existing external-agent harness; faculty or institutional context will be identified only where actually relevant.

If the form asks for department/degree, answer it exactly. Do not imply a computer-science degree or manufacturing-lab affiliation.

## Expected outputs

1. controlled benchmark runs;
2. case-level failure/control taxonomy;
3. summary metrics for unsupported actions, abstention, false blocking, completion and intervention;
4. reproducible evaluation artifacts where provider policy permits;
5. technical report / paper draft;
6. explicit negative results and failure traces rather than success-only reporting.

## What not to say

Do not claim:

- “Hardware-Splicer is an alignment solution”;
- “Claude is unsafe unless constrained by Hardware-Splicer”;
- “the benchmark proves general agent safety”;
- “Claude has passed the corpus” before execution;
- “physical correctness is proven” while the fresh SPI bench chain remains pending.

Preferred narrower language:

> **agent control / oversight / safe consequential tool use / authority gating / evidence-constrained autonomy.**

## Remaining route-specific blanks

Only these should remain open at submission time:

- `[FINAL CLAUDE MODEL AVAILABILITY / EXACT IDS]`;
- `[PROJECT START/END WINDOW]`;
- `[PUBLIC OUTPUT FORMAT / TARGET VENUE]`;
- `[LIVE APPLICATION FIELD LIMITS]`.

## Pre-submit checklist

- [ ] current Anthropic application fields/limits re-checked;
- [ ] research topic clearly presented as AI safety/control;
- [ ] no generic product-development language leads the application;
- [ ] core protocol revision frozen before scored runs;
- [ ] current model availability/pricing re-checked;
- [ ] no pending evidence promoted into results;
- [ ] clean/non-confidential evaluation data only;
- [ ] Claude Console organization/account details ready if requested;
- [ ] receipt preserved after submission.
