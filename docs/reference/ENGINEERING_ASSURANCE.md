# Engineering assurance

Hardware Splicer's assurance surface answers three questions from canonical project state:

1. Which source claim supports each engineering requirement, candidate, decision, action,
   or blocker?
2. Which exact outputs become stale or blocked when an identified source or claim changes?
3. Which source transcriptions have received independent review, without confusing that
   review with physical correctness or authorization?

It is a read-only projection except for claim-review submissions. It does not introduce a
second evidence store, infer undeclared dependencies, promote evidence authority, or grant
fabrication, power-on, motion, operational, or release authority.

## Product API

The canonical product API and MCP gateway expose:

- `GET /v1/projects/{project_id}/engineering/assurance`
- `GET /v1/projects/{project_id}/engineering/assurance/review-packet`
- `POST /v1/projects/{project_id}/engineering/assurance/evidence-delta`
- `POST /v1/projects/{project_id}/engineering/assurance/reviews`

For agent workflows, `hs_backend_task_manifest("bounded_pre_fabrication")` returns the exact
OpenAPI-derived contracts for the relevant project, plan, assurance, delta, and package
operations in one call. It is a context projection only; every mutation still re-enters the
canonical API handler.

The assurance view contains the source identity, revision/hash, locator, extraction method,
authority ceiling, review state, downstream output IDs, reference-integrity findings,
conflicts, blockers, and existing readiness state.

The independent review packet deliberately excludes candidates, decisions, and agent
conclusions. A reviewer receives only the frozen source identity, locator, paraphrase, and a
response slot for `SUPPORTED`, `PARTIAL`, `WRONG`, or `AMBIGUOUS`.

A review submission is an optimistic, revisioned project transaction. It records the
reviewer's declared identity and response, but leaves `independent_signoff=false` and has
`authority_effect=none`. Reviewer identity is not cryptographically attested by this route.

## Evidence delta

The delta endpoint accepts explicit changed or unresolved source/claim IDs. It can also
derive changed identities by comparing two stored project revisions. The existing
conservative evidence-impact engine then classifies dependent claims and engineering
outputs as:

- `invalidated` when a declared dependency changed;
- `blocked` when dependency coverage or an upstream dependency is unresolved;
- `retained` when every declared dependency is unchanged.

Missing dependency declarations never count as proof that an output remains valid. Delta
evaluation is diagnostic only and cannot authorize an output.

Example request:

```json
{
  "base_revision": 3,
  "candidate_revision": 4,
  "changed_source_ids": ["src-dut-datasheet"]
}
```

For offline inspection of a filesystem-backed project:

```bash
python scripts/export_project_assurance.py \
  --project-root /path/to/projects \
  --project-id my-project \
  --kind review-packet
```

The output is derived from the requested revision and is not persisted unless a caller
explicitly stores it as an external report.
