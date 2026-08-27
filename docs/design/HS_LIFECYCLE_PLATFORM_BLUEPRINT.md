# Hardware-Splicer Lifecycle Platform — Design Blueprint

**Status:** design only — no implementation authorized by this document  
**Date:** 2026-08-28  
**Branch:** `design/refurb-lifecycle-blueprint-20260828`  
**Upstream:** `agent/submission-package-2026q3`

## 0. Decision summary

Hardware-Splicer should not become a generic second-hand marketplace or another repair-guide site.

The defensible extension is an **evidence-native lifecycle layer for repaired, refurbished, modified, and repurposed hardware**. Hardware-Splicer remains the engineering truth/evidence producer. The lifecycle platform stores and projects what happened to an individual physical unit, what evidence supports its current state, which transformation procedure was used, what warranty/service obligations exist, and what an authorized human or AI agent may infer from that record.

The first target is a **single-unit lifecycle proof**, not a marketplace:

> commodity keyboard → HS donor intake → split-keyboard transformation → revision-bound validation → unit passport → reusable transformation recipe → agent-readable service context → sale-style listing projection

The platform must be architected so that the same evidence core can later support refurbishment shops, reseller listings, warranties, repair/service agents, third-party verification, or Digital Product Passport (DPP) integrations without making those commercial surfaces authoritative.

---

# 1. Problem definition

Current used/refurbished-hardware systems normally optimize one of three things:

1. **Certification of an existing standardized device** — diagnostics, grading, data erasure, lock status, battery condition.
2. **Lifecycle/compliance identity** — Digital Product Passports and supply-chain traceability.
3. **Repair knowledge** — human-readable guides and parts/tool instructions.

Hardware-Splicer has a different native asset: **the engineering transformation record**.

For a transformed unit, a buyer, technician, insurer, agent, or future owner may need to know:

- what physical donor product(s) this unit came from;
- which original components were retained, rejected, removed, or substituted;
- what destructive operations were performed;
- why those operations were considered safe/appropriate;
- what new components were added;
- which measurements/tests were performed;
- which exact revision/artifacts those measurements validate;
- what failures occurred and what repairs followed;
- what remains unresolved;
- what current functionality is evidenced;
- what warranty/service scope applies;
- which known transformation recipe or procedure family applies;
- how an AI agent may troubleshoot this exact unit without hallucinating generic hardware history.

A normal marketplace description cannot answer this reliably. A generic repair guide cannot answer it for an individual modified unit. A model-level product passport cannot by itself capture the detailed engineering transformation chain.

---

# 2. Product boundary

## 2.1 Hardware-Splicer Core — authoritative engineering source

Existing HS responsibilities remain authoritative:

- donor intake and functional salvage;
- exact/unresolved identity;
- interface contracts;
- evidence provenance;
- engineering/project revision state;
- deterministic constraints;
- physical evidence;
- human authority;
- capability/reuse analysis;
- splice plans and build artifacts.

The lifecycle platform **must consume these states; it must never reinterpret a weaker HS state as a stronger commercial claim**.

Example:

`interface_status = PARTIAL` must not become `fully tested` merely because a listing template wants a simple badge.

## 2.2 Lifecycle Registry — append-only record of what happened

Stores unit identity and lifecycle events:

- acquired/intake;
- inspected;
- disassembled;
- component removed;
- component attached;
- repaired;
- transformed/spliced;
- firmware changed;
- tested;
- failed;
- reworked;
- verified;
- listed;
- transferred/sold;
- warranty opened;
- serviced;
- returned;
- retired/recycled.

Corrections are new events. Historical events are not silently edited away.

## 2.3 Unit Passport — human + machine-readable projection

The passport is a **view**, not a second truth store.

It resolves one physical unit to:

- identity;
- origin/donor lineage;
- current configuration;
- component provenance;
- transformation history;
- current verified capabilities;
- open limitations;
- test evidence;
- warranty/service state;
- relevant recipe/procedure;
- public/private access links.

