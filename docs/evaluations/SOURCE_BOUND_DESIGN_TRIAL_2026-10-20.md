# Hardware Splicer: canonical evidence-to-design trial

Date: 2026-10-20. Executed on Optiplex. Qwen disabled.
This is a conditional source-bound plan, NOT a finished repair or
physically functional new machine.

## Architectural finding

The mature engineering_planner already implements engineering source
graphs, claim/provenance tracking, source conflicts, robot topology,
identity mapping and change-impact analysis. The old
source_agnostic_benchmark instead calls the historical intake planner,
without passing the complete source catalog and conflicts.

This trial calls the existing engineering_planner on all four original
cases, then creates specific conditional decisions grounded in claim IDs,
source identities, verbatim values and claim SHA-256 hashes.
An independent checker compares these to the original engineering
sources and a separately generated canonical plan.

## Historical baseline (controlled offline/Qwen-disabled run)

- Conflicting quadruped: 48/100; reference and gap triage
- Damaged donor rover: 70/100; structured project assistance
- Field-failure rover: 50/100; reference and gap triage
- Requirements-only rover: 100/100; historical bounded candidate

The historical rubric is NOT independent physical engineering truth.
An earlier run without these exact offline settings scored none in
the top category. Under this consistent run it awarded one full score
despite lacking real electrical, mechanical, safety and bench proof.

## New source-bound trial results

- Conflicting quadruped: 4/4 source IDs preserved, 4 blocking conflicts,
  2 conditional decisions. No mixed-generation actuator architecture
  authorized.
- Donor repair rover: 4/4 source IDs, 2 blocking conflicts, 2 conditional
  decisions. Burned driver and mismatched motor remain excluded from
  any physical acceptance; zero usable motors independently proved.
- Field-failure rover: 4/4 source IDs, 1 blocking conflict, 2 conditional
  decisions. Revision 7, camera-mast stability, rail droop and regression
  need are carried into plan, without invented stability numbers.
- Requirement-only rover: zero external sources needed, 2 conditional
  decisions; runtime power and actual frame geometry still unknown.

Every source-linked decision lists the exact original claim IDs and
hashes, and marks unknown engineering measurements as missing.
All four conditional records pass the independent SOURCE-INTEGRITY
check, and none grants fabrication, power, repair or product authority.

## Actual new public-source holdout: stationary label feeder

Six archived public-page receipts from the earlier real public-source
controller were supplied as an unseen source-bound case:
three secondhand marketplace seller records (LS2208 scanner,
Epson LQ-680 printer, bare QNAP TS-219P II motherboard), and
three official model-family documentation pages (Zebra, Epson, QNAP).
All have original public URL, observation time and source body digest.

The canonical planner inferred a ROVER from this explicitly
STATIONARY_ONLY problem. Initial source integrity checks alone did
not catch that false candidate. The new requirement-to-topology
gate detected the contradiction and:
- Preserved all six source metadata records and nine claim citations.
- Rejected the rover topology as unusable.
- Labeled the architecture UNRESOLVED_STATIONARY_EQUIPMENT.
- Marked conditional design acceptance FALSE and physical authority FALSE.

This is a FAILED engineering design but a successful detection of
irrelevance. It is not scored as a usable stationary machine.

## Independent negative tests

Intentionally altered source versions, quote content, original
constraint values, conflict dispositions, claimed measurements,
provenance levels and source reference membership. The independent
oracle rejected these falsifications. A deliberately deleted
source-to-decision link is rejected even with source metadata intact.

30 focused tests passed across new source-to-design, existing
engineering planner/source graph and historical benchmark. This
number does not establish physical functionality.

## Reproduction and interfaces

Run:
PYTHONPATH=src QWEN_DISABLED=1 HARDWARE_SPLICER_QWEN_DISABLED=1 \
  python -m scripts.run_source_bound_design_trial --out /tmp/hs-source-bound

SDK function: plan_source_bound_design(scenario=...)
MCP tool: hs_plan_source_bound_design

Machine-readable evaluation:
SOURCE_BOUND_DESIGN_TRIAL_2026-10-20.json.

## Remaining critical limitations

1. Canonical planner still generates irrelevant robot architectures.
   New guard detects and blocks; underlying generation needs repair.
2. Decision generation here is bounded, rule-based, conditional and
   domain-specific. It is not arbitrary independent engineering design.
3. No hardware specimen has been obtained, powered, measured, wired,
   repaired, fabricated or tested.
4. Source claims from fixture-like evidence:// URIs are NOT instrument
   authenticated, even if their original records claim measured authority.
5. Legacy golden-real bench pathways remain outside this trial; their
   capture provenance and physical power authorization need a separate
   review. simulated=false inside a JSON fixture is not reliable proof.

No user manual checking was required for this software milestone.
