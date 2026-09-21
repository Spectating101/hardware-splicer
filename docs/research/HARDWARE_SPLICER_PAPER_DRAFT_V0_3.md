# Hardware-Splicer: Evidence-Bounded Agentic PCB Engineering

*Deterministic Verification and Human-Scoped Physical Authority*

**Draft v0.3 — September 2026**  
**Artifact snapshot:** Hardware-Splicer main commit `fdaad56cf88d8f81db48bf6cd69430c79d7d5820`

> **Paper status:** working systems preprint. The software, artifact, and bounded-agent results described below are supported by preserved repository evidence. Fresh fabrication/bench validation, a full live ten-case reliability matrix, and an independent operator study remain pending and are not claimed.

## Abstract

Large language models and tool-using agents can increasingly generate hardware artifacts, write electronic-design-automation (EDA) scripts, and operate engineering tools. However, successful generation or software-level validation does not establish that a physical circuit is correct, safe to fabricate, or safe to power. This paper presents **Hardware-Splicer**, an agentic printed-circuit-board (PCB) engineering workflow designed around an explicit separation between model reasoning, deterministic engineering checks, physical evidence, and human authorization. The system exposes a canonical engineering backend through a Model Context Protocol (MCP) gateway, binds project state and evidence to exact revisions and artifact hashes, preserves model/tool traces, and treats physical authority as a separate, human-scoped state rather than a consequence of model confidence or continuous-integration success.

We evaluate the approach on a complete pre-fabrication reference design: a 3.3 V host to 1.8 V W25Q128JW SPI-flash adapter using a TXU0304 level translator and TLV75518 regulator. The artifact includes an editable KiCad 9 schematic, routed two-layer PCB, exact bill of materials, 18 test points, 20 ground-stitching vias, deterministic packaging, and a staged physical handoff procedure. At the evaluated artifact snapshot, the machine-verification receipt reports zero schematic ERC errors or warnings, zero actionable PCB DRC violations, zero unconnected pads, and zero footprint, BOM, topology, schematic-parity, assembly-variant, board-identity, or ground-reference issues. A preserved live Astra run additionally demonstrates bounded operation through the canonical tool surface and revision-linked substantive project progress. Importantly, after these successes the system still reports `physical_correctness = UNPROVEN` and `physical_authority_granted = false`, because no reference board has yet been fabricated or measured.

The contribution is therefore not a claim of autonomous hardware correctness. It is a systems pattern for **evidence-bounded agentic engineering**: AI may propose and operate tools, deterministic systems may constrain and verify digital artifacts, physical evidence may establish measured behavior, and a human may authorize the next physical step—without allowing one evidence class to silently substitute for another.

**Keywords:** agentic engineering; PCB design; electronic design automation; large language models; hardware verification; provenance; Model Context Protocol; human-in-the-loop engineering

## 1. Introduction

Generative models are rapidly entering electronic-design-automation workflows. Prior work has shown that language models can serve as engineering assistants, generate EDA scripts, decompose design flows, and synthesize digital or PCB-oriented artifacts [1–5]. These systems address a real productivity problem: modern hardware development requires engineers to coordinate specifications, component documentation, scripts, design tools, verification outputs, and repeated revisions across a long toolchain.

The central engineering risk is equally clear: **a plausible model output is not the same thing as a physically correct circuit**. Conventional EDA checks have explicit limits. Electrical-rules checking can reject many connection errors, and design-rule checking can verify a PCB against encoded geometry and connectivity constraints, but neither measures the behavior of a manufactured board [6,7]. A model that can call such tools therefore inherits neither their authority nor capabilities beyond their scope.

Hardware-Splicer was developed around this distinction. Its design principle is:

> **AI proposes → deterministic systems constrain → bench evidence decides → human authorizes.**

The objective is narrower than autonomous hardware design. Hardware-Splicer asks whether a general-purpose AI agent can perform useful hardware-engineering work while deterministic constraints, source provenance, exact revision state, physical measurements, and human authorization remain independently authoritative.

This paper studies that question through a concrete end-to-end artifact rather than a prompt-only benchmark. The reference task is a 3.3 V-host to 1.8 V SPI-flash adapter for a W25Q128JW device. The system must reason over manufacturer constraints, preserve exact component identity, generate and manipulate engineering artifacts, produce a routed KiCad design, run electrical and board-level checks, package fabrication and review outputs reproducibly, and prepare a physical validation sequence. At the same time, the workflow must refuse to interpret digital success as physical success.

