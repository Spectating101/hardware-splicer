# Fabricator convergence: canonical truth and authority ownership

Status: C0 convergence contract for `agent/fabricator-convergence-v0`.

This note exists to prevent the donor/mission line and the fabricator/lab line from creating parallel truth stores while they converge. A new subsystem may project, index or compare canonical records, but it must not silently become a second owner of the same fact.

## Canonical ownership map

| Concept | Canonical owner | Convergence rule |
| --- | --- | --- |
| Mission intent, mission state, accepted candidate and terminal verdict | `mission_store.py` event/replay model | Fabricator services may consume mission identity/state; they do not rewrite terminal mission truth. |
| Project snapshot and candidate revision lineage | `ProjectStore` + engineering review/revision workflow | Revisions change through the reviewed project path. Physical or agent services may propose a revision, never silently mutate one. |
| Donor identity and interface contract | project-local donor contracts resolved by `mission_donors.py` | The convergence resource graph is a read-only projection. It does not copy donor contracts into a new database. |
| Donor electrical/dimensional physical evidence | canonical `PhysicalEvidenceEnvelope` records in the project physical-validation ledger | P4/P5 findings and model inference cannot promote themselves to measurement. `mission_donors.py` recomputes usable grades from canonical evidence. |
| P5 reverse-engineering findings | mission event/history as non-promoting re-observations | Findings can guide investigation and requests; they are not contract truth or physical measurement. |
| Raw physical observations | `physical_observation_store.py` | Raw bytes/hashes remain observations until explicit evidence promotion. |
| Promoted physical evidence | `physical_feedback.py` / canonical physical-evidence model | Promotion requires procedure, target, acceptance criteria and revision binding. |
| Engineering artifacts | `engineering_artifact_store.py` and the fabricator digital thread | An engineering artifact is non-executable unless a later bounded transform creates an exact physical artifact. |
| Executable physical artifacts | `physical_artifact.py` registry | Approval binds the exact executable artifact/hash and target; mission name or successful generation is insufficient. |
| Physical execution plan and human authority | `physical_operator.py`, `physical_approval.py`, `physical_authority.py` | Scheduling, leases, model output and mission readiness never grant actuation authority. |
| Tool/lab capability availability | server-owned `FabricationCapabilityRegistry` | Agent input may request capabilities, but cannot register endpoints, credentials or a new machine identity. |
| Lab scheduling and reservations | `fabrication_workflow_scheduler.py` + `fabrication_resource_leases.py` | A lease reserves a resource only. It is not a physical grant. |
| Supplier price/stock observations | `ProcurementQuoteBook` server/provider snapshots | Agents can consume quotes but cannot ingest a quote or purchase. |
| Clean/reclaim/hybrid comparison | `FabricationOptionTradeoff` | Comparison is derived from retained inputs and returns a Pareto frontier; it does not select an automatic winner. |
| Revision proposal after physical failure | `physical_revision_proposal.py` feeding reviewed project revision | Failed evidence may ground a proposal. The proposal cannot reopen/mutate an accepted revision by itself. |
| Agent/MCP projections | bounded manifests over the canonical APIs | Projection exposes stable IDs/schemas only; it owns no engineering or physical truth. |

## New convergence resource graph

The C2 resource graph is deliberately a **projection**, not a store.

It may combine:

- donor capabilities recomputed by `mission_donors.read_donors()` from project-local contracts and canonical physical evidence;
- server-configured fabrication/lab resources from `FabricationCapabilityRegistry`;
- later catalog/material/human resources only when their own canonical owner is explicit.

The graph must retain the source resource ID, support/evidence class, weakest donor evidence grade, unresolved facts, availability and geometry/interface constraints where canonical data exists.

It must not:

- promote an agent hypothesis;
- replace the donor contract;
- invent a scalar confidence score that erases evidence class;
- turn server configuration into physical evidence;
- turn availability or reservation into actuation authority;
- persist a copied donor capability as independent truth.

Architecture options may reference graph resource IDs. When they do, donor dependency count, unavailable-resource burden and unresolved-resource facts are derived by HS rather than trusted from agent-supplied counters.

## Convergence invariants

1. **One fact, one owner.** Projections may be regenerated; canonical facts are updated only through their owning workflow.
2. **Weaker evidence never upgrades stronger semantics.** Model inference, re-observation, documents and person measurements remain distinguishable.
3. **Artifact success is not physical correctness.** Compile/DRC/slice/export/dispatch success cannot establish that the physical object works.
4. **Reservation is not authority.** A scheduler allocation or lease cannot energize, move, flash or fabricate.
5. **Revision boundaries are sticky.** Evidence, executable artifacts and approvals remain bound to the revision/hash they were created for.
6. **Unknown remains useful but unknown.** A partially understood donor may contribute bounded capabilities without being forced into a complete identity.
7. **Agent counters are advisory at most.** Where HS can derive a quantity from canonical resource references, HS derives and checks it.

C0 is complete when this ownership map remains true on the converged branch and no integration shim introduces a second truth/authority owner. C2 is complete when donor capabilities can participate in architecture comparison through the read-only resource projection while unresolved donor facts remain visible and fail closed.