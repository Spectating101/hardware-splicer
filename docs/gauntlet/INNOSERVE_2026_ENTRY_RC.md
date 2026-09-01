# Hardware Splicer — InnoServe 2026 Entry RC

## Official 2026 constraints to design around

Source: 2026 InnoServe college rules and FAQ at `https://innoserve.tca.org.tw/Rules/Detail?category=College` and `https://innoserve.tca.org.tw/FAQ`.

- Registration: **2026-08-03 09:00 to 2026-10-05 16:00**.
- Final: **2026-11-07**, National Taiwan University Sports Center.
- Current university / graduate students are eligible.
- Team: up to 8 students + 1–2 school advisors.
- A team can select at most two competition groups (except the separate Titansoft Agile special award rule).
- Required core submission assets include a system overview document, student-status evidence, consent materials, team photo and a **3-minute YouTube introduction video**.
- FAQ: system overview must be a Word file, **no more than 5 pages**, max 4 MB, with required typography per the organizer template.

Always re-check the official site before final upload because organizer attachments can be revised during the registration period.

## Recommended entry configuration

### Primary: Information Application (IP)

Best default because Hardware Splicer is now a complete information / engineering application rather than only a model demo.

2026 final scoring emphasizes:

- Innovation — 30%
- Practicality — 15%
- Stability / UX — 15%
- Scalability — 15%
- System documentation — 15%
- Presentation — 10%

This makes the product-convergence work strategically important: judges must see one stable workflow, not a bag of kernels.

### Second default: AI Tool Application (Generative AI)

Use the same product with stronger emphasis on AI-assisted mission planning, candidate generation, evidence-aware operator guidance and tool orchestration.

2026 final scoring emphasizes:

- Innovation — 30%
- Application / integration / user acceptance — 40%
- Technical maturity / scalability — 20%
- Demonstration — 10%

### Optional swap: AMD AI Agent Innovation

Consider replacing the second entry with AMD only if we deliberately integrate an AMD resource before finals. Official 2026 rules require finalist demonstrations to use AMD-related resources.

AMD judging emphasizes:

- Technical — 20%
- Innovation — 30%
- Market — 40%
- Documentation / presentation — 10%

Hardware Splicer is a plausible fit because the product agent can plan and execute a multi-step resource-to-machine workflow, but do not force this track merely for the AI-agent label. The required AMD demonstration dependency must be real.

## Entry title

**Hardware Splicer — Reuse-First AI for Turning Available Hardware Into Buildable Machines**

Alternative short title:

**Hardware Splicer: What Can I Build With What I Already Have?**

## One-line problem

Modern engineering software is excellent once the desired design is known, but people, labs and repair environments often begin with a heterogeneous pile of real existing hardware whose identity, compatibility and reuse value are incomplete or uncertain.

## One-line solution

Hardware Splicer inventories those resources, synthesizes candidate machine architectures under budget / reuse / risk constraints, tells the operator what evidence is missing, verifies bounded engineering claims, and generates simple missing mechanical adapters when necessary.

## System-overview document: five-page structure

### Page 1 — Problem + product

**Headline:** What can I build with what I already have?

Use one strong photo of a real parts pile / cyberdeck donor set.

Cover:

- existing hardware is hard to reintegrate because geometry, interfaces, identity and condition vary;
- current specialist CAD / ECAD systems normally assume a design problem has already been specified;
- Hardware Splicer starts from resources and a desired outcome;
- canonical loop: **Inventory → Goal → Candidates → Resolve → Verify → Build**.

Do not begin with architecture diagrams.

### Page 2 — Product workflow

Show six horizontally connected product screens / states:

1. donor / parts-bin intake;
2. resource inventory with confidence and provenance;
3. goal / budget;
4. candidate comparison;
5. concrete Resolve action;
6. workbench / build output.

Include one candidate comparison such as:

| Candidate | Reuse | Additional cost | Open evidence | Character |
| --- | ---: | ---: | ---: | --- |
| Maximum reuse | high | medium | several | preserves donor hardware |
| Balanced | medium-high | medium | fewer | default |
| Low risk | lower | higher | fewest | substitutes uncertain parts |

Use real system output when capturing the final submission; do not invent metrics for the document.

### Page 3 — Technical differentiation

Focus only on capabilities judges can observe:

- resource strategy across owned / salvaged / procurable / designed parts;
- source / provenance model;
- exact placement + BREP geometry;
- surface anchors and mating checks;
- insertion / path reasoning;
- guided operator evidence collection;
- calibrated bench measurement sessions;
- bounded adapter synthesis with STEP export and parent-solid checks.

Add one authority ladder:

> AI inference → operator observation → source evidence → exact computation → calibrated measurement → physical result → human authority

Key statement:

> **The model can propose; it cannot silently promote its own proposal into physical truth.**

### Page 4 — Canonical use case + impact

Primary case: **cyberdeck from existing / salvaged hardware**.

Mission example:

> Build a portable Linux cyberdeck from the available display, compute board, keyboard, battery, hub and enclosure hardware while minimizing additional spending.

Show:

- resource pile;
- selected architecture;
- one incompatibility;
- generated adapter;
- build output.

Broader applications:

- inspection rover;
- repair / upgrade;
- lab fixtures;
- field instruments;
- prototyping with parts-bin / COTS inventory.

Do not claim measured waste diversion or market ROI until external builds provide evidence. State those as evaluation targets.

