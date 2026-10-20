# Practical Chemistry — actual Hardware Splicer workflow audit

Checkpoint: October 20, 2026. Isolated chemical engineering branch in PR #169.
These are synthetic project and case fixtures, not independent physical
compatibility verification, production UI tests or measured economic uplift.

## Original architecture gap

HS practical chemistry worked through a standalone product API and MCP call.
Its results were not bound to a MachineProject component or revision, and
could disappear from the canonical project review and findings workflow.
A good decision algorithm alone does not establish workflow improvement.

## Integration delivered

The same canonical product FastAPI app exposes a revision-pinned preview:

    POST /v1/projects/{project_id}/chemistry/practical/preview

Request fields: expected_revision, component_id, assessment (the same input
model used by the preexisting practical chemistry assessment endpoint).

The endpoint loads the canonical HS ProjectStore/MachineProject and validates
the project revision, component identity and existing declared material
family. It rejects stale revisions, mismatched materials and missing components.

It returns an uncommitted candidate snapshot and the exact next-review
request body for the existing project-review API. It records a complete
chemistry assessment against a component, with an input-and-result digest and
source-specificity limitations. It also prepares deterministic observed-only
chemistry blockers in the existing HS engineering findings ledger.

Calling the preview does NOT mutate the accepted project. Creating a pending
full-snapshot project review still does NOT mutate the accepted revision.
After an explicitly submitted review acceptance the existing HS review store
creates a new project revision. The new findings appear in the existing
project findings endpoint and hash-verified review packet. Their provenance
is attested=false and authority ceiling observed; no physical action is
authorized.

Previously recorded component assessments are not silently discarded when
screening a second component. On reuse HS recomputes the older record's
project/revision/component/input/result digest and refuses tampered records.

## Measured integrated software results

Run from repo root:

    PYTHONPATH=src python eval/practical_chemistry/full_hs_workflow_benchmark_v1.py

Four authored case paths executed against the real FastAPI product app,
temporary ProjectStore, HS review API, finding ledger and review packet:

| Synthetic case | Chemistry decision | New accepted-revision chemistry findings |
|---|---|---:|
| Contaminated PCB with unknown nearby plastic | Research or replace | 2 |
| PP console housing bonding | Options for validation | 3 |
| Gold contact requiring no residue | Options for validation | 2 |
| Thermal pad under high heat load | Research or replace | 5 |

For all 4 cases: baseline contained zero chemistry findings; preview and
pending review did not mutate project revision 1; test-submitted acceptance
created revision 2, with source-scoped unverified chemistry findings including
at least one release blocker. Review packet cryptographic integrity verified.
No physical release or action authorization occurred.

Additional contract tests exercise both canonical API and MCP dispatch,
component mismatch, stale revision conflict, unverified source status,
multiple-component retention, and tamper rejection.

This demonstrates information continuity and review visibility. Findings
counts are output counts, NOT independent repair benefit measurements.

## Benefits actually demonstrated

- Correct project and part identity preserved across chemistry and review.
- Repair constraints, source-claim scope, failure modes and missing evidence
  retained in the same accepted revision as the rest of the engineering work.
- Existing staged review and review packet reused; no second chemical
  workspace or persistence layer.
- Old records with broken content digests cannot silently contaminate the
  next proposed review.
- Remaining unknowns and contraindications visible to subsequent reviewers.

## Significant limitations and open validation gates

1. No physical repair performed. None of the 4 cases validates product
   compatibility, true cure, electrical insulation or actual thermal
   performance.
2. No human UI/browser test, no technician usability evaluation, and NO
   measured time reduction, financial uplift or failure-rate improvement.
3. Indexed product/source statements are manufacturer/repair-page claims,
   not original TDS/SDS bytes freshly fetched, pinned and validated in
   this full-workflow experiment.
4. The legacy full-snapshot review API accepts an actor string; synthetic
   review acceptance does not prove a qualified reviewer authenticated or
   approved physical work.
5. Pending full-snapshot reviews are visible under the reviews endpoint;
   the review packet's candidate proposal section is a different type of
   proposal and does not include these pending reviews.
6. CRITICAL: The standalone MachineProject release assessor does NOT yet
   consume persisted practical chemistry blockers as compulsory global
   release-gate inputs. The new blockers appear in the findings ledger and
   review packet, but the audit does NOT prove that every downstream
   manufacturing/release route enforces them.
7. No autonomous photo-based diagnosis or independently grounded case
   classification tested; synthetic inputs are supplied as ground truth.

## Readiness decision

The v2 chemistry core is a FUNCTIONING integration prototype that improves
review continuity and carries actionable concerns into the same HS project.
It is not yet a field-validated repair decision engine or proven complete
physical workflow gate. The next acceptance step should verify real
sources/measurements, downstream release gating, authenticated reviews and a
guided UI with independent technicians, then measure actual time and repair
outcomes. Freeze unrelated general chemistry features until those gaps close.
