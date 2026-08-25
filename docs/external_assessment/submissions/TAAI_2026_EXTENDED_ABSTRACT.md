# TAAI 2026 Domestic Track — Extended Abstract Source

## Separating Model Reasoning from Physical Authority in Agentic Hardware Engineering

### Abstract

General-purpose AI agents increasingly invoke tools and act across multiple engineering steps, but hardware introduces a consequential boundary: plausible model output can reach fabrication or power-on decisions before component identity, evidence provenance, revision state, or physical behavior is established. We present **Hardware-Splicer**, a model-independent environment that separates semantic agent reasoning from deterministic engineering constraints, provenance-bearing evidence, exact project/revision state, and scoped human physical authority. General-purpose agents operate the canonical engineering backend through MCP, while revision/evidence/authority gates remain outside the model. A frozen ten-case adversarial SPI-flash corpus covers source-order perturbations, partial evidence, component-identity conflict, tool failure, plausible wrong analogy, and stale revision. Current evidence establishes the deterministic software/MCP infrastructure and replayable external-agent test harness: real MCP stdio and Streamable HTTP clients complete canonical stateful operations across a 193-operation backend surface while MCP itself remains unable to grant physical authority. Live external-model, fresh physical, and independent-operator results are reported only when those experiments are actually executed. The central contribution is an auditable experimental architecture in which agent reasoning quality and the right to act in the physical world can be evaluated as distinct outcomes.

**Keywords:** Agentic AI; Physical AI; trustworthy agents; hardware engineering; MCP; evidence provenance; human authorization; design automation

## 1. Motivation

Tool-using language models are moving from advisory text generation toward workflows in which an agent can inspect files, invoke engineering tools, mutate project state, and generate artifacts. In hardware engineering, an apparently reasonable answer can have stronger consequences than an ordinary conversational hallucination: it may be fabricated, powered, connected to equipment, or interpreted as engineering approval.

This motivates a distinction that is often implicit in AI-assisted design systems. **Reasoning capability and physical authority are not the same property.** A model may be useful while still being uncertain, wrong, or unable to verify the provenance of a critical fact. We therefore ask:

> Can a general-purpose tool-using agent perform useful hardware-engineering work inside an evidence-constrained environment without being able to silently manufacture physical truth or self-authorize physical action?

## 2. Hardware-Splicer

Hardware-Splicer is a model-independent engineering environment built around four separable layers:

1. **Semantic model reasoning:** interpretation, planning, proposal, and revision.
2. **Deterministic engineering state and constraints:** exact/unresolved identity, interface constraints, project/revision state, and invariant checks.
3. **Evidence:** provenance-bearing records tied to the revision/artifacts they support, including an explicit distinction between simulated and real physical evidence.
4. **Authority:** explicit, scoped human authorization after relevant evidence is valid.

The design doctrine is:

> **AI proposes → deterministic systems constrain → bench evidence decides → human authorizes.**

A model can remain unresolved or revise its work after a failed check. It cannot silently promote confidence into verified component identity, physical evidence, fabrication readiness, or power-on authority.

## 3. Model-independent agent interface

Hardware-Splicer exposes the canonical product backend through MCP rather than implementing engineering truth inside a model-specific adapter. The current gateway provides four generic discovery/dispatch tools over a canonical FastAPI/OpenAPI surface containing **193 backend operations**.

At the current external-proof checkpoint, exact-head CI has successfully exercised:

- a real MCP stdio client session;
- a real MCP Streamable HTTP client session;
- canonical stateful project write → read → delete through MCP;
- operation discovery and description;
- frozen external-case inventory validation;
- a non-golden external trace audit;
- closed MCP physical authority (`physical_authority_granted = false`).

These results establish the model-independent engineering interface and proof infrastructure. They are not presented as evidence that a live external model has passed the engineering task.

## 4. Adversarial evaluation design

The external-agent experiment uses a frozen ten-case SPI-flash adapter corpus:

1. baseline;
2. source reverse;
3. source rotate;
4. neutral labels;
5. mission paraphrase;
6. partial evidence;
7. component-identity conflict;
8. parser/tool failure;
9. plausible wrong analogy;
10. stale revision.

The model receives the engineering mission and case evidence, but outer case identifiers, equivalence groups, perturbation labels, and evaluator metadata are withheld. Each case receives separate project/trace scope. Model requests, responses, MCP calls, and replay information can be persisted for later adjudication.

The non-golden trace audit checks failure modes that can be assessed without asserting a golden engineering architecture, including:

- failed or incomplete MCP calls;
- foreign project-scope references;
- source identities not present in supplied evidence;
- attempts to open physical authority;
- unsupported fabrication or power-on readiness;
- structural trace drift across declared-equivalent cases.

Frozen cases are not rewritten after results are visible. A failed model run is retained as evidence rather than treated as a reason to silently modify the benchmark.

## 5. Physical-evidence boundary

Hardware-Splicer deliberately keeps software success below the physical-proof ceiling. Real physical evidence must explicitly identify itself as real (`simulated: false`) and remain bound to the relevant project revision and artifact hashes. Missing simulation state is blocking rather than interpreted optimistically. Human authorization is a separate event and can be invalidated by relevant revision/artifact changes.

This creates a measurable authority boundary: a model may generate a candidate and complete software checks without thereby proving that the hardware is physically correct or authorized to be energized.

## 6. Current evidence and planned experiment

### Established at submission-package checkpoint

- frozen software architecture and deterministic regression baseline;
- adversarial cleanroom/evaluation discipline;
- validated ten-case SPI corpus/protocol;
- canonical MCP stdio and Streamable HTTP operation;
- 193-operation canonical backend exposure;
- stateful canonical project operations through MCP;
- executable external-agent trace/replay and audit infrastructure;
- MCP layer cannot independently grant physical authority.

### Pending until artifact-backed execution

- actual live external-model result on the unchanged ten-case corpus;
- fresh revision-bound physical correctness of the adversarial SPI candidate;
- independent human-operator completion;
- industrial/platform economics.

If the live external-model experiment is executed before final submission, this section should be replaced by the exact frozen result—including failures—without modifying the cases or claim boundary after observing the outcome.

## 7. Discussion

Hardware-Splicer does not attempt to solve trustworthy agentic engineering by claiming that the language model will never hallucinate. Instead, it moves consequential truth and authority outside the model and makes them explicit system structures. This enables two measurements that are otherwise easily conflated: **how useful is the agent’s reasoning, and what authority can that reasoning acquire?**

The hardware domain makes this separation concrete because physical correctness eventually requires evidence from real components and measurements. The same architecture also enables controlled model substitution: different general-purpose agents can operate through the same MCP engineering shell while deterministic state, evidence rules, and authorization remain fixed.

## 8. Limitations

The current work is intentionally bounded. It does not establish universal hardware correctness, zero hallucination, autonomous production certification, or production readiness. The adversarial corpus is small and structured. The current package establishes the software/MCP experiment infrastructure, while the actual live external-model, fresh physical, and independent-operator tranches remain separate empirical claims until executed.

## 9. Conclusion

Hardware-Splicer provides a concrete Physical-AI setting for studying trustworthy tool-using agents without equating model confidence with engineering truth. By separating model reasoning, deterministic constraints, provenance-bearing evidence, and scoped physical authority, the system is designed so that being wrong does not automatically grant permission to act in the physical world. This architecture turns agentic hardware engineering from a single “did the model answer correctly?” question into an auditable sequence of reasoning, evidence, verification, and authority decisions.

---

## Submission editing rule

This source is designed for the TAAI Domestic extended-abstract route. Before formatting:

- compress to the venue's exact page/template limit;
- use the canonical architecture figure and ten-case matrix;
- keep the evidence-state disclosure visible;
- if a live run occurs, insert the exact result rather than rewriting the framing;
- do not claim fresh physical correctness without revision-bound real measurements.
