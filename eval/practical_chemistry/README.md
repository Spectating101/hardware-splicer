# HS Practical Chemistry Decision Benchmark

From the Hardware Splicer repo root:

    PYTHONPATH=src python eval/practical_chemistry/decision_benchmark_v1.py

This suite runs 31 authored expectations for manufacturer-specific chemistry
screening under varied materials, neighboring plastics, battery hazards,
powered boards, contact residue, coatings, polymer finishing and corrosion.

The 11 manually selected manufacturer/repair guidance references and 10
available approaches are in the practical chemistry catalog under package
data. They are not experimental safety or compatibility certifications.

See docs/PRACTICAL_CHEMISTRY_ENGINE.md for endpoints and economics.

## Practical V2 and expansion freeze

Run the 35 additional v2 authored edge/failure cases:

    PYTHONPATH=src python eval/practical_chemistry/decision_benchmark_v2.py

The v2 extension registry is the separate
src/hardware_splicer/data/practical_chemistry_catalog_v2.json.
Both registries load into a single canonical product/API and MCP interface.

See docs/PRACTICAL_CHEMISTRY_V2_FREEZE.md. After v2, use real device
evidence and held-out repair outcomes to prioritize changes, rather than
adding unrelated chemistry solvers or unverified product recommendations.

## HS project-to-review workflow benchmark

    PYTHONPATH=src python eval/practical_chemistry/full_hs_workflow_benchmark_v1.py

Runs 4 synthetic projects through the actual HS API, revisioned ProjectStore,
practical chemistry preview, pending review, submitted acceptance, findings
and hash-bound review packet. This is a software integration demonstration,
not an operator usability study, real-world repair or measured ROI.

See docs/PRACTICAL_CHEMISTRY_HS_WORKFLOW_AUDIT.md.