## 2.4 Recipe Registry — reusable transformation knowledge

A recipe is **not a fixed tutorial**.

It is a versioned transformation family containing:

- applicability conditions;
- donor archetypes;
- known incompatible variants;
- required observations;
- required tools/instruments;
- preconditions;
- decision branches;
- evidence gates;
- allowed physical operations;
- expected new parts;
- validation protocol;
- failure modes;
- known completed instances;
- transferability/reuse metrics;
- superseded versions.

HS still adapts the recipe to the actual donor.

## 2.5 Listing / Warranty / Service projections — non-authoritative commerce views

These views translate evidence into ordinary customer language without changing the evidence state.

Examples:

- cosmetic grade;
- functional grade;
- verified battery health;
- replacement-part disclosure;
- tested capabilities;
- remaining known limitations;
- warranty duration/scope;
- service contact;
- expected use case;
- listing export.

## 2.6 Marketplace — explicitly out of scope for initial design

Do not build inventory liquidity, checkout, seller onboarding, payments, shipping, dispute resolution, or returns until evidence shows that HS passports/recipes create demand independent of owning the marketplace.

Existing marketplaces can be treated as downstream channels.

---

# 3. External standards and interoperability posture

The platform should be **DPP-compatible by architecture**, not marketed as EU-DPP compliant until an applicable product-group delegated act and conformity analysis says so.

Design for the following external patterns:

## 3.1 Persistent item identity

Every physical unit receives a persistent item-level identifier.

Initial internal form:

`urn:hs:unit:<uuid>`

Public resolver form:

`https://id.hardware-splicer.example/u/<unit-id>`

Later adapters may support GS1/EN 18219-compatible identifiers where commercially justified.

Rules:

- identity survives resale and service;
- identifier is never reused;
- replacement unit receives a new identity;
- donor unit identities remain linked rather than overwritten;
- public serial numbers/IMEIs are not exposed by default.

## 3.2 QR / data carrier

A QR code or other data carrier resolves the physical object to its passport.

The QR should contain a stable resolver URI, not all passport data.

The resolver may return different resources/content types:

- consumer passport page;
- machine JSON/JSON-LD;
- service view;
- warranty view;
- provenance/evidence bundle;
- recall/safety notice;
- recipe lineage.

This mirrors the core design logic of GS1 Digital Link: one persistent identity, multiple context-specific digital resources.

## 3.3 Lifecycle events modeled compatibly with EPCIS concepts

Use an internal event model that can project into GS1 EPCIS 2.0 where useful.

Especially important:

- **Object-like event** — unit observed/tested/moved/graded;
- **Association-like event** — component attached/detached from a unit;
- **TransformationEvent-like semantics** — donor inputs become one transformed output;
- sensor/measurement observations;
- certification/attestation references.

The donor → transformed-unit relation should never be represented as an unstructured note if it can be represented as explicit input/output lineage.

## 3.4 Structured open data

Use conventional JSON as the canonical application representation.

Provide JSON-LD projection where semantic interoperability is useful.

Do not force the whole implementation to depend on RDF tooling.

## 3.5 Cryptographic claim integrity

Phase 1 may use signed server-generated attestations and content hashes.

Architecture should allow later projection into:

- W3C Verifiable Credentials 2.0 for issuer/holder/verifier use cases;
- GS1 Digital Signatures / JSON-LD claims;
- other open attestation formats.

Do not use blockchain merely to say records are immutable. A signed append-only event/attestation chain with strong identity, authorization, backups, and auditable corrections is sufficient unless a multi-organization trust problem later justifies a distributed system.

---

# 4. Canonical domain model

## 4.1 `AssetUnit`

Represents one physical object.

Minimum fields:

```text
unit_id
unit_type
manufacturer
model
manufacturer_serial_ref_private
origin_state
current_revision
current_owner_ref_private
created_at
retired_at
public_visibility
```