The paper makes four contributions:

1. **An evidence-bounded authority model for agentic hardware engineering.** Hardware-Splicer separates software evidence, agent-execution evidence, physical evidence, and authorization evidence. Evidence does not automatically move upward between these classes.
2. **A canonical tool surface for model-independent engineering operation.** A general-purpose agent reaches the same backend used by the Web/API/CLI product through an MCP gateway rather than through a separate model-specific implementation.
3. **A reproducible pre-fabrication PCB artifact with fail-closed verification.** The reference design binds the schematic, PCB, bill of materials, project rules, symbols, manifest, and verifier to cryptographic hashes and rejects missing, ambiguous, or inconsistent validation state.
4. **An evaluation that treats unproven physical correctness as a result rather than a defect to hide.** Software checks and a live agent run pass their respective bounded criteria, yet fabrication and power-on authority remain false because the relevant physical evidence does not exist.

The main research question is:

> **Can an AI-assisted hardware workflow produce a reproducible, reviewable pre-fabrication PCB artifact while keeping model reasoning, deterministic validation, physical evidence, and human authorization as distinct authority layers?**

The present study answers this question only at the software, artifact, and workflow levels. No board from the evaluated reference design has yet been fabricated or measured. Physical correctness is explicitly outside the current claim boundary.

## 2. Related Work

### 2.1 Language models in EDA

ChatEDA couples an LLM-based agent with EDA executors to decompose and operate an RTL-to-GDSII flow [1]. ChipNeMo demonstrates domain adaptation for industrial chip-design applications including engineering question answering, EDA script generation, and bug summarization [2]. Surveys of LLMs for EDA describe a rapidly expanding design space while emphasizing reliability, verification, domain knowledge, and integration challenges [3].

These systems establish that language models can be productive participants in hardware workflows. Hardware-Splicer is complementary: its research object is not only whether a model can generate a candidate, but how candidate generation is separated from evidence and authority after a model gains access to real engineering tools.

### 2.2 Generative systems for PCB design

PCBSchemaGen combines an LLM agent with constraint-guided synthesis and a datasheet-derived knowledge graph to generate and verify PCB schematics [4]. SchGen focuses on a semantically grounded code representation and a large schematic dataset to improve editable PCB schematic generation [5]. Both highlight a defining property of PCB work: real components have package, pin, voltage, direction, topology, and manufacturability constraints that must be represented explicitly.

Hardware-Splicer shares the view that hardware generation should be constrained by machine-checkable structure, but emphasizes a different layer. Model output is a proposal inside a revisioned project; verification extends to provenance, artifact hashes, packaging, and handoff state; and physical authority remains explicit so that passing a digital checker cannot be interpreted as permission to fabricate or power hardware.

### 2.3 Tool-using agents and protocol boundaries

MCP provides a standardized interface through which AI applications can discover and invoke external tools [8]. Hardware-Splicer uses MCP as a transport and discovery boundary, not as a correctness mechanism. The gateway exposes the canonical product backend instead of duplicating engineering logic in a model adapter. Tool transport success and engineering correctness therefore remain separate claims.

## 3. System Design

### 3.1 Evidence and authority classes

Hardware-Splicer separates four evidence classes:

1. **Software evidence** — code, deterministic validators, EDA checks, exact-head tests, and reproducible package generation.
2. **Agent evidence** — actual model inputs, outputs, tool calls, trace state, and replay material.
3. **Physical evidence** — measurements explicitly identified as real and bound to an exact project revision, artifact identity, setup, and component state.
4. **Authority evidence** — explicit, scoped human decisions made after relevant evidence is valid.

The system does not allow success in one class to silently promote a claim into another. Green CI is not physical evidence. A successful MCP call is not model competence. A fabrication package is not fabrication authorization. A model cannot authorize its own proposal.

### 3.2 Revision-bound project state

Agentic workflows create frequent revisions. Hardware-Splicer therefore treats project revision and artifact identity as part of the engineering truth state. Evidence is bound to exact revisions and hashes. Relevant changes can invalidate prior evidence or authority rather than allowing stale validation to carry forward.

This mechanism is particularly important at the physical boundary. A bench measurement is meaningful only relative to the exact board revision, component population, setup, and procedure that produced it.