### Page 5 — Evidence, maturity + expansion

Separate **what works now** from **next empirical proof**.

Works now:

- guided reuse mission UI;
- provisional donor intake;
- candidate resource planning;
- actionable Resolve flow;
- measurement / field-agent flow;
- project-bound STEP / placement / exact geometry;
- bounded adapter synthesis.

Next physical evidence:

- canonical cyberdeck build;
- fabricated HS-generated adapter;
- repeated second build (inspection rover);
- measured task time / additional spend / reuse ratio;
- successful and failed compatibility records.

Expansion thesis:

> recycling → salvage → parts-bin DIY → repair → upgrade → lab / field tools → constrained prototyping.

## Three-minute video script

### 0:00–0:20 — Cold open

Camera on a pile of actual hardware.

**Narration:**

> “CAD can design almost anything. But it does not begin with this question: I already own these unrelated parts — what useful machine can they become?”

### 0:20–0:40 — Product thesis

Open the Hardware Splicer landing / Mission surface.

> “Hardware Splicer is a reuse-first physical systems synthesis platform. It starts from available resources, not an empty canvas.”

Show the six-stage loop.

### 0:40–1:05 — Inventory

Photograph a donor item or show the donor intake.

Emphasize:

> “A photo observation can enter planning, but it stays provisional. The system does not invent voltage, connector or geometry facts just because the object looks familiar.”

### 1:05–1:30 — Candidate architectures

Set the cyberdeck goal / budget. Compare reuse / balanced / low-risk candidates.

> “The optimization objective may change the architecture. Evidence requirements do not.”

### 1:30–1:50 — Resolve

Open a concrete blocker.

Show an instruction such as identify a model, measure current, confirm a connector or attach measured geometry.

> “Instead of saying ‘insufficient evidence,’ Hardware Splicer tells the operator exactly what information closes the decision.”

### 1:50–2:25 — Engineering workbench

Show direct pose editing, Geometry, exact surface anchors and adapter synthesis.

> “Here the problem is mechanical: these donor surfaces do not directly connect. Hardware Splicer resolves the exact BREP surfaces, generates the missing bridge as a real STEP solid, and immediately checks it against both parents.”

Show the adapter in the actual scene.

### 2:25–2:45 — Authority boundary

Zoom the generated adapter result.

> “Geometry can pass while fabrication remains blocked. Material, retention, tolerance, strength and electrical compatibility still need their own evidence.”

This is a feature, not a disclaimer.

### 2:45–3:00 — Close

Return to the parts pile / physical build.

> “Hardware Splicer turns what you already have into what you can actually build — while keeping every unproven assumption visible.”

End card:

**Waste → Inventory → Goal → New Machine**

## Judge questions to prepare

### “Isn’t this just Fusion / Onshape with AI?”

No. Those tools are stronger specialist authoring environments. HS begins from heterogeneous physical resources and decides what can be reused, what must be measured / bought / fabricated, and which claims are evidence-backed. Specialist CAD can remain a backend for complex authoring.

### “Why does this need AI?”

AI handles open-ended interpretation, mission decomposition, candidate generation and operator guidance across heterogeneous evidence. Deterministic engineering kernels and evidence rules constrain claims that should not be decided by language-model confidence.

### “What is actually verified?”

Answer by evidence class. For the mechanical demo: source hash / pose binding, exact OCCT surfaces, bounded parent distance / intersection and generated STEP can be computationally verified. Structural, material, retention and fabrication remain explicitly unresolved unless separately proven.

### “What stops Autodesk from copying this?”

The current product is a wedge, not yet a moat. The defensible asset would come from accumulated observed compatibility: donor identities, measured characteristics, adapters that worked / failed, revision differences and physical build outcomes. That feedback graph must be built through real deployments.

### “Who uses it first?”

Near-term users:

- makers / cyberdeck builders;
- repair / reuse communities;
- university labs;
- robotics prototyping teams;
- technicians / field engineers with existing inventories.

### “What is the business model?”

Do not overclaim. Plausible lanes:

- individual maker / pro subscription;
- lab / team workspace;
- component / supplier / procurement integrations;
- enterprise repair / reuse / maintenance workflows;
- compatibility / evidence intelligence services.

Market and willingness-to-pay require external validation.

## Submission asset checklist

Before upload:

- [ ] exact RC SHA frozen;
- [ ] canonical deployment URL;
- [ ] root landing page screenshot;
- [ ] Mission screenshot;
- [ ] candidate comparison screenshot;
- [ ] Resolve screenshot;
- [ ] exact Geometry / anchor screenshot;
- [ ] generated adapter screenshot;
- [ ] physical donor-pile photo;
- [ ] physical cyberdeck / partial-build photo if available;
- [ ] 3-minute English / Chinese narration version as appropriate;
- [ ] ≤5-page system overview in organizer template;
- [ ] advisor(s) confirmed;
- [ ] student-status evidence;
- [ ] consent / team photo assets;
- [ ] every numerical claim reconciled against repository / physical evidence.

## Final track decision rule

Default to **IP + Generative AI** unless a stronger external dependency is deliberately closed.

Choose **AMD** instead of Generative AI only if:

- AMD runtime / hardware is genuinely integrated;
- the final live demo can run with the required AMD resource;
- the market-oriented story is stronger than the general AI-tool story.

Do not enter a vendor track with a last-minute cosmetic integration.