Important distinction:

- manufacturer identity = what the donor originally was;
- HS identity = this individual lifecycle object;
- current product identity = what the transformed unit is now.

## 4.2 `ComponentInstance`

One individually tracked retained/replacement component where tracking adds value.

```text
component_instance_id
part_identity
origin: donor_original | donor_other | new | unknown
source_unit_id
installed_on_unit_id
installed_at_revision
removed_at_revision
identity_evidence
condition_state
```

Do not serialise every resistor by default. Track at the granularity needed for service, claims, regulation, or high-value reuse.

## 4.3 `LifecycleEvent`

Append-only occurrence in physical history.

```text
event_id
event_type
timestamp
actor_id
facility_id?
unit_ids
input_unit_ids?
output_unit_ids?
component_ids?
project_revision_before
project_revision_after
evidence_refs
attestation_refs
notes
supersedes_event_id?
```

Event types should be explicit and controlled.

## 4.4 `TransformationRecord`

Special lifecycle record for refurbish/repair/splice work.

```text
transformation_id
input_units
output_unit
recipe_ref?
hs_project_id
baseline_revision
final_revision
retained_components
removed_components
added_components
physical_operations
failures
repairs
verification_summary
open_limitations
```

For the split-keyboard case, the original keyboard is an input unit and the final split keyboard is either:

- the same lifecycle identity with a major-transformation revision, or
- preferably a new output identity linked to the donor input when the product function/form materially changes.

Default blueprint recommendation: **new output unit identity for major transformation; retain full donor lineage.**

## 4.5 `EvidenceClaim`

A commercial/customer-visible statement must resolve back to explicit evidence.

```text
claim_id
subject_unit_id
predicate
value
status: PROVEN | PARTIAL | UNVERIFIED | REJECTED | EXPIRED
issuer
method
project_revision
evidence_refs
valid_from
valid_until?
superseded_by?
```

Example:

`right_half_all_keys_functional = true`

must link to a defined test run, not a seller text field.

## 4.6 `TestRun`

```text
test_run_id
protocol_id
protocol_version
unit_revision
operator
instrument_refs
started_at
completed_at
raw_artifact_hashes
result
failed_checks
passed_checks
```

Tests should be reproducible enough that another technician can understand what `PASS` means.

## 4.7 `Actor` / `Facility` / `Instrument`

Track who/what created evidence where relevant.

Evidence assurance should distinguish:

- `SELF_REPORTED`
- `OPERATOR_OBSERVED`
- `MACHINE_OBSERVED`
- `INSTRUMENT_MEASURED`
- `AUTOMATED_PROTOCOL`
- `INDEPENDENT_VERIFIED`

These are provenance classes, not universal quality rankings.

## 4.8 `RecipeFamily` and `RecipeVersion`

```text
recipe_family_id
recipe_version
transformation_goal
applicability_constraints
donor_archetypes
incompatible_variants
required_observations
required_tools
required_measurements
decision_graph
physical_operation_templates
new_parts_policy
validation_protocol
known_failure_modes
validated_instance_refs
status: DRAFT | OBSERVED | REPLICATED | DEPRECATED
```

Recipe maturity:

- `DRAFT` — proposed procedure, no completed unit;
- `OBSERVED` — one artifact-backed completed unit;
- `REPLICATED` — multiple sufficiently independent completed units;
- `DEPRECATED` — superseded/unsafe/obsolete.

Do not call a one-off successful build a universally proven recipe.

## 4.9 `WarrantyPolicy` and `WarrantyCase`

Warranty is separate from engineering verification.

```text
policy_id
seller_or_provider
coverage_start
coverage_end
covered_capabilities
exclusions
transferable
service_process
```

A warranty claim may consume passport evidence but must not modify historical engineering evidence.

## 4.10 `ListingProjection`

Generated, non-authoritative view of current unit state.

Separate at minimum:

- cosmetic condition;
- functional condition;
- evidence depth;
- modifications;
- replacement/retained parts;
- known limitations;
- warranty.

