# Practical Chemistry v2 — Final Planned Feature Expansion and Freeze Gate

**State:** isolated branch development candidate, NOT production release.
**Role in Hardware Splicer:** practical chemistry and materials decisions for
repair, reuse, material compatibility, device protection and fabrication.
Scientific thermodynamics/simulation remain opt-in support, not product focus.

## Implemented capability matrix

The v2 catalog loads BOTH independent, versioned source registries.
At the v2 build checkpoint: **21 indexed manufacturer/repair sources,
20 scoped methods, 12 practical tasks**. Public manufacturer sources include
3M, MG Chemicals, Henkel, DuPont, Prusa and iFixit.

| Workflow | Useful practical differentiation | Acceptance evidence still required |
|---|---|---|
| PCB/connector cleaning | Flux vs contact clean, zero-residue vs protective films, energized/battery-stop | True contamination type, exact plastic/coating compatibility, contact retest |
| Adhesives | PP/PE specialty acrylic vs unproven generic epoxy, joint loads and rework | Exact polymer grade, adhesion/fatigue and operating exposure coupons |
| PCB conformal protection | Acrylic vs silicone-modified coating, contact keep-outs and rework | Actual mask plan, cleaning, dielectric/adhesion/cure tests |
| Electronic encapsulation | 832HD **rigid** vs 832FX **flexible**, irreversible rework, cure stress/heat | Heat rise, exotherm, cure, shrinkage, component strain and field servicing |
| Thermal interface | Henkel HC5000 compliant gap pad vs MG 860 *thin* paste | As-built thickness, pressure/compression, contact impedance, measured power and temperature |
| RTV seals | MG 1035 **neutral-cure** RTV instead of treating all RTV as equivalent | Confined cure, substrate adhesion, moisture ingress and leak/corrosion testing |
| O-ring and gasket compounds | DuPont MOLYKOTE 111 vs 55: 55's potential rubber swelling matters | Actual NBR/EPDM/SR grade, dimensional compatibility, leak/ageing |
| Lubricants | YM-102 PAO slide/gear grease vs sealing compounds | Specific resin, contamination migration, wear/load and cycles |
| Conductive contact protection | MG 846 conductive grease *must not* be substituted for dielectric treatment | Insulation/short avoidance, contact resistance, contamination and cycling |
| Corrosion triage | Surface deposits vs pitting vs trace/metal loss; possible replacement | Microscopy/continuity/insulation testing, contamination root cause |
| Solvent finishing | ASA sensitivity, adjacent material damage and specialist hold | Physical sample, suitable PPE/ventilation and dimensional recheck |
| Repair economics | Full user-quoted attempts and failure path vs replacement | Verified local supply quotes, labor, failure probability and independent test outcomes |

## V2 thermal screening (carefully bounded)

The model may calculate optimistic **bulk conduction only**:

    R_bulk_ideal = L_m / (k_W_per_mK * A_m2)
    deltaT_bulk_ideal = power_W * R_bulk_ideal

This is NOT system/device thermal prediction. Interface contact resistance,
bondline variation, clamps/compression, thermal spreading, convection, product
aging and mechanical feasibility are NOT represented. Even if it passes an
assumed allowed temperature-rise threshold, HS returns RESEARCH REQUIRED
until pressure and independently measured interface impedance are available.

A worst-case useful numerical veto: if the optimistic, bulk-only delta T
already exceeds the caller's thermal-rise limit, flag the proposal as BLOCKED.
The **0.2mm paste-thickness screening criterion is an intentionally conservative
HS heuristic**, not a manufacturer-stated absolute limit. Engineers must
validate actual product/application geometry rather than relying on it.

Manufacturer documents used for practical distinctions:
- Henkel HC5000 TDS: 5.0 W/mK, compressible silicone pad and specified
  offered thicknesses; thermal impedance varies with pressure/deflection.
- MG 860: electrical insulation, reworkable paste, not a structural adhesive.
- MG 832HD/832FX: rigid vs flexible electronics encapsulation trade-offs.
- MG 1035: neutral-cure electronics-grade RTV.
- DuPont MOLYKOTE 55: rubber-swelling lubricant, grade-specific test warning.
- MG 846: electrically conductive contact grease, not an insulator.

Source URLs, evidence scope and manufacturer claims are in
src/hardware_splicer/data/practical_chemistry_catalog_v2.json.
No source revision is silently authenticated, and no supplier price or
compatibility grade is fabricated.

## Software verification

Runnable benchmark suites:

    PYTHONPATH=src python eval/practical_chemistry/decision_benchmark_v1.py
    PYTHONPATH=src python eval/practical_chemistry/decision_benchmark_v2.py

These are **31 legacy and 35 new authored test cases**, not an independent
performance benchmark or product safety certificate. The new tests cover
real-world error modes including incompatible conductive grease in insulation,
thermal paste with thick gaps, thermal pad conduction vs actual contact,
potting/serviceability, O-ring swelling, elastomer grade uncertainty,
unverified seal cure, battery hazards, and pitted/corroded traces.

The canonical FastAPI operation and existing HS MCP discovery/invocation
surfaces are reused. No separate project store, physical actuation, automatic
purchase or manufacturing authority.

## Freeze decision

**Stop adding general-purpose practical chemistry features after v2** unless
a real hardware repair/manufacturing case produces a specific verified
capability gap.

Next work should be VALIDATION, not expanding catalogs for their own sake:
1. Check original supplier product revisions/TDS/SDS and pin source hashes.
2. Run held-out repair scenarios, ideally independent technicians' records.
3. Compare screening outputs with real coupon/joint/seal/thermal trials.
4. Obtain verified local vendor quotes for specific products and batches.
5. Track false positive approvals, false negative screens, and unanswered cases.
6. Build the guided user-facing operator workflow around this existing API.
7. Merge only after full repository CI and concurrent mechanical work review.

**Critical blockers for real work:** no real compatibility certification,
no unknown-battery handling approval, no measurement-based cure/thermal/gear
durability evidence, no autonomous source freshness check or external expert
qualification. A source-scoped product description is *not* a verified
compatibility matrix for a specific physical specimen.

## Canonical HS project-workflow audit

Chemistry can now preview assessments against one revision-pinned HS
MachineProject component, stage an existing full-snapshot review, and
retain chemical blockers in the existing findings and hash-bound review packet
after a submitted acceptance. It does NOT certify or independently verify
a repair. See docs/PRACTICAL_CHEMISTRY_HS_WORKFLOW_AUDIT.md for the 4-case
integration test, remaining global release gate gap, and limitations.

## Later release enforcement

The release-readiness, audited physical-authorization and engineering-plan persistence enforcement implementation is documented in docs/PRACTICAL_CHEMISTRY_RELEASE_ENFORCEMENT.md. It does not establish independent chemical clearance.
