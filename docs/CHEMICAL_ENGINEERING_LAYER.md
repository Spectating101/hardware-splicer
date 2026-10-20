# Chemical engineering — computational integration and evidence boundaries

HS represents chemical disciplines in the canonical MachineProject, alongside
mechanical, electrical, firmware and other domains. The existing HS project
store, source graph, revision reviews and MCP gateway remain authoritative.
No second agent or engineering-release system is created.

## Implemented and callable

| Endpoint | Backend | Actual scope |
|---|---|---|
| GET /v1/engineering/chemical/engines | HS probe | Installed vs implemented scientific adapters |
| POST /v1/engineering/chemical/molecule/inspect | RDKit (optional) | SMILES formula, molecular weight, charge |
| POST /v1/engineering/chemical/properties/inspect | thermo (optional) | Density, heat capacity, viscosity and thermal conductivity at T/P |
| POST /v1/engineering/chemical/materials/composition | pymatgen-core (optional) | Elemental mass/atomic fractions and reduced formula |
| POST /v1/engineering/chemical/materials/evidence-check | HS MachineProject | Read-only property/limit reconciliation across chemical, mechanical and electrical constraints |
| POST /v1/engineering/chemical/materials/compare | HS MachineProject | Fairness-gated comparison across candidates; rejects unequal screening requirements |
| POST /v1/engineering/chemical/enclosure/assembly-review | MachineProject + electrical ERC + STEP geometry + mechanical fit + chemical evidence | Read-only, identity-bound joint enclosure screening; recomputes geometry/fit rather than trusting supplied status |
| POST /v1/engineering/chemical/materials/document-claim/evidence-draft | HS canonical document-claim adapter | Parsed ISO75 HDT quote to proposed MachineProject EvidenceRef, with page/hash locator and no authority promotion |
| POST /v1/engineering/chemical/gas/state | Cantera (optional) | Bounded air-model thermophysical state and TP equilibrium |
| POST /v1/engineering/chemical/process/mass-balance | HS engine | Declared overall and nonreactive component mass-flow checks |
| POST /v1/engineering/chemical/battery/discharge | PyBaMM (optional) | Reference Li-ion SPM discharge curve (Chen2020 parameter set) |

Install only the needed optional dependencies:

    pip install -e '.[chemical]'
    pip install -e '.[chemical-process]'
    pip install -e '.[chemical-battery]'
    pip install -e '.[chemical-materials]'

Optional engines return HTTP 503 when absent; HS never fabricates solver outputs
to hide a missing dependency. Routes appear in canonical OpenAPI and are callable
via the existing hs-backend-mcp gateway.

For concise agent discovery, the MCP gateway supports task manifests
chemical_material_review, chemical_process_review,
chemical_battery_model_review and chemical_enclosure_assembly. These are discovery groups, not autonomous
authorization or long-running background tasks.

## Suggested agent sequence

1. Locate canonical project, component identities, constraints and source objects.
2. Discover models with the engines endpoint; run calculations with explicit
   inputs and preserve engine versions, parameters, units and conditions.
3. For material suitability, select an existing MachineProject component with
   metadata.material_id; a constraint whose applies_to includes the component
   and whose metadata specifies material_property, unit, min_value/max_value;
   and EvidenceRef rows supporting BOTH component and constraint, carrying
   a source ref and metadata for identical material_id, material_property, unit,
   and value.
4. Run materials/evidence-check. Identity mismatch, unit mismatch, source gaps,
   numeric failures and conflicting values block the report. For ISO 75 heat
   deflection evidence, the method and test load (0.45 MPa or 1.80 MPa) must
   match EXACTLY. No converting from HDT into a generic max service temperature.
   The evidence must include a source SHA256 and page locator; these are
   asserted by the caller, not re-fetched in this comparator. Matching numeric
   limits are only numerically_consistent_but_unverified.
5. Compare candidates through materials/compare, which rejects incomparable
   criteria even if one candidate's smaller checklist passes.
