# InnoServe 2026 — Verified Routing Overlay

**Verification date:** 2026-08-13  
**Status:** high-priority route  
**Online registration deadline:** 2026-10-05 16:00 (Taiwan time)

Official sources used for this routing decision:

- 2026 competition rules: https://innoserve.tca.org.tw/Rules/Detail?category=College
- 2026 competition notice: https://innoserve.tca.org.tw/News/Details/23
- download area: https://innoserve.tca.org.tw/Download

## Eligibility

The 2026 rules explicitly allow currently enrolled university students including **master's and doctoral students** in the relevant categories.

For the two recommended categories below:

- each team may have up to 8 students;
- 1–2 school advisers are required.

The general registration scheme allows a team to enter **up to two categories** (except the separate Titansoft special-award rule).

## Recommended two-category strategy

The strongest working pair for Hardware-Splicer is:

1. **Industry AI Innovation — ADIAI**
2. **AMD AI Agent Innovation — AMD**

The official rules allow up to two categories per team and list both as available designated categories. The organizer retains final authority to adjust category placement.

If entering both, prepare **two category-specific system-overview documents**. The rules explicitly require two system-overview documents for teams entering two groups.

## Required submission package

The general 2026 registration flow requires:

- system overview document;
- competition declaration / personal-data & portrait consent;
- student ID front/back or school-issued proof of enrollment when the student card does not visibly establish enrollment;
- **3-minute work-introduction video uploaded to YouTube**, with URL entered in registration;
- team photo larger than 1280×720;
- category-specific attachments where applicable.

The official competition notice states online registration runs from 2026-08-03 09:00 through **2026-10-05 16:00**, with completion before 15:59:59.

## ADIAI — why Hardware-Splicer fits

The 2026 Industry AI Innovation category explicitly welcomes AI technologies including **AI agents**, edge AI, generative AI, deep learning, machine learning and NLP for industry/social application. It also encourages disclosure/use of open platforms such as GitHub and Hugging Face, with a possible bonus for clearly describing that use in the system-overview document.

### Preliminary scoring

- Innovation — 40%
- Practicality — 30%
- Technical quality — 30%

### Final scoring

- Innovation — 30%
- Practicality — 30%
- Technical quality — 20%
- Presentation/demo — 20%

### Hardware-Splicer overlay

Emphasize:

- AI-agent engineering task quality rather than generic chat;
- real industrial semiconductor-support workflow;
- source-blind embedded operator;
- deterministic evidence/identity/revision constraints;
- physical authority separation;
- one real physical case;
- one independent user if available before finals;
- clear, visual failure→block→evidence→repair story.

The open-source/GitHub bonus should be treated as presentation leverage, not a reason to expose secrets or weaken the architecture.

## AMD AI Agent — why Hardware-Splicer fits

The official AMD category is explicitly based on **Agentic AI that autonomously plans and completes tasks**. It allows broad resources including cloud LLMs and names tools such as ChatGPT/Claude Code as examples.

For finals, however, the team **must use an AMD-related resource**, which may include:

- AMD–ITRI Joint Lab compute;
- AMD-provided cloud LLM resource;
- an AMD GPU;
- an AMD AI PC;
- other AMD-provided tooling listed by the organizer.

Do not redesign Hardware-Splicer around AMD. Add the smallest defensible **runtime/demo execution path** needed for finals while keeping the evidence/authority architecture vendor-neutral.

### Preliminary scoring

- Technical quality — 20%
- Innovation — 30%
- Market/application value — 40%
- Documentation completeness — 10%

### Final scoring

- Technical quality — 20%
- Innovation — 30%
- Market/application value — 40%
- Presentation/demo — 10%

### Prize currently listed

- 1st: NT$50,000
- 2nd: NT$30,000
- 3rd: NT$10,000
- 2 honorable mentions: NT$5,000 each

## Dominance implication

ADIAI and AMD reward different weaknesses in the current proof package:

- ADIAI strongly rewards practical/technical maturity and presentation;
- AMD puts **40%** on market/application value.

Therefore the highest-leverage work is not another internal architecture layer. It is:

1. genuine live model evidence;
2. fresh unseen-case model evidence;
3. one revision-bound physical case;
4. one independent user / pilot-quality observation;
5. a clean 3-minute video.

## 3-minute video structure

Use the canonical evaluator package, compressed to:

**0:00–0:20 — problem**  
AI hardware can look plausible before it is safe to fabricate.

**0:20–0:50 — product**  
Hardware-Splicer lets the AI reason but keeps identity/evidence/revision/authority independently auditable.

**0:50–1:40 — live product path**  
Normal task → embedded operator → proposal/unresolved state → deterministic checks → revisioned Engineering Package.

**1:40–2:25 — failure/evidence demonstration**  
Show one strong failure/refusal and, if available, the fresh unseen case / physical evidence chain.

**2:25–2:50 — practical value**  
Explain the engineering handoff problem it reduces without inventing quantified savings.

**2:50–3:00 — close**  
**AI proposes → deterministic systems constrain → bench evidence decides → human authorizes.**

If physical/live/independent proof is still pending when the video is recorded, say so explicitly rather than implying completion.

## Administrative checklist

- [ ] 1–2 school advisers confirmed
- [ ] enrollment proof available
- [ ] choose ADIAI + AMD unless a later dominance review changes the strategy
- [ ] separate system-overview document for each selected category
- [ ] 3-minute YouTube video
- [ ] team photo >1280×720
- [ ] competition declaration / consent documents
- [ ] AMD finals execution path planned without vendor-locking the core architecture
- [ ] proof-state claims synchronized with canonical evaluator package

## Go/no-go

Hardware-Splicer is already administratively eligible for both recommended categories. The remaining question is **dominance**, not eligibility.

Do not spend the long runway until October on generic feature work. Use it to turn pending live/unseen/physical/independent evidence into real artifacts.
