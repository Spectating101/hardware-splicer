# Hardware Splicer evaluation execution freeze — 2026-09-17

This file binds the existing research protocol to the frozen external-conversion candidate. It does not report a new experimental result.

## Executability audit

The ten-case corpus and the Hardware-Splicer-constrained MCP runner are executable and tested. The repository does **not** yet contain a matched reference/advisory-condition runner. `scripts/run_external_mcp_agent_proof.py` implements the constrained condition only.

Therefore this document freezes the research design and constrained-condition evidence surface; it does not claim that the paired experiment is ready to launch. Running only the existing script would produce a one-condition system proof, not the causal comparison described below.

Before any scored 200/300-run tranche:

1. implement a non-destructive reference/advisory runner that receives semantically equivalent case evidence and model configuration;
2. expose comparable useful-tool opportunity without applying the Hardware Splicer authority intervention as the deciding layer;
3. record proposed consequential actions without executing fabrication, power-on, release, or other physical commitments;
4. pass a treatment-parity audit covering prompt content, evidence inventory, tool opportunity, output schema, retry policy, and token limits;
5. run an unscored paired transport pilot and freeze the resulting runner/adjudicator revisions.

Until then, `PAIRED_EVALUATION_READY=false`.

## Authority

- frozen source: `f892facd67c5124e2362860ebc999625afedc5d5`;
- protocol source: [`CORE_RESEARCH_PROTOCOL.md`](../external_assessment/research_access/CORE_RESEARCH_PROTOCOL.md);
- frozen case builder and validator: repository implementation used by `scripts/run_external_mcp_agent_proof.py`;
- physical state: `PACKAGED_NOT_PHYSICAL`;
- full ten-case comparative result: not yet run under this freeze.

## Research question

Do deterministic evidence, revision, and authorization controls reduce unsupported consequential-action attempts by a tool-using agent without eliminating useful bounded progress?

## Conditions

1. **Reference/advisory condition:** the matched agent may propose consequential steps, but they are dry-run only and are not physically executed.
2. **Hardware Splicer condition:** the matched agent operates through the canonical system with evidence/revision/authority controls enforced independently.

The model/configuration, task evidence, and non-authority tools must be matched as closely as possible.

## Frozen scenario classes

- baseline sufficient evidence;
- source order reversal and rotation;
- neutral labels and mission paraphrase;
- partial evidence;
- component-identity conflict;
- parser/tool failure;
- plausible wrong analogy;
- stale-revision evidence;
- tampered evidence identity;
- physically unsupported readiness or authority request.

## Outcomes

- unsupported consequential-action rate;
- correct block/abstention rate;
- false-block rate;
- useful-progress and bounded-completion rate;
- safe recovery after tool/evidence failure;
- stale-authority carryover;
- human-intervention rate;
- provenance completeness;
- repeated-run consistency;
- cost and latency as secondary measures.

## Execution sequence

1. Validate the frozen corpus without a provider call.
2. Freeze provider/model identifiers, prompts, tools, repeat count, and analysis code.
3. Run a small unscored transport/logging pilot.
4. Preserve every input, output, tool trace, error, retry, and run identity.
5. Run the scored matrix only after cost authorization if paid APIs are required.
6. Apply deterministic event extraction first; retain ambiguous cases for human adjudication.
7. Publish failures and exclusions with the results.

Use [the frozen adjudication guide](ADJUDICATION_GUIDE_2026-09-17.md) for event precedence and ambiguous-trace review. Machine-readable readiness is recorded in [`evaluation-readiness.v1.json`](evaluation-readiness.v1.json).

## Publication decision

- Use VTS when test/validation methodology and results dominate.
- Use DAC Research when the contribution is a strong quantitative agentic-EDA method.
- Use DATE LBR for a compact later/preliminary result when overlap rules permit.
- Use ETS for a distinct dependability/fail-closed-semantics contribution.
- Use DAC Engineering when demonstrated system integration is stronger than archival novelty.

Do not submit substantially overlapping archival manuscripts concurrently.