Avoid one overloaded Grade A/B score.

---

# 5. Trust and integrity model

## 5.1 One-way authority

```text
HS engineering/evidence state
          ↓
lifecycle events + attestations
          ↓
unit passport / recipe evidence
          ↓
listing / warranty / agent views
```

Nothing downstream may automatically promote upstream truth.

## 5.2 Append-only history

Events should not disappear because a later repair succeeds.

Correct pattern:

```text
2026-09-03 post-cut ROW4 continuity FAIL
2026-09-03 jumper J04 installed
2026-09-03 ROW4 continuity PASS
```

Incorrect pattern:

```text
ROW4 PASS
```

with the failure silently erased.

## 5.3 Evidence binding

Every consequential evidence object should bind to:

- unit identity;
- project/unit revision;
- relevant component/artifact hashes when possible;
- protocol version;
- actor/tool/instrument identity where relevant;
- timestamp;
- raw evidence artifact or digest.

## 5.4 Public claims are projections

A customer may see:

> All keys verified after split conversion.

An agent/service technician may see:

```text
claim → test protocol → 87 expected scan codes → 87 passed
          ↓
firmware hash
PCB/cut revision
measurement evidence
```

## 5.5 Revocation / invalidation

A later physical modification may invalidate earlier claims.

Example:

Replacing the inter-half cable does not invalidate cosmetic grading, but may invalidate the previously verified communication-stability claim until retested.

Reuse HS selective-evidence-invalidation concepts rather than inventing a separate invalidation engine.

---

# 6. Agent-readable service architecture

The agent surface should exist because the passport is structured, not because a chat UI is the product.

## 6.1 Read-only default

Any external/general-purpose agent begins read-only.

Suggested capabilities:

```text
get_unit_summary(unit_id)
get_unit_configuration(unit_id)
get_unit_history(unit_id, scope)
get_current_claims(unit_id)
explain_claim(claim_id)
get_open_limitations(unit_id)
get_recipe_lineage(unit_id)
get_service_context(unit_id, symptom)
compare_unit_to_recipe(unit_id, recipe_version)
check_warranty(unit_id, symptom)
```

## 6.2 Service reasoning

Example customer request:

> Right half of my HS split keyboard stopped working.

Agent should retrieve:

- exact unit/revision;
- transformation architecture;
- inter-half connection type;
- prior failure/repair history;
- currently installed controller/firmware;
- relevant recipe failure modes;
- warranty state;
- allowed troubleshooting actions.

It should not infer that every split keyboard uses TRRS/QMK/etc.

## 6.3 Write authority

Agents do not directly rewrite lifecycle truth.

A service operation should create a proposed intervention/session. Human/instrument-backed observations then enter the normal HS evidence/authority path before a lifecycle event is finalized.

---

# 7. Recipe Registry design

## 7.1 What a recipe is

A recipe is a **transferable engineering procedure family** backed by completed unit evidence.

For `commodity-keyboard → split-keyboard`, the recipe does not prescribe one cut line. It specifies a decision process:

1. classify donor construction;
2. identify controller and matrix topology;
3. establish desired split corridor;
4. enumerate affected nets/components;
5. compare architecture options:
   - retain original MCU + harness;
   - dual-controller conversion;
   - abandon donor PCB / rebuild matrix;
6. require relevant pre-cut evidence;
7. execute chosen physical operation;
8. validate post-cut state;
9. generate firmware/configuration if required;
10. run final functional/stability protocol.

## 7.2 Recipe reuse and HS capability reuse

Recipe transfer should integrate with existing HS capability-manifest and selective-evidence-invalidation work.

A recipe can declare dependencies such as:

```text
keyboard_matrix_topology
pcb_layer_assumption
controller_architecture
voltage_domain
split_transport
mechanical_cut_clearance
```

When donor B differs from donor A, HS predicts which procedure/evidence can transfer and which must be re-established.

