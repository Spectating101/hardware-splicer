# Chemical engineering evaluation — evidence-first FDM enclosure case

Date: 2026-10-20.
Branch: agent/chemical-engineering-v0.
Not a production acceptance test or material selection approval.

## Use case and evidence

Question: for an illustrative thermally exposed electronics enclosure, can HS
screen Prusament ASA and Prusament PC Blend against explicit standardized
material-test criteria, retaining scientific context and refusing to substitute
incomplete data for safety evidence?

Manufacturer TDS sources (PDF page 2, typical material properties):

| Candidate | ISO75 HDT at 0.45 MPa | ISO75 HDT at 1.80 MPa | PDF SHA256 |
|---|---:|---:|---|
| Prusament ASA | 93 deg C | 86 deg C | a8e322580ae1683f398c8a0cfe7c9221747f1b6ec99d2a953e3e48161a959aab |
| Prusament PC Blend | 113 deg C | 93 deg C | 25f7aa7b99cc24e5b7d75fbbfd5fa949a3e5689b7201c6b34a9cb588d7c040c7 |

ASA: https://storage.googleapis.com/prusa3d-content-prod-14e8-wordpress-prusament-prod/2024/05/bc8551ef-tds_prusament-asa_2024_en.pdf

PC Blend: https://prusament.com/wp-content/uploads/2022/10/PCBlend_Prusament_TDS_2022_16_EN.pdf

The experiment downloaded both vendor PDFs to a temporary Optiplex directory,
computed SHA256 over complete bytes, extracted page-2 text with PyPDF,
and independently rechecked four quoted ISO75 values. All two document hashes
and all four material values matched. Original PDF bytes are not checked into Git.

## Result A — deterministic screening / adversarial cases

Benchmark source: eval/chemical_materials/prusa_enclosure_screen_v1.py

**10 / 10 authored cases passed.** These are hand-constructed, expected-output
tests, not independent predictive-validation evidence. The benchmark used
hypothetical acceptance thresholds (100 deg C at 0.45 MPa, 90 deg C at 1.80 MPa),
not actual enclosure qualification requirements.

- Under those thresholds, ASA fails the screening criteria.
- PC Blend meets both numerical ISO75 screening thresholds, but remains
  unverified; no manufacturing, chemical safety or electrical authorization.
- With a stricter 100 deg C screen at 1.80 MPa, BOTH materials are blocked.
- Adding missing electrical insulation evidence blocks BOTH candidates.
- Injecting wrong ISO75 load, wrong method, missing source ref, malformed
  SHA256, different material identity, or conflicting source data blocks
  unsupported candidate claims.
- Giving candidates different constraint sets triggers a comparison-level
  fairness blocker; a candidate cannot win merely by having fewer checks.

The material comparator is strictly read-only, with no implicit authority
upgrade. Its sub-10 ms localhost response times in the small benchmark
illustrate its bounded computational cost; these are not production latency
measurements.

## Result B — canonical source-to-project pipeline

Experiment: eval/chemical_materials/registered_pdf_end_to_end.py

Executed against TWO actual Prusa PDFs and an isolated temporary HS ProjectStore.

- 2 original PDF digests checked.
- 2 canonical document hash rechecks performed.
- 4 page-anchored document claims registered at *proposed* authority.
- 4 values checked against exact ISO75 quoted rows.
- 4 proposed MachineProject EvidenceRef candidates constructed.
- Material screen: ASA = blocked, PC Blend = numerically consistent but unverified.
- No material selection authorized; source-to-evidence conversion created no
  automatic physical verification or operational permission.
- Chemical screening produced no project store revision change.

The source-to-evidence mapping is deterministic for ISO75 HDT tables,
but document quotes were **selected manually** during this controlled
experiment. Autonomous multi-vendor datasheet identification, reading and
interpretation remain unproven.

## Why this matters

This is the first practical source-grounded use case connecting HS's third
engineering pillar with its existing project and document-evidence systems:
electrical enclosure need -> mechanical candidate -> manufacturer material
properties -> comparable method/condition-specific screening -> missing proof.

The test identifies where candidate performance differs and, more importantly,
where an apparent result MUST NOT be treated as evidence of actual suitability.

## Major remaining limitations

1. HDT is a standardized deflection test under a stated load, not an unqualified
   continuous operating-temperature rating.
2. Neither source establishes print-process repeatability, as-built part geometry,
   flame classification, dielectric withstand, creepage/clearance, corrosion,
   thermal cycling, or operating safety for any particular enclosure.
3. Manufacturer-reported typical values are not measured evidence for a physical
   sample. No independent source credibility scoring was conducted.
4. The claim-adapter checks quote/value consistency but cannot authenticate a
   document by itself. The canonical project source-document path must verify
   bytes before claim creation.
5. These tests do not validate the open scientific engines against independent
   reference data, nor demonstrate a general purpose chemical reasoning agent.
6. No autonomous experiment generation, physical verification or actual
   manufacturing selection is authorized.

Conclusion: **credible prototype for evidence-bounded material screening**,
but **not ready to choose certified production materials without human review
and application-specific experimental/standards evidence**.

## Results C — chemical/mechanical/electrical integration

A new read-only enclosure assembly endpoint combines real internal HS
mechanical STEP/clearance checkers, electrical ERC and material evidence
checks. In 11 deliberately authored negative/positive scenarios, 11 passed.

- Baseline: under hypothetical 100C (0.45 MPa) and 90C (1.8 MPa) HDT criteria,
  PC Blend is numerically consistent. The synthetic PCB/lid exclusion volumes
  have declared separation 8 mm against a 5 mm clearance screen; the illustrative
  net has two mapped pins and no electrical ERC errors. Result UNVERIFIED.
- Negative scenarios reject ASA material evidence, lid/PCB overlap,
  multiple electrical hard drivers, wrong project identities, untracked
  electrical component, disconnected enclosure/PCB mating identity,
  missing materials evidence, missing clearance coverage, and unequal
  candidate screening constraints.
- A forged precomputed passing geometry status is ignored: the actual
  geometry and fit analyses are recomputed from supplied model details.
- A separate pair of tests blocks nonfinite mechanical/electrical parameters.
- Outstanding evidence explicitly covers real operating temperature,
  full geometric bodies/fit, insulation, material provenance and manufacturing.

The example STEP is a deliberately minimal Cartesian-point envelope, not a
production CAD solid. The electrical net and geometric coordinates are
synthetic declared tests. There is no true 3D collision or thermal simulation.

A second integrated experiment, registered_three_layer_end_to_end.py,
uses BOTH original Prusa PDFs with hash verification, four page-anchored
proposed claims, four evidence objects, and the three-layer assembly review.
It returned 11 mechanical geometry checks, 2 fit checks and 0 ERC errors
while reporting only analytical consistency, never build authorization.
The material screen did not mutate the project's revision history.

These are software integration proofs, NOT engineering validation of a real
enclosure. The next research step is a real STEP/PCB artifact, real thermal
measurements, application-specific electrical/safety constraints, independent
multi-vendor evaluation and a guided interface.