### 3.3 Canonical engineering surface

The current agent path exposes the canonical Hardware-Splicer backend through a four-tool MCP discovery/dispatch gateway. The gateway is generated from the canonical FastAPI/OpenAPI product surface rather than from a second model-specific implementation. At the documented proof checkpoint the MCP contract exposes 193 canonical backend operations and has been exercised through both stdio and Streamable HTTP clients.

The product additionally exposes Web, HTTP API, CLI, and MCP surfaces around the same project state and verification logic. This reduces the risk that an agent demo operates a simplified system with different engineering semantics from the actual product.

### 3.4 Fail-closed physical evidence

Physical evidence must explicitly identify itself as real. Missing or ambiguous simulation status is blocking; a capture does not become physical evidence merely because `simulated` was omitted. The durable physical path binds evidence envelope/content hashes, exact project revision, expected candidate state, evidence kinds, and authorization scope.

The resulting rule is intentionally simple: **software may prepare a physical action, but it cannot manufacture the evidence required to justify that action.**

## 4. Reference Design

The evaluated artifact is `spi-flash-adapter-v1`, a probing-oriented two-layer adapter between a 3.3 V host and a 1.8 V Winbond W25Q128JW SPI flash device.

The design contains:

- a TXU0304PWR level translator with three A-to-B channels and one B-to-A channel;
- a TLV75518PDBVR fixed 1.8 V regulator;
- explicit host and DUT rail-isolation/current-measurement links;
- independent chip-select biasing for the host and DUT domains;
- a default-disabled translator with a normally open enable path;
- local decoupling, dual ground fills, and 20 ground-stitching vias;
- 18 test points and four mounting holes;
- a 90 mm × 50 mm two-layer PCB;
- a read-only first-use transaction using SPI command `0x9F` at 5 MHz, mode 0.

The initial assembly deliberately leaves selected links unpopulated and keeps the translator disabled. These choices support staged bring-up rather than maximizing convenience at first power-on.

The design is tied to frozen manufacturer-document identities for the W25Q128JW, TXU0304, and TLV755 family. Project-local KiCad symbols represent the relevant manufacturer pinout and directionality. The current artifact is explicitly a **bounded pre-fabrication result**: internally consistent and reviewable, but not fabrication-authorized, power-on-authorized, or physically validated.

## 5. Deterministic Verification and Packaging

The reference-design verifier fails closed unless all recognized structural and EDA checks are satisfied. The checked-in verification receipt binds the canonical schematic, routed PCB, BOM, design manifest, project rules, symbol library, symbol table, electrical contract, and verification logic to SHA-256 identities.

At the current artifact snapshot the recorded checks are:

| Check | Result |
|---|---:|
| schematic ERC errors | 0 |
| schematic ERC warnings | 0 |
| actionable PCB DRC violations | 0 |
| unconnected PCB pads | 0 |
| footprint errors | 0 |
| schematic-to-PCB parity issues | 0 |
| BOM parity issues | 0 |
| required-topology issues | 0 |
| assembly-variant issues | 0 |
| board-identity issues | 0 |
| ground-reference issues | 0 |

The toolchain recorded in the verification artifact uses KiCad CLI/pcbnew 9.0.2. Routing is pinned to Freerouting v2.4.1, but routing output receives no independent authority: imported routing must still pass KiCad DRC, connectivity, and schematic-parity checks.

The board-level verifier additionally checks structural ground-reference constraints. The current receipt records filled ground areas of 4,291.606 mm² on B.Cu and 3,354.461 mm² on F.Cu, with 20 ground-stitching vias and local ground-via distances below 2 mm for the checked IC and bypass-capacitor ground pads. These are geometric checks, not impedance or waveform measurements.

The review/manufacturing package contains canonical KiCad sources, BOM/design/verification records, renders, Gerbers, drill files, placement data, and per-file SHA-256 identities. Timestamps and selected generated fields are normalized so repeated packaging of the same canonical inputs is reproducible. Package existence does not set `fabrication_ready` to true.

## 6. Agent Execution Evidence

Hardware-Splicer includes a frozen ten-case external SPI corpus covering baseline and adversarial variants such as source ordering, mission paraphrase, partial evidence, identity conflict, parser failure, plausible analogy traps, and stale-revision evidence. The corpus and proof harness are preserved separately from live-model results.