## 7.3 Empirical recipe metrics

Track:

- successful completed units;
- failed/abandoned units;
- intervention time;
- new-parts cost;
- donor reuse ratio;
- evidence reuse ratio;
- retest compression;
- failure modes;
- warranty/service incidents;
- recipe-branch frequency.

Do not optimize the public recipe score before enough observations exist.

---

# 8. Passport views

One data core, multiple access-controlled views.

## 8.1 Public / buyer view

- current product identity;
- donor-origin summary;
- current functionality;
- cosmetic condition;
- major modifications;
- replacement/retained component disclosure where useful;
- latest test date;
- open limitations;
- warranty summary;
- QR verification state.

## 8.2 Technical / service view

- component topology;
- exact revisions;
- transformation events;
- test protocol results;
- firmware/config hashes;
- known failure/repair history;
- recipe lineage;
- replacement compatibility;
- service actions;
- evidence references.

## 8.3 Private operator view

- acquisition price;
- seller identity;
- private serial/IMEI;
- internal costs/labor;
- private diagnostics;
- customer information;
- dispute/service notes.

## 8.4 Regulator/auditor view — future

Only if required and appropriately authorized.

Keep the access-control model compatible with DPP's principle that different actors may have different field-level access rights.

---

# 9. Condition, grading, and warranty semantics

Do not invent one universal `HS Grade A`.

Use separate dimensions:

```text
cosmetic_condition
functional_coverage
verification_depth
component_provenance
battery_or_consumable_health
known_limitations
warranty_scope
```

For phones or standardized mobile devices, adapters may later map to CTIA grading terminology.

For general electronics, functional verification should be protocol-specific.

For data-bearing devices, resale-ready status should have an explicit sanitization claim aligned with an approved sanitization standard/process. NIST SP 800-88 Rev. 2 is a suitable current reference for program-level media sanitization design, but an actual operation must implement an appropriate approved technique/tool and record validation.

---

# 10. Taiwan commercial/compliance boundary

This blueprint is not legal advice. Before commercial sale of transformed/refurbished electrical/electronic goods in Taiwan, route the exact product category and modification through a compliance review.

Design implications:

- do not assume an original BSMI mark automatically covers a materially modified product;
- retain original regulatory identity separately from transformed-unit identity;
- passport must not call HS verification a regulatory certification;
- allow compliance artifacts/marking to be attached as distinct claims;
- online/distance-sale workflows must support required consumer disclosures and statutory cancellation/return obligations;
- warranty wording must identify the actual warrantor and scope;
- personal data must remain outside public passport data by default.

For prototypes/research not offered for sale, preserve a distinct `research/prototype` lifecycle state so it cannot accidentally be projected as commercial-ready inventory.

---

# 11. Reference architecture

```text
                         ┌──────────────────────────┐
                         │   Hardware-Splicer Core  │
                         │ engineering truth/evidence│
                         └────────────┬─────────────┘
                                      │ signed/hashed projections
                                      ▼
                         ┌──────────────────────────┐
                         │    Lifecycle Registry    │
                         │ units + events + claims  │
                         └───────┬────────┬─────────┘
                                 │        │
                    ┌────────────┘        └─────────────┐
                    ▼                                   ▼
          ┌──────────────────┐                ┌──────────────────┐
          │  Unit Passport   │                │ Recipe Registry  │
          │ human + machine  │                │ procedure family │
          └───────┬──────────┘                └────────┬─────────┘
                  │                                    │
           ┌──────┼────────┐                      HS reuse engine
           ▼      ▼        ▼
       public   service   agent/API
        page     view       MCP
           │
           ▼
   ┌──────────────────┐
   │ Listing/Warranty │
   │    Projections   │
   └────────┬─────────┘
            ▼
      external channels
     eBay/Shopee/etc.
```

---

# 12. Storage architecture

Recommended conceptual split:

## Transactional state

Relational database for:

- unit identities;
- current revisions;
- event indices;
- access rights;
- warranty/listing state;
- recipe metadata.

## Evidence/artifact store

Content-addressed object storage for:

- photos;
- bench logs;
- raw measurements;
- firmware/config files;
- PDFs;
- diagnostic exports;
- generated engineering packages.

Store hashes in the registry.

## Search/index layer

Derived index for:

- full-text service search;
- vector/semantic recipe retrieval;
- agent retrieval;
- cross-unit failure-mode analysis.

Search is never authoritative; retrieval results resolve to canonical records.

---

# 13. API blueprint

No implementation in this design pass. Proposed boundary only.

```text
GET  /v1/units/{id}
GET  /v1/units/{id}/passport
GET  /v1/units/{id}/events
GET  /v1/units/{id}/claims
GET  /v1/units/{id}/evidence/{claim_id}
GET  /v1/units/{id}/service-context

POST /v1/units/{id}/service-sessions
POST /v1/transformations
POST /v1/transformations/{id}/events
POST /v1/tests

GET  /v1/recipes
GET  /v1/recipes/{family}/{version}
GET  /v1/recipes/{family}/{version}/instances
POST /v1/recipes/{family}/{version}/evaluate-transfer

GET  /v1/resolver/{identifier}
```

Public write APIs should not exist initially.

---

# 14. Reference pilot: split keyboard lifecycle

## Phase K0 — frozen donor

Create:

`unit: donor-keyboard-001`

Evidence:

- intact photos;
- manufacturer/model;
- baseline functional test;
- acquisition/source metadata;
- original physical state.

## K1 — engineering transformation

HS controls:

- donor disassembly;
- topology/matrix reconstruction;
- architecture choice;
- pre-cut evidence gates;
- physical modification plan;
- post-cut repair/reconstruction;
- firmware/config;
- bench validation.

## K2 — transformed output unit

Create:

`unit: hs-split-keyboard-001`

Link:

`donor-keyboard-001 → TransformationRecord → hs-split-keyboard-001`

Record all retained/replacement components and exact evidence state.

## K3 — passport

QR/public page shows:

- donor origin;
- transformation summary;
- verified functionality;
- major component provenance;
- current limitations;
- latest validation date;
- no unsupported certification language.

## K4 — recipe v0

Create:

`recipe: keyboard/commodity-to-split@0.1`

Status: `OBSERVED` only after the actual unit is completed.

## K5 — agent service test

Blind troubleshooting comparison:

- generic agent with only product category;
- agent with unit passport + recipe lineage.

Measure whether passport context reduces unsupported assumptions and improves diagnostic ordering.

## K6 — sale-style projection

Generate a truthful listing page/export, but do not operate a marketplace.

If commercial sale is considered, perform product-specific Taiwan compliance/warranty analysis first.

---

# 15. Phased roadmap

## Blueprint phase — NOW

Documentation/research only.

Deliverables:

- architecture;
- entities;
- trust model;
- standards mappings;
- pilot protocol;
- explicit non-goals.

No code.

## Phase 0 — single-unit lifecycle proof

Only after blueprint review.

- split keyboard as first unit;
- static machine-readable passport generated from existing HS artifacts;
- no marketplace;
- no generalized DPP compliance claim;
- no external sellers.

## Phase 1 — internal registry

If Phase 0 is useful:

- persistent unit/event/claim registry;
- recipe v0;
- QR resolver;
- service history.

## Phase 2 — agent/service interface

- read-only API/MCP;
- unit-specific troubleshooting;
- recipe transfer query;
- warranty/service context.

## Phase 3 — refurb workflow adapters

- data sanitization records;
- standardized diagnostics where applicable;
- condition/listing projections;
- seller/shop workflow.

## Phase 4 — external interoperability

- GS1 Digital Link / EPCIS projections where justified;
- DPP standards adapters;
- signed/verifiable credentials;
- third-party service providers/auditors.

## Phase 5 — commerce decision

