# DATE 2027 Late Breaking Results — Draft Source

## Late Breaking Results: Evidence-Constrained Agentic Engineering with Revision-Bound Physical Authority

**Status:** reserved source; do not finalize the Results section until substantive external-proof evidence exists.

### Abstract

AI agents are increasingly capable of invoking design and engineering tools, but physical workflows require a distinction between a model producing a plausible design and that design acquiring fabrication or power-on authority. Hardware-Splicer is a model-independent agentic hardware-engineering environment that keeps deterministic engineering state, provenance-bearing evidence, exact revision/artifact binding, and scoped human authority outside the model. The canonical engineering backend is exposed through MCP, enabling different general-purpose agents to operate the same 193-operation surface while retaining fixed evidence and authority rules. A frozen ten-case adversarial SPI-flash corpus covers source-order perturbations, partial evidence, component-identity conflict, tool failure, plausible wrong analogy, and stale revision. Current infrastructure establishes real MCP stdio and Streamable HTTP operation, stateful canonical backend access, and replayable external-agent traces while preserving closed MCP physical authority. The final LBR should report the first substantive live-agent and/or revision-bound physical result from this frozen experiment.

## 1. Problem and contribution

Agentic design automation is often evaluated by the quality of the generated artifact or completion of a tool workflow. In consequential hardware engineering, those metrics alone are insufficient. A plausible design can still depend on unresolved component identity, unsupported evidence, stale revisions, failed tools, or unmeasured physical assumptions.

Hardware-Splicer contributes an explicit separation between:

- model semantic reasoning;
- deterministic engineering constraints and project state;
- provenance/revision-bound evidence;
- human physical authority.

The system is designed so that model confidence cannot itself promote a candidate into verified physical truth.

## 2. Architecture

```text
General-purpose agent
       │
       ▼
      MCP
       │
       ▼
Canonical Hardware-Splicer backend
       │
       ├─ exact project/revision state
       ├─ source/evidence provenance
       ├─ deterministic interface constraints
       ├─ engineering artifacts/package
       ├─ revision-bound physical evidence
       └─ scoped authorization ledger
       │
       ▼
Candidate → evidence gates → human authority → physical world
```

The MCP gateway is generated from the canonical FastAPI/OpenAPI product surface rather than implementing a second engineering truth layer. This makes model substitution possible while preserving the same deterministic/evidence policy.

## 3. Experimental design

The frozen SPI-flash corpus contains ten cases:

1. baseline;
2. source reverse;
3. source rotate;
4. neutral labels;
5. mission paraphrase;
6. partial evidence;
7. identity conflict;
8. parser/tool failure;
9. plausible wrong analogy;
10. stale revision.

The model does not receive outer perturbation/equivalence metadata. Each case receives isolated project/trace scope. The harness persists model requests/responses and MCP calls and audits for:

- failed/incomplete calls;
- foreign project-scope references;
- unsupported source identities;
- attempts to open physical authority;
- unsupported fabrication/power readiness;
- structural drift across equivalent variants.

Frozen cases are not edited after outcomes are visible.

## 4. Infrastructure result already established

At the current external-proof checkpoint:

| Check | Result |
|---|---|
| real MCP stdio client | PASS |
| real MCP Streamable HTTP client | PASS |
| canonical project write → read → delete | PASS |
| canonical backend operations exposed | 193 |
| frozen ten-case inventory validation | PASS |
| external trace-audit infrastructure | PASS |
| MCP physical-authority grant | FALSE |

This establishes experiment infrastructure only. It is not the LBR's final empirical result.

## 5. Final Results section — fill only from canonical evidence

**Do not fabricate or prewrite positive numbers here.** When external proof exists, insert the exact frozen outcome.

Preferred result table:

| Case / family | MCP trajectory complete | unsupported-source violation | authority violation | unresolved-state behavior | outer engineering outcome | physical outcome |
|---|---:|---:|---:|---|---|---|
| [populate from run] | | | | | | |

Preferred additional measurements where available:

- model/provider/config and exact revision;
- tool-call count / failed calls;
- equivalent-case structural drift;
- human intervention count;
- candidate revision/artifact hashes;
- real measurement summary tied to `simulated:false` evidence;
- failure → repair → revalidation sequence.

A negative or mixed result is publishable evidence if the protocol remained frozen.

## 6. Physical authority boundary

Hardware-Splicer treats software success and physical correctness as separate claims. Real physical evidence must explicitly declare itself real, be bound to the exact revision/artifact candidate, and precede scoped human authorization. Missing simulation state is blocking. Relevant design changes can invalidate earlier evidence/authority.

This creates an authority-violation metric independent of whether the agent's final architecture is judged correct.

## 7. Discussion

The experiment tests a practical form of AI-native design automation in which agent capability can change without changing the engineering truth layer. This separation may allow cross-model evaluation under identical constraints and makes it possible to distinguish “the agent reached a useful answer” from “the system allowed an unsupported answer to become consequential.”

The bounded semiconductor validation-support domain provides a realistic bridge between agentic AI, electronic-system design/test workflows, and physical evidence.

## 8. Limitations

The final submission must retain these limitations unless evidence changes them:

- bounded hardware domain;
- small structured adversarial corpus;
- no universal hardware-correctness claim;
- no zero-hallucination claim;
- no autonomous production-certification claim;
- industrial economics unproven until external cases exist.

## 9. Conclusion

Hardware-Splicer provides a model-independent architecture for agentic hardware engineering where deterministic state, evidence provenance, and physical authority remain explicit and independently auditable. DATE LBR should be used to report the first substantive frozen live-agent/physical result from this architecture, not merely to restate that the infrastructure exists.

---

## Finalization gate

Do not submit this LBR unless the final two-page paper contains a substantive empirical result beyond the already-proven MCP transport infrastructure. Preferred trigger: live external-model ten-case evidence, fresh revision-bound SPI physical evidence, an independent-operator result, or a controlled cross-model comparison.
