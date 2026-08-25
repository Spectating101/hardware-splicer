# TAS 2026 Short Paper Draft

## Hardware-Splicer: Keeping Tool-Using AI Agents Below the Physical-Authority Boundary

### Abstract

Tool-using language-model agents increasingly mutate external state rather than merely produce text. In hardware engineering, this creates a consequential distinction between an agent producing a plausible proposal and that proposal acquiring fabrication, power-on, or release authority. We present **Hardware-Splicer**, a model-independent engineering environment that separates semantic model reasoning from deterministic engineering state, provenance-bearing evidence, and scoped human physical authority. General-purpose agents operate the canonical backend through MCP, while exact project/revision state, source/evidence rules, physical-proof status, and authorization remain independently enforced. A frozen ten-case adversarial SPI-flash corpus tests partial/conflicting evidence, source-order perturbations, tool failure, plausible wrong analogy, and stale revision. The current proof infrastructure demonstrates real MCP stdio and Streamable HTTP operation over a 193-operation canonical backend, stateful project mutation/readback, trace/replay capture, and a closed MCP physical-authority boundary. We argue that trustworthy-agent evaluation should measure not only whether an agent is correct, but also whether uncertainty or error can silently acquire consequential authority.

## 1. Motivation

A common framing for trustworthy agents asks whether an agent follows instructions, uses tools correctly, or produces an accurate result. Consequential engineering adds another question: **what is the agent allowed to cause when its answer is uncertain or wrong?**

Hardware makes this boundary unusually concrete. A language model may plausibly identify a component, infer an interface, or suggest a wiring decision before the underlying evidence is sufficient. If the surrounding system treats fluent output as verified engineering state, a hallucination can cross into fabrication or power-on.

Hardware-Splicer is built around a narrower target than “make the model infallible”:

> **Being wrong should not automatically grant physical authority.**

## 2. System boundary

Hardware-Splicer separates four layers:

1. **Model reasoning:** semantic interpretation, planning, proposal, and revision.
2. **Deterministic state/constraints:** exact or unresolved identity, interface rules, tool/check results, and exact project revisions.
3. **Evidence:** provenance-bearing records tied to the revisions and artifacts they support, including explicit simulated-vs-real physical status.
4. **Authority:** a separate scoped human decision after relevant evidence is valid.

The resulting architecture is:

`general-purpose agent → MCP → canonical Hardware-Splicer backend → deterministic/evidence gates → candidate → human authority → physical world`

The model may inspect, propose, revise, block, or remain unresolved. It is not the authoritative source of component identity, physical evidence, or permission to energize hardware.

## 3. Model-independent tool use

The current MCP gateway is generated from the canonical FastAPI/OpenAPI product backend rather than reproducing engineering logic inside a model adapter. Four generic tools support backend status, operation discovery, operation description, and canonical operation invocation.

At the current proof checkpoint, exact-head CI has exercised:

- a real MCP stdio client;
- a real MCP Streamable HTTP client;
- canonical stateful project write → read → delete;
- 193 canonical backend operations;
- the external trace-audit harness;
- a closed MCP physical-authority state.

This separation makes the agent replaceable. Different general-purpose models can be tested inside the same engineering/evidence shell without changing the authority policy.

## 4. Adversarial evaluation

The external-agent proof uses a frozen ten-case SPI-flash adapter corpus containing:

- baseline;
- source reversal and rotation;
- neutral-label and mission-paraphrase variants;
- partial evidence;
- component-identity conflict;
- parser/tool failure;
- plausible wrong analogy;
- stale revision.

Outer case identifiers, perturbation labels, equivalence groups, and evaluator metadata are withheld from the model. Each case receives separate project and trace scope. The test harness preserves model requests/responses and MCP calls for replay.

A non-golden trace audit checks safety-relevant properties without pretending to know one universal correct hardware architecture. It can fail a trace for incomplete tool calls, foreign project scope, unsupported evidence identity, attempted authority opening, or unsupported fabrication/power readiness. Structural drift across declared-equivalent cases is retained as a review signal.

Frozen cases are not rewritten after outcomes are visible. Failure is evidence.

## 5. Physical evidence as an authority ceiling

Software success is deliberately below the physical-proof ceiling. Real physical evidence must explicitly declare `simulated: false`, remain tied to the exact revision/artifact boundary it validates, and precede human authorization. Missing simulation state is blocking rather than interpreted favorably. Relevant revision changes can invalidate earlier evidence or authorization.

This design prevents a green software workflow or fluent model answer from being relabeled as physical correctness.

## 6. Trustworthiness claim

Hardware-Splicer does not currently claim zero hallucination, universal correctness, production certification, or autonomous engineering approval. Its contribution is an explicit architecture for separating:

- agent capability;
- engineering truth state;
- evidence provenance;
- consequential authority.

The current software/MCP infrastructure is established. The live external-model corpus result, fresh adversarial SPI physical validation, and independent human-operator experiment remain separate pending claims until artifact-backed execution occurs.

## 7. Implications for trustworthy agent systems

The Hardware-Splicer case suggests a broader design principle for tool-using agents: **permissions should not be inferred from the agent's confidence in its own proposal.** Where tool use can produce consequential effects, independently maintained state, evidence, and authority can make failures inspectable and contain their downstream impact.

This reframes agent evaluation from a single outcome metric into at least two axes:

1. Was the agent useful/correct?
2. What authority could the agent acquire when it was not?

Hardware engineering supplies a concrete environment in which those axes can ultimately be grounded against physical measurements.

## 8. Conclusion

Hardware-Splicer is an experimental and product-oriented engineering shell for general-purpose AI agents in which deterministic truth, evidence, and human physical authority remain outside the model. The central claim is not that the AI will always be right, but that uncertainty and error should remain unable to silently become physical permission. This boundary provides a reusable basis for evaluating trustworthy tool-using agents in a consequential physical domain.

---

## Submission condition

This is a conditional route because TAS 2026 is fully in-person in Arlington, Virginia. Submit only if the paper/abstract can be formatted with low marginal work and downstream attendance cost is acceptable. If a live-agent result occurs before submission, report the frozen result—including failures—without modifying the corpus after observation.