Only after evidence of demand.

Choose among:

- listing-export infrastructure;
- certification/passport SaaS for refurbishers;
- service/warranty tooling;
- recipe/licensing ecosystem;
- managed marketplace.

Marketplace is not the default.

---

# 16. Success metrics

## Technical integrity

- 100% of public functional claims resolve to canonical evidence;
- zero silent deletion of lifecycle failures;
- zero downstream promotion of `PARTIAL/UNVERIFIED` evidence to proven state;
- unit/revision linkage complete for consequential tests;
- transformation input/output lineage complete;
- passport rebuild from canonical records is deterministic.

## Recipe quality

- applicability decisions explainable;
- unknown/incompatible donors fail closed;
- recipe version frozen per completed instance;
- one-off procedure not promoted to replicated recipe;
- transfer/invalidation predictions measured against later evidence.

## Agent utility

Compare passport-aware vs generic troubleshooting:

- unsupported assumptions;
- number of diagnostic steps;
- first-correct-test rate;
- authority violations;
- resolution rate.

## Commercial evidence — later

Only after real sales/service:

- listing conversion;
- price premium/discount;
- return rate;
- warranty claim rate;
- service time;
- dispute rate;
- buyer usage of passport.

No commercial metric should be fabricated from prototype data.

---

# 17. Key risks and design responses

| Risk | Response |
|---|---|
| passport becomes marketing copy | claims must resolve to HS evidence |
| sellers fabricate history | signed actor/tool attestations + immutable event history |
| every tiny component becomes tracking overhead | explicit component-tracking threshold |
| recipe overfits first unit | maturity states + applicability rules + replication evidence |
| AI invents repair history | read-only canonical retrieval; agent cannot rewrite facts |
| proprietary DPP dead-end | open JSON + API + JSON-LD/GS1 adapters |
| blockchain complexity theater | no blockchain requirement |
| privacy leak via serial/customer data | field-level access + private identifiers |
| original regulatory mark misrepresented | separate original compliance from transformed-unit claims |
| marketplace consumes project | marketplace explicitly deferred |
| lifecycle system becomes second HS truth source | one-way authority from HS → registry/projections |

---

# 18. Research-derived design constraints

The blueprint deliberately incorporates current external practice:

1. Used-device certification platforms show that **item-level diagnostic history and API-readable certification** can carry commercial value.
2. Refurb marketplaces show that **functional testing, condition disclosure, warranties, and seller quality controls** are expected trust mechanisms.
3. iFixit demonstrates the scale/value of structured repair procedures and exposes its guide corpus programmatically.
4. EU ESPR/DPP architecture requires persistent identifiers, data carriers, machine-readable/open data, differentiated access rights, and long-term lifecycle availability.
5. The EU DPP Registry is live as of July 2026, and six harmonized DPP standards covering IDs, carriers, exchange, storage, APIs, and interoperability are already cited.
6. GS1 EPCIS provides a mature event vocabulary and specifically models input→output physical transformations.
7. CIRPASS-2 is actively piloting repair/refurbish/rebuild use cases in electronics and launched an OpenDPP open-source catalogue in August 2026.
8. W3C Verifiable Credentials 2.0 provides a standardized future mechanism for signed machine-verifiable claims.
9. R2v3 Appendix C explicitly treats testing/repair/refurbishment and verification of device condition/functionality as a formal reuse process.
10. Taiwan commercialization requires product-specific inspection/compliance and consumer-contract analysis; prototype evidence must not be mislabeled as regulatory certification.

See `HS_LIFECYCLE_RESEARCH_MATRIX.md` for the external validation matrix and source links used for this design.

---

# 19. Final architecture doctrine

> **Hardware-Splicer changes and verifies hardware. The Lifecycle Platform remembers what happened. The Recipe Registry learns what transfers. The Passport explains the present unit. Agents consume that context. Commerce may project it, but may not rewrite it.**

This separation is the core design constraint.
