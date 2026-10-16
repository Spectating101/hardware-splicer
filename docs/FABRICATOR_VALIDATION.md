# Frozen fabricator validation

This layer makes physical validation repeatable without letting an agent rewrite acceptance criteria after seeing the result.

## Model

A `ValidationProcedure` is registered by trusted server/human configuration and binds:

- project id;
- candidate revision;
- ordered validation steps;
- requirement ids each step validates;
- required physical-evidence kind and target ids;
- bounded criteria (`numeric_range`, `equals`, `text_contains`, `text_not_contains`).

The canonical procedure is hashed. Criteria are immutable after registration.

## Evidence binding

An evaluated `PhysicalEvidenceRecord` must:

- belong to the same project;
- belong to the same candidate revision;
- identify its frozen `validation_step_id`;
- carry the exact `validation_procedure_sha256` in metadata.

The agent-facing API accepts evidence ids only. It does not accept measurement values, thresholds, criteria, evidence payloads or procedure definitions.

## Verdict recomputation

`ValidationProcedureEvaluator` recalculates each criterion from the retained evidence `measured_values`.

If an evidence record says `passed=true` but the frozen criteria recompute to failure, HS treats the step as failed and records an inconsistency blocker.

Exactly one retained evidence record is required per frozen step. Missing/duplicate evidence, wrong evidence kind, wrong targets, stale procedure hash or wrong candidate revision prevents the scope from passing.

`validation_scope_passed=true` means only that every step in this specific frozen procedure passed. It does not claim global/whole-device physical correctness and grants no physical authority.

## Agent surface

`/v1/fabricator/validation/*` is fail-closed until a server-owned `FabricatorValidationWorkbench` is configured.

Agent operations are intentionally limited to:

- list frozen validation procedures;
- evaluate retained evidence ids against one frozen procedure.

There is no agent route to create/edit procedures, change thresholds, supply raw measurement values, or mint authority.

The bounded MCP/OpenAPI projection is `fabricator_validation_manifest()`.
