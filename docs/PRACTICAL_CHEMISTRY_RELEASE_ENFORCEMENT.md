# Hardware Splicer Practical Chemistry — Release Enforcement

**Status:** implemented as a fail-closed, revision-scoped prototype on draft PR #169. Not deployed. No independent chemical safety certification or physical clearance.

## Enforcement surfaces

A shared project chemistry gate recomputes release blockers from the stored project snapshot, rather than trusting cached permission booleans or marketing claims. It validates project/revision/component/assessment digest, accepted finding provenance, and component existence in the MachineProject.

GET /v1/projects/{project_id}/engineering/release-gate:
- reads actual persisted MachineProject and chemistry screening results.
- reports assessment blockers and an explicit chemistry gate with codes.
- downgrades achieved release state to at most design_ready whenever chemistry assessment records exist and remain unverified.
- never authorizes a stale historical revision; a model-only standalone assessor explicitly labels its output unscoped.

Project physical-validation packet/evidence routes:
- expose the same chemistry release gate.
- still permit recording valid physical observations, but force audited and nested physical assessments to applicable=false and authorized_operations=[] while chemistry blocks.
- refuse treating an accepted project review as chemical/material safety verification.

Alternative engineering plan/audited physical-evidence persistence:
- recomputes the gate from the previously saved project snapshot.
- strips all nested and top-level scoped physical authorization, audited applicability, and ready-to-authorize flags from saved plans and their returned responses.
- retains accepted chemistry assessments through engineering-plan regeneration.

ProjectStore:
- generic project saves and staged-review acceptance cannot erase a previously assessed component's chemistry records.
- missing, altered or orphaned chemistry findings are blocked; missing components in newer machine models remain blockers.
- malformed chemistry history cannot simply be deleted by another revision.

No-chemistry projects remain governed by their usual electrical/mechanical/physical gates; the chemistry gate reports not_applicable.

## Tested scope

Cases include: (1) otherwise operationally authorized MachineProject restricted by chemistry; (2) stale release revision rejected; (3) tampered assessment and deleted finding detected; (4) attempted chemistry-record deletion by generic save and review acceptance denied; (5) engineering-plan regeneration retains chemistry and removes forged physical grants; (6) real HTTP attested inspection can save evidence while physical authorizations remain closed; (7) alternate nested plan audit permission lists blocked; (8) unchanged nonchemical flow still works.

Tests are simulated/synthetic engineering software acceptance checks, NOT physical chemistry experiments, product compatibility qualification, time-savings measurement or real technician review.

## Critical unresolved launch gates

1. No attested independent chemical-clearance workflow yet. The present policy intentionally holds physical authorization closed after an assessment is recorded. A real operator cannot automatically discharge that hold by marking a source verified, accepting a project review, or claiming a test passed.
2. Stateless engineering calculations, generated files and historical exports are not authoritative project release paths. UI integrations must consult the saved-project release gate.
3. Generic review APIs accept an actor string, not independent operator identity attestation. This cannot clear chemistry authorization.
4. Local file-system administrators can alter JSON artifacts outside the API; storage signatures and authorization are out of scope.
5. Physical specimen tests, manufacturer TDS/SDS content pinning, end-user/browser workflow, source freshness, complete deployment and measured economic benefits remain unverified.

Keep the PR draft until source-backed, measurement-linked and authenticated clearance is implemented and validated, along with cross-surface policy testing. The gate is safe against the tested bypasses but is not proof of universal production authorization enforcement.
