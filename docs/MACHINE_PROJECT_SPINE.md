# Canonical machine project spine

Hardware Splicer stores one traceable machine project per build. PCB, mechanical,
firmware, sourcing, assembly, splice and bench data attach to that project as
discipline payloads instead of becoming competing project formats.

This document covers the persistent project layer shipped after
[`INTEGRATION_STACK.md`](INTEGRATION_STACK.md): the canonical model, durable
revisions, semantic diffs, and the staged review workflow that guards them.

## Ownership boundary

The spine owns:

- project identity and revision history;
- cross-discipline structure (subsystems, components, requirements, constraints);
- authority state per engineering claim;
- release assessment and its blockers;
- which candidate edits may become the next durable revision.

The spine does **not** own compile output, DRC/ERC truth, bench measurements, or
firmware artifacts. Those remain with their existing subsystems and are attached
as payloads.

## Core doctrine

**Authority is never implicitly upgraded.** Importing, seeding, composing,
diffing, or reviewing a project reports state — none of them promote a claim.
Release assessment reports blockers rather than silently marking a project
build-ready or operationally authorized.

## Ontology

Four enums carry the semantics. They live in `machine_project.py` and are shared
by API, UI, and future CI gates.

| Enum | Values |
|------|--------|
| `Domain` | `system`, `mechanical`, `electrical`, `firmware`, `software`, `sourcing`, `assembly`, `verification` |
| `AuthorityState` | `unknown` → `proposed` → `declared` → `observed` → `measured` → `verified` → `authorized` |
| `LifecycleState` | `intake` → `architecture` → `design` → `verify` → `bench` → `package` |
| `ReleaseState` | `concept` → `design_ready` → `build_ready` → `bench_ready` → `operationally_authorized` |

`RequirementKind` classifies requirements as `functional`, `performance`,
`safety`, `interface`, or `constraint`.

Release authority is **monotonic**: evidence supporting a higher state also
satisfies a lower requested state (`machine_release.release_state_satisfies`).
Blockers always win — see `assessment_allows` for the single permission rule
shared by API, UI and CI.

## Modules

| Module | Role |
|--------|------|
| `machine_project.py` | Canonical model and ontology (`hardware_splicer.machine_project.v1`) |
| `machine_project_seed.py` | Deterministic seed from project intake |
| `machine_project_diff.py` | Identity-aware semantic diff |
| `machine_project_compile_adapter.py` | Projection from compile spec |
| `machine_release.py` | Release-state ordering and the permission rule |
| `project_store.py` | Durable revisions (`hardware_splicer.project_snapshot.v1`) |
| `project_review_store.py` | Staged review workflow (`hardware_splicer.project_review.v1`) |
| `project_api.py` | `/v1/projects` — persistence and review |
| `machine_project_api.py` | `/v1/machine-projects` — model, seed, diff, release |

Seeding is deliberately conservative: it creates purpose, requirements,
subsystems, components and declared constraints, but never invents pin mappings,
mechanical fits, firmware behavior, or verification evidence.

## Semantic diff

The diff is identity-aware rather than line-oriented. It reports engineering
object additions/removals, field changes, and **authority transitions**, so human
or agent edits can be reviewed before replacing a persisted revision.

Changes carry a `ReviewSeverity` of `info`, `warning`, or `required`. A diff
never grants authority; it only reports what changed and what demands explicit
review.

## Staged review workflow

Candidate snapshots are stored **outside** revision history until explicitly
accepted. A review decision never upgrades engineering authority — it only
controls whether a candidate may become the next durable revision.

Review status lifecycle:

```text
pending ──accept──> accepting ──> accepted
   └─────reject───> rejected
```

`accepting` is a journaled intermediate state. If the process dies mid-accept,
`_reconcile_accepting` replays the journal on next load so the workflow resumes
rather than stranding the candidate. The event log is append-only.

Review covers the **entire candidate snapshot**, not only machine fields — a
change to any part of the snapshot surfaces in the console.

### Concurrency

`project_store` raises `RevisionConflict` when `expected_revision` does not match
the stored revision; `project_review_store` raises `ReviewConflict` for a
decision against a review that has already moved on. Both surface as a stable
API error contract — clients may rely on the shape.

## API surface

`/v1/projects`

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `""` | List projects (`include_archived`) |
| `GET` | `/{project_id}` | Load a project |
| `PUT` | `/{project_id}/snapshot` | Save snapshot (optimistic `expected_revision`) |
| `GET` | `/{project_id}/revisions` | Revision history |
| `POST` | `/{project_id}/duplicate` | Duplicate |
| `DELETE` | `/{project_id}` | Delete |
| `GET` | `/{project_id}/reviews` | List reviews |
| `POST` | `/{project_id}/reviews` | Open a review for a candidate |
| `GET` | `/{project_id}/reviews/{review_id}` | Load a review + diff |
| `POST` | `/{project_id}/reviews/{review_id}/decision` | Accept or reject |

`/v1/machine-projects`

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/schema` | Canonical schema |
| `POST` | `/validate` | Validate an envelope |
| `POST` | `/from-intake` | Seed from intake |
| `POST` | `/from-compile-spec` | Project a compile spec |
| `POST` | `/from-session` | Migrate a legacy session |
| `POST` | `/diff` | Semantic diff |
| `POST` | `/assess-release` | Release assessment + blockers |

## Frontend

`apps/splice-ui/src/projectSession/` holds the durable workspace:
`projectPersistence.js` (revision save/load), `projectReviewApi.js` (browser
client), and `projectSession.js`. `ProjectWorkspace.jsx` mounts
`ProjectReviewPanel` (revision review console) and `MachineArchitecturePanel`
(cross-discipline structure).

Review traffic is suppressed until a durable revision actually exists, so a fresh
project does not emit review calls against nothing.

## Verification

```bash
pytest -q \
  tests/test_project_store.py \
  tests/test_project_review_store.py \
  tests/test_project_api.py \
  tests/test_project_review_api.py \
  tests/test_machine_project.py \
  tests/test_machine_project_diff.py \
  tests/test_machine_project_diff_review_flags.py \
  tests/test_machine_release.py
```

Frontend: `make splice-ui-build`.

## Authority invariants

1. Seeding, importing, or migrating never upgrades an authority state.
2. A diff reports authority transitions; it does not perform them.
3. Accepting a review promotes a **snapshot to a revision**, never a claim to a
   higher authority.
4. Release assessment reports blockers; blockers always outrank achieved state.
5. Release authority is monotonic — one ordering rule shared by API, UI and CI.
6. Review acceptance is journaled and crash-recoverable; a partial accept
   resumes rather than silently dropping or double-applying.
7. The review event log is append-only.
8. Revision and review conflicts raise a stable, documented error contract.
