# AWS Community Day Taiwan 2026 — CFP Packet

**Route state:** FIRE NOW  
**CFP deadline:** 2026-09-07  
**Event:** 2026-10-31, Shih Chien University Taipei campus  
**Official event:** https://awscmd.tw/  
**Current CFP redirect:** `https://go.awscmd.tw/cfp` → external Qualtrics form

## Verified fit

The current 2026 event/CFP explicitly includes Agentic AI and Generative AI among its technical themes. The event is community-organized by AWS User Group Taiwan and is positioned around practical architecture/engineering experience rather than requiring every talk to be an AWS product tutorial.

This submission should teach transferable engineering lessons. Do **not** pretend Hardware-Splicer currently depends on AWS services merely to fit the venue.

## Recommended submission choices

- **Primary topic:** Agentic AI
- **Secondary topic:** Generative AI, if a second choice is allowed
- **Language:** English, unless the live form or speaker preference materially favors another choice
- **Audience level:** intermediate / advanced practitioner
- **Target audience:** AI/agent engineers, cloud architects, platform engineers, security/reliability engineers, technical leads building tool-using systems
- **Format:** technical case study / architecture lessons, not product pitch

Use the live form's exact labels if they differ.

## Recommended talk title

**When AI Agents Touch Hardware: Designing Evidence and Authority Boundaries**

Alternative:

**Keeping Tool-Using AI Agents Below the Physical-Authority Boundary**

The first title is preferred for this audience because it is concrete before introducing the more abstract “authority boundary” concept.

## 100-word abstract

AI agents are moving from answering questions to operating tools. In hardware engineering, that creates a dangerous transition: a plausible answer can become a fabricated or powered mistake before component identity, evidence provenance or physical behavior is actually known. This talk presents the engineering lessons behind Hardware-Splicer, an agentic hardware environment that separates model reasoning from deterministic constraints, revision-bound evidence and scoped human authorization. We will examine adversarial cases involving partial evidence, identity conflicts, tool failure, analogy traps and stale revisions, then extract reusable patterns for consequential agents: preserve provenance, make uncertainty explicit, test recovery behavior, and never let model confidence silently become action authority.

## 250-word abstract

General-purpose AI agents increasingly do more than answer questions: they call tools, modify state and execute multi-step workflows. In physical engineering, that changes the failure mode. A fluent but unsupported model answer can become a fabricated adapter, unsafe power-on decision or wasted engineering cycle before the underlying component identity, evidence provenance, revision state or physical behavior is actually established.

This talk presents a practical systems pattern developed through Hardware-Splicer, a model-independent environment for bounded agentic hardware engineering. The agent is allowed to reason, inspect evidence, propose changes and operate engineering tools through MCP/API. It is **not** allowed to silently promote model confidence into verified identity, physical evidence or release authority. Deterministic engineering constraints, exact revision state, provenance-bearing evidence and scoped human authorization remain independently authoritative.

The session walks through adversarial cases involving partial evidence, component-identity conflicts, parser/tool failure, plausible wrong analogy and stale revisions. Rather than presenting an “AI that never hallucinates,” the talk focuses on a more useful engineering question: what should the surrounding system do when an agent is wrong, uncertain, stale or overconfident?

Attendees will leave with a reusable pattern for consequential agent systems: separate reasoning from truth, bind evidence to identity and revision, make unresolved states explicit, score failure/recovery behavior, and treat authority as an explicit capability rather than something inferred from fluent output.

## Three audience takeaways

1. **Reasoning is not authority.** Agent output should not automatically become verified state or permission to act.
2. **Evidence needs identity and revision boundaries.** Stale or conflicting evidence should fail closed rather than quietly carry forward.
3. **Measure failure behavior, not only success.** Abstention, recovery, false blocking and authority escalation are first-class agent metrics.

## Why a cloud/agent audience should care

The hardware domain is the stress case, not the only application. The same failure pattern appears whenever a cloud-hosted agent can mutate consequential state through APIs, automation, infrastructure or operational tools.

The transferable architecture is:

`agent reasoning → deterministic constraints → provenance/current-state checks → explicit authority boundary`

The talk should explicitly connect this pattern back to general tool-using agents without inventing an AWS service dependency.

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

Translate the pattern into cloud/API/agent systems where a model can mutate real state.

### Q&A

Keep claims bounded to repository evidence state.

## Speaker-bio source copy

### 80-word bio

> Master's researcher at Yuan Ze University and AI/data systems builder working on evidence-grounded agentic systems, reproducible research infrastructure and empirical research. Current technical work includes Hardware-Splicer, an auditable environment for bounded AI-assisted hardware engineering, and research-data systems focused on provenance and reproducibility. The recurring research interest is how AI systems can remain useful while keeping a clear boundary between model inference, evidence and consequential authority.

### 40-word bio

> Master's researcher at Yuan Ze University building evidence-grounded agentic and research-data systems. Current work focuses on Hardware-Splicer, a bounded AI-assisted hardware-engineering environment that separates model reasoning from deterministic evidence and physical authority.

If the live form asks for department/degree, answer it exactly rather than allowing the short bio to imply a CS or engineering degree.

## Demo guidance

A live demo is optional, not required for the proposal to work.

Preferred evidence order:

1. architecture diagram;
2. one adversarial trace/case;
3. authority-boundary state transition;
4. short demo only if stable.

If a live demo is used:

- prefer the existing 3-minute external-assessment demo;
- do not imply live external-model competence if that run is still pending;
- do not show a simulated result as fresh real bench proof;
- keep a screenshot/trace fallback so the talk does not depend on live infrastructure.

## AWS-specific restraint

Do not insert Bedrock, Lambda, SageMaker or other AWS services into the talk unless they are actually used before the event. The CFP topic fit comes from Agentic AI and practical system architecture; forced cloud-service adaptation would weaken credibility.

If an AWS implementation is genuinely added later, treat it as a small deployment example rather than rewriting the talk around it.

## Pre-submit checklist

- [ ] open current Qualtrics CFP form and copy exact field/character limits;
- [ ] submit before 2026-09-07; do not depend on an unverified end-of-day cutoff;
- [ ] select Agentic AI as primary topic;
- [ ] choose language/session length from actual form options;
- [ ] use title/abstract/takeaways/bio above unless live field limits require compression;
- [ ] use one repository/demo link only if requested;
- [ ] no unsupported AWS integration claim;
- [ ] no pending live-model/physical result claimed;
- [ ] preserve exact submitted text and CFP confirmation receipt.