6. For PDF provenance, use HS's existing project-scoped source ingestion,
   hash-reverified document pages, and page-anchored document claims, then
   request a proposed evidence draft using the chemical bridge. This bridge
   checks ISO75 quote/value agreement, but it does not itself re-read the PDF.
7. Independent source verification, domain review and physical validation remain
   separate, required gates. No claim receives implicit promotion.

Supported material metric units: heat_deflection_temperature=K (ISO75 with
0.45 or 1.80 MPa load), density=kg/m3; youngs_modulus=Pa;
thermal_conductivity=W/(m*K); electrical_resistivity=ohm*m;
max_service_temperature=K; specific_heat_capacity=J/(kg*K).

## Model boundaries

Cantera is fixed to bundled air.yaml with input gases N2, O2, AR;
temperature 250-1200 K; pressure 50 kPa-5 MPa. Optional equilibrium is
constant-T/P, not real reactor kinetics or process safety.

PyBaMM is fixed to the Li-ion single particle model (SPM), Chen2020
parameters, C-rate 0.1-1 and duration 60-3600 s. It describes a reference
cell, not a real unidentified battery, pack, BMS, repair, abuse or thermal
runaway. No physical battery operation is authorized.

pymatgen-core describes elemental composition only: no measured crystal phase,
strength, material compatibility or processing. The mass balance verifies
declared arithmetic only, not an actual apparatus or chemical reaction.

All outputs explicitly deny chemical safety, material compatibility,
fabrication, physical operation and release authorization. User-supplied
source refs are POINTERS rather than authenticated evidence.

## Still missing

- Authenticated material-source acquisition and compatible source-specific data.
- Corrosion, solvent compatibility, uncertainty and processing-history models.
- Real reaction kinetics/reactor coupling and complex mixture phase behavior.
- Battery electrical/cooling/geometry co-simulation and measured-cell calibration.
- Chemical hazard analysis, physical validation and production release.
- User-facing guided chemistry workflow beyond canonical API/MCP.

Later isolated candidates: DWSIM (separate GPLv3 process flowsheet program)
and Open Reaction Database (experimental reaction records). Neither is
embedded in HS here.

## Reproducible real-source evaluation

- Evaluation script: eval/chemical_materials/prusa_enclosure_screen_v1.py.
  Ten authored cases, not a blinded dataset or statistical accuracy claim.
- Optional source verifier: eval/chemical_materials/verify_prusa_tds.py.
  Verifies original Prusa ASA / PC Blend PDF SHA256 and page-2 ISO 75 values.
- Registered-source integration: eval/chemical_materials/registered_pdf_end_to_end.py.
  In a temporary isolated ProjectStore, exercises HS source PDF ingestion,
  hash-reverified document reading, page-anchored claim registration, proposed
  EvidenceRef conversion and read-only material screening.
- Detailed limitations and benchmark findings: docs/CHEMICAL_ENGINEERING_EVALUATION.md.

## Three-layer assembly review (v1)

The bounded assembly operation requires:
- One canonical MachineProject with two distinct material candidates, one
  selected mechanical enclosure and one explicit electrical board component.
- An ElectricalDesign with the same project ID, mapped component identities,
  populated pins/nets, and a canonical ERC check, actually executed.
- A MechanicalGeometryReport with the same project ID and STEP source summaries
  plus part-linked reciprocal board/enclosure mating interfaces.
- Explicit PCB/lid clearance envelopes and a constraint linking the
  selected enclosure and board. The geometry and fit checks are recomputed.
- Method/load-matched material evidence under equivalent candidate criteria.

Contradictions and missing coverage block analytical screening. A clean result
is still bounded_assembly_screen_consistent_but_unverified, NOT build-ready.
It includes mandatory independent follow-up on operating thermal loads, actual
solid geometry, insulation, manufacturing, and material source qualification.
No coupled thermal solver, structural FEA, real PCB inspection, safety
certificate or fabrication authority is provided.

See eval/chemical_materials/three_layer_enclosure_v1.py for 11 bounded cases,
and registered_three_layer_end_to_end.py for a genuine original-PDF-to-HS-
project evidence and three-layer screening exercise on a temporary store.
