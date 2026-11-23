# Documentation index

Where to look, by what you are trying to do. Files that code, tests or CI refer to by path stay at this level; dated or one-off material lives under [`archive/`](archive/). If two docs disagree, [`DOCUMENTATION_INDEX.md`](DOCUMENTATION_INDEX.md) says which wins.

## Start here

- [`GITHUB_START_HERE.md`](GITHUB_START_HERE.md): single entry page for a first read.
- [`HARDWARE_SPLICER_MISSION_FREEZE.md`](HARDWARE_SPLICER_MISSION_FREEZE.md): canonical scope and work-selection contract.
- [`GITHUB_FEATURE_INTEGRATION_2026-11-16.md`](GITHUB_FEATURE_INTEGRATION_2026-11-16.md): what is integrated and how it is validated together.
- [`COLD_INTERNAL_EXIT.md`](COLD_INTERNAL_EXIT.md): what the project does and does not claim.
- [`PROGRESSION_STATUS.md`](PROGRESSION_STATUS.md): living status of what has shipped.

## Using Hardware Splicer

- [`SETUP.md`](SETUP.md): install and environment.
- [`QUICKSTART_SPLICE_v1.md`](QUICKSTART_SPLICE_v1.md): install, doctor, first build.
- [`RELEASE_v1.1.md`](RELEASE_v1.1.md): install, verify and deploy the v1.1 line.
- [`DEMO_5_MIN_UI.md`](DEMO_5_MIN_UI.md) and [`DEMO_10_MIN.md`](DEMO_10_MIN.md): demo scripts.
- [`DEVICE_MODELED_RUN.md`](DEVICE_MODELED_RUN.md): plan, generate and test a device application off-hardware.
- [`SALVAGE_PLAN.md`](SALVAGE_PLAN.md): salvage planning and its hazard rules.
- [`SPLICE_PRODUCT.md`](SPLICE_PRODUCT.md): product tiers and roadmap.
- [`DESIGN_PARTNER.md`](DESIGN_PARTNER.md) and [`OFFER_SPLICE_BENCH_KIT_v1.md`](OFFER_SPLICE_BENCH_KIT_v1.md): pilot programme and bench kit.
- [`SUPPORT_AND_LIABILITY_v1.md`](SUPPORT_AND_LIABILITY_v1.md) and [`../SECURITY.md`](../SECURITY.md): support terms and security reporting.
- [`releases/`](releases/): release notes for each tagged version; [`../CHANGELOG.md`](../CHANGELOG.md) is the summary.

## Architecture and invariants

Read these before changing engine or API code. Tests enforce them.

- [`MACHINE_PROJECT_SPINE.md`](MACHINE_PROJECT_SPINE.md): canonical project model, durable revisions, staged review.
- [`INTEGRATION_STACK.md`](INTEGRATION_STACK.md): evidence-first boundary to external tools.
- [`ENGINE.md`](ENGINE.md): engine reference.
- [`DESIGN_PRINCIPLES.md`](DESIGN_PRINCIPLES.md): design principles behind the checks.
- [`CANONICAL_PROJECT_STUDIO.md`](CANONICAL_PROJECT_STUDIO.md): the project studio model.
- [`PCB_ENGINE_DATA_CONTRACT.md`](PCB_ENGINE_DATA_CONTRACT.md): PCB engine data contract.
- [`reference/`](reference/): topical reference for current subsystems, such as [`MCP.md`](reference/MCP.md), [`ROUTING_ENGINE.md`](reference/ROUTING_ENGINE.md), [`PART_LOOKUP.md`](reference/PART_LOOKUP.md), [`CLAIMS_BOUNDARY.md`](reference/CLAIMS_BOUNDARY.md) and [`DEVICE_PLAN.md`](reference/DEVICE_PLAN.md).
- [`PAPER.md`](PAPER.md): pointer to the research manuscript in [`research/`](research/).

## Operating agents

- [`../CLAUDE.md`](../CLAUDE.md): working notes for agents, including the authority rule.
- [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md): API and MCP quickstart.
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md): how an agent runs the system.
- [`TESTING.md`](TESTING.md): test suites and focused test lists.
- [`AGENT_DRY_RUN_CHECKLIST.md`](AGENT_DRY_RUN_CHECKLIST.md) and [`EXTERNAL_PROOF_CHECKLIST.md`](EXTERNAL_PROOF_CHECKLIST.md): external dry-run and proof checklists.
- [`EXTERNAL_MCP_AGENT_PROOF.md`](EXTERNAL_MCP_AGENT_PROOF.md): how an outside agent proves the MCP backend.
- [`OPERATIONS_RUNBOOK_v1.md`](OPERATIONS_RUNBOOK_v1.md): operating runbook.

## Evidence and status

- [`HARDWARE_SPLICER_OPERATING_STATE.md`](HARDWARE_SPLICER_OPERATING_STATE.md): current operating state, with its machine-readable twin `HARDWARE_SPLICER_OPERATING_STATE.json`.
- [`status/`](status/): dated status notes and generated logs.
- [`external_assessment/`](external_assessment/): external assessment packets and submissions.
- [`product/`](product/): claims, evidence map and offline demo material.
- [`install_reports/`](install_reports/): install reports from other machines.
- [`PROOF_PACK_CONTENTS.md`](PROOF_PACK_CONTENTS.md): what the proof pack contains.
- [`CONSOLIDATION_AUDIT_2026-07-31.md`](CONSOLIDATION_AUDIT_2026-07-31.md): repository state at the July consolidation.

## Archive

[`archive/`](archive/) holds material that is kept for history and is not current guidance.

- `archive/plans/`: plans, program doctrine and acceptance contracts.
- `archive/audits-and-results/`: audits, benchmarks, experiments and one-off study results.
- `archive/handoffs/`: past handoff and competition-handoff notes.
- `archive/strategy/`: positioning, competition, funding and feasibility notes.
- `archive/demos/`: superseded demo scripts and comparison cases.
- `archive/legacy_overlays/`, `archive/screenshots/` and `archive/WORKER_REPORT_B.md`: older captures and a worker report.