A live primary-source Astra run is preserved as a sanitized proof bundle. That run demonstrates bounded MCP operation, revision-linked substantive project progress, provenance, and a constrained terminal report. Its recorded result is `passed` for the bounded protocol, while the preserved state remains:

- `physical_correctness = UNPROVEN`;
- `physical_authority_granted = false`;
- unseen competence adjudication remains outside what the single run can establish.

This distinction is important. The run establishes that a general-purpose model can perform substantive work through the canonical tool surface. It does not establish source truth, universal engineering correctness, fabrication readiness, or distributional reliability over the frozen ten-case corpus.

## 7. Evaluation

The present evaluation asks three bounded questions.

### RQ1 — Can an external AI operate the canonical engineering system rather than a demonstration-only adapter?

**Supported at existence level.** The MCP path reaches the canonical backend and preserves existing revision/evidence/authority behavior. Real stdio and Streamable HTTP clients, stateful project operations, and a preserved live Astra run establish that the agent surface is executable.

### RQ2 — Can the workflow produce a complete, reproducible pre-fabrication PCB artifact that passes encoded engineering checks?

**Supported for the evaluated reference design.** The SPI adapter includes editable KiCad sources, a routed PCB, exact BOM, explicit component identities, deterministic packaging, and a verification receipt with zero recorded issues in the encoded ERC/DRC/parity/topology/BOM/assembly/ground-reference checks.

### RQ3 — Does digital success remain separated from physical correctness and authorization?

**Supported structurally and by the current result state.** Despite successful digital checks and bounded agent execution, the project continues to report physical correctness as unproven and physical authority as false. The current workflow therefore demonstrates the intended separation rather than silently upgrading digital success into a physical claim.

The evaluation does **not** answer whether the PCB will function after fabrication. That question requires physical evidence and remains intentionally open.

## 8. Discussion

### 8.1 The central result is separation, not autonomy

A conventional demonstration of an AI hardware agent often emphasizes how much of the design flow the model can perform. Hardware-Splicer instead treats the boundary between *performance* and *authority* as a first-class systems problem.

A clean ERC/DRC report is valuable because it rejects a class of candidate defects; it does not become a proxy for bench measurement. A live model run is valuable because it demonstrates operational capability; it does not become evidence that all source interpretations are correct. A complete Gerber package is valuable because it makes an artifact inspectable and reproducible; its existence does not authorize fabrication.

The practical objective is not to eliminate model error. It is to prevent a model error from obtaining more authority than the available evidence supports.

### 8.2 Deterministic checks should remain independently authoritative

LLMs can explain engineering rules and may correctly predict whether a design will pass a checker, but allowing the model to be both proposer and sole judge collapses independence. Hardware-Splicer therefore uses EDA tools and dedicated validators as separate adjudicators for machine-checkable claims.

This does not make the deterministic layer complete. A checker cannot reject a constraint that nobody encoded. The correct interpretation is therefore **independent validation of encoded constraints**, not formal proof of all hardware behavior.

### 8.3 Failure is part of the research artifact

The reference design's revision history includes corrections to an earlier candidate, and the proof area preserves failed or diagnostic runs rather than publishing only successful traces. This matters for agentic engineering: if failures are deleted after the system sees the case, later evaluation becomes difficult to audit and can overstate reliability.

Hardware-Splicer therefore treats frozen cases, replay material, and failure preservation as part of the research artifact. The system is intended to make it possible to study not only whether an agent succeeds, but how it fails and whether the surrounding engineering system contains the failure.

## 9. Limitations and Next Experiments

### 9.1 No fabricated-board evidence

The largest limitation is explicit: the evaluated SPI reference board has not yet been fabricated or measured. Consequently, this paper makes no claim about rail behavior, waveform quality, thermal behavior, assembled-system timing margin, component substitutions, assembly defects, or real functional success.

The highest-value next experiment is to fabricate the frozen candidate, preserve the exact manufacturing package, execute the staged bring-up with independent review, and ingest raw measurements as revision-bound real evidence.

### 9.2 Incomplete live-model reliability evaluation

One live primary-source run demonstrates bounded operation, but the frozen ten-case adversarial corpus has not yet been executed as a completed live-provider reliability matrix. Future work should preregister the provider/model/configuration and run all unchanged cases while retaining failures, tool traces, and outer adjudication.

