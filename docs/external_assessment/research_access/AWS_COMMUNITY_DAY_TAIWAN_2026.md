# AWS Community Day Taiwan 2026 — CFP Packet

**Route state:** FIRE NOW  
**CFP deadline:** 2026-09-07  
**Event:** 2026-10-31, Shih Chien University Taipei campus  
**Official event:** https://awscmd.tw/

## Verified fit

The 2026 CFP explicitly includes six topic areas, including **Generative AI applications** and **Agentic AI trends**. English-language sessions are accepted alongside Chinese sessions. The official event page states that first-time participants are welcome and that the conference is community-organized by AWS User Group Taiwan with AWS/AWS Educate support.

This submission should teach transferable engineering lessons. Do **not** pretend Hardware-Splicer currently depends on AWS services merely to fit the venue.

## Recommended talk title

**When an AI Agent Can Touch Hardware: Evidence, Authority, and Failure Boundaries**

Alternative:

**Keeping Tool-Using AI Agents Below the Physical-Authority Boundary**

## Recommended topic

Primary: **Agentic AI**  
Secondary if the form allows: **Generative AI applications**

## 100-word abstract

AI agents are moving from answering questions to operating tools. In hardware engineering, that creates a dangerous transition: a plausible answer can become a fabricated or powered mistake before component identity, evidence provenance or physical behavior is actually known. This talk presents the engineering lessons behind Hardware-Splicer, an agentic hardware environment that separates model reasoning from deterministic constraints, revision-bound evidence and scoped human authorization. We will examine adversarial cases involving partial evidence, identity conflicts, tool failure, analogy traps and stale revisions, and discuss a broader design principle for consequential agents: useful autonomy should increase without allowing model confidence to silently acquire physical authority.

## 250-word abstract

General-purpose AI agents increasingly do more than answer questions: they call tools, modify state and execute multi-step workflows. In physical engineering, that changes the failure mode. A fluent but unsupported model answer can become a fabricated adapter, unsafe power-on decision or wasted engineering cycle before the underlying component identity, evidence provenance, revision state or physical behavior is actually established.

This talk presents a practical systems pattern developed through Hardware-Splicer, a model-independent environment for bounded agentic hardware engineering. The agent is allowed to reason, inspect evidence, propose changes and operate engineering tools through MCP/API. It is **not** allowed to silently promote model confidence into verified identity, physical evidence or release authority. Deterministic engineering constraints, exact revision state, provenance-bearing evidence and scoped human authorization remain independently authoritative.

The session will walk through adversarial cases involving partial evidence, component-identity conflicts, parser/tool failure, plausible wrong analogy and stale revisions. Rather than presenting an “AI that never hallucinates,” the talk focuses on a narrower and more useful engineering question: what should happen when an agent is wrong, uncertain or working from stale evidence?

Attendees will leave with a reusable design framework for consequential agent systems: separate reasoning from truth, preserve provenance and revision state, make unresolved states explicit, and treat authority as a capability that must be earned by evidence rather than inferred from model confidence.

## Three audience takeaways

1. **Reasoning is not authority.** Agent output should not automatically become verified state or permission to act.
2. **Evidence needs identity and revision boundaries.** Stale or conflicting evidence should fail closed rather than quietly carry forward.
3. **Measure failure behavior, not only success.** Abstention, recovery, false blocking and authority escalation are first-class agent metrics.

## Suggested session flow — 30–40 minutes

### 0–5 min — The new failure boundary

Why tool-using agents create a different problem from chat assistants.

### 5–12 min — Four-layer architecture

- model reasoning;
- deterministic engineering constraints;
- provenance/revision-bound evidence;
- explicit human authority.

### 12–22 min — Adversarial cases

Use examples from the frozen SPI corpus:

- partial evidence;
- conflicting identity;
- tool failure;
- plausible wrong analogy;
- stale revision.

### 22–30 min — What to measure

- unsupported consequential actions;
- correct abstention;
- false blocking;
- recovery;
- intervention;
- useful task completion.

### 30–35 min — Generalization beyond hardware

Apply the same pattern to other consequential agentic workflows.

### Q&A

Keep claims bounded to repository evidence state.

## Speaker-bio source copy

### 80-word bio

> University-affiliated master's researcher and AI/data systems builder working on evidence-grounded agentic systems, reproducible research infrastructure and empirical research. Current technical work includes Hardware-Splicer, an auditable environment for bounded AI-assisted hardware engineering, and research-data systems focused on provenance and reproducibility. The recurring research interest is how AI systems can remain useful while keeping a clear boundary between model inference, evidence and consequential authority.

### 40-word bio

> University-affiliated master's researcher building evidence-grounded agentic and research-data systems. Current work focuses on Hardware-Splicer, a bounded AI-assisted hardware-engineering environment that separates model reasoning from deterministic evidence and physical authority.

## Demo guidance

If a live demo is requested or useful:

- prefer the existing 3-minute external-assessment demo;
- show architecture + one adversarial case + authority boundary;
- do not imply live external-model competence if that run is still pending;
- do not show a simulated result as fresh real bench proof.

## AWS-specific restraint

Do not insert Bedrock, Lambda, SageMaker or other AWS services into the talk unless they are actually used before the event. The CFP topic fit comes from Agentic AI; forced cloud-service adaptation would weaken credibility.

If an AWS implementation is genuinely added later, treat it as a minor deployment example rather than rewriting the talk around it.

## Pre-submit checklist

- [ ] open current CFP form and copy exact field/character limits;
- [ ] submit before 2026-09-07;
- [ ] select Agentic AI as primary topic;
- [ ] choose English unless a Chinese delivery is intentionally preferred;
- [ ] use one repository/demo link only if the form requests it;
- [ ] no unsupported AWS integration claim;
- [ ] no pending live-model/physical result claimed;
- [ ] preserve CFP confirmation receipt.