Useful quantitative measures include case completion rate, evidence-identity errors, unsupported authority attempts, stale-revision errors, tool-recovery behavior, and trace divergence under semantically equivalent perturbations.

### 9.3 No independent operator study yet

A technically competent outsider who did not author the system has not yet completed the canonical independent-operator protocol. A future study should measure setup time, intervention count, misunderstood states, tool failures, evidence omissions, recovery behavior, and whether the authority model is understandable to a reviewer.

### 9.4 Single reference-design family

The current evaluation centers on one SPI adapter. It cannot establish generality across analog, mixed-signal, power, RF, high-speed digital, safety-critical, or production-scale boards. Additional reference designs should deliberately stress different constraint and measurement classes.

## 10. Conclusion

Hardware-Splicer demonstrates a practical systems pattern for integrating general-purpose AI agents into PCB engineering without treating the model as final authority. The system combines a canonical tool surface, revision-bound project state, deterministic EDA and domain checks, provenance-bearing artifacts, replayable agent traces, explicit physical-evidence requirements, and human-scoped authorization.

On the evaluated 3.3 V-to-1.8 V SPI-flash reference design, Hardware-Splicer produces a complete and reproducible pre-fabrication KiCad artifact with clean encoded verification results. A preserved live Astra run shows that a general-purpose model can perform substantive work through the canonical bounded interface. Yet the system still reports the correct current physical state: **unproven**.

That negative state is not missing polish; it is the principal systems result. The workflow is designed so that an AI can be useful before it is trustworthy enough to act alone, and so that digital success cannot silently become permission to cross into the physical world.

The next decisive experiment is physical: fabricate the frozen reference design, bind the board and instrumentation to the exact artifact revision, execute the staged validation protocol, preserve failures and repairs, and determine whether the evidence chain can carry the system from a verified digital candidate to a justified human authorization.

## References

[1] Z. He, H. Wu, X. Zhang, X. Yao, S. Zheng, H. Zheng, and B. Yu, “ChatEDA: A Large Language Model Powered Autonomous Agent for EDA,” arXiv:2308.10204, 2023.

[2] M. Liu et al., “ChipNeMo: Domain-Adapted LLMs for Chip Design,” arXiv:2311.00176, 2023.

[3] J. Pan, G. Zhou, C.-C. Chang, I. Jacobson, J. Hu, and Y. Chen, “A Survey of Research in Large Language Models for Electronic Design Automation,” arXiv:2501.09655, 2025.

[4] H. Zou, P. Han, E. Nazerian, and A. Q. Huang, “PCBSchemaGen: Constraint-Guided Schematic Design via LLM for Printed Circuit Boards (PCB),” arXiv:2602.00510, 2026.

[5] Q. Luo, R. Ma, X. Zhang, and L. Qiu, “SchGen: PCB Schematic Generation with Semantic-Grounded Code Representations,” arXiv:2605.30345, 2026.

[6] KiCad Project, “Schematic Editor 9.0 Documentation — Electrical Rules Checking,” KiCad Documentation, 2026.

[7] KiCad Project, “PCB Editor 9.0 Documentation — Design Rules Checking,” KiCad Documentation, 2026.

[8] Model Context Protocol, “The 2026-07-28 Specification,” Model Context Protocol specification release, July 28, 2026.

[9] Hardware-Splicer, open-source artifact repository, artifact snapshot `fdaad56cf88d8f81db48bf6cd69430c79d7d5820`, September 2026.

[10] J. Knechtel, O. Sinanoglu, and R. Karri, “LLMs for Secure Hardware Design and Related Problems: Opportunities and Challenges,” arXiv:2605.10807, 2026.

## Appendix A. Reproducibility Snapshot

- paper artifact snapshot: `fdaad56cf88d8f81db48bf6cd69430c79d7d5820`;
- live Astra primary-source proof run repository commit: `7780ba99b1b67f45d3c97dd5f69689fbae2663d9`;
- evaluated PCB toolchain: KiCad CLI/pcbnew 9.0.2;
- router: Freerouting v2.4.1, accepted only after KiCad verification;
- reference design ID: `spi-flash-adapter-v1`;
- physical correctness at the draft snapshot: `UNPROVEN`;
- physical authority at the draft snapshot: `false`.
