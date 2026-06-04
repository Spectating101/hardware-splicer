# Circuit-Mecha Service SKU Contracts (2026-03-01)

## SKU-1: Draft Feasibility Pack

### Scope
- Intake requirements normalization (EE+ME).
- 1 initial design bundle run.
- Baseline DFM + simulation + safety report.

### Deliverables
- `mecha_splicer.bundle.json`
- `MECH_CHECK.md`
- `DESIGN_DECISIONS.md`
- `RISK_REGISTER.md`

### Acceptance Criteria
- At least one complete generated artifact set.
- All major assumptions explicitly listed.
- Clear pass/fail gate state for baseline candidate.

### Revisions
- 1 revision round.

## SKU-2: Verified Prototype Pack (Default)

### Scope
- Full vibe-to-proof / magic-loop iteration until pass/fail conclusion.
- Pricing lock workflow with editable SKU overrides.
- EE gate + ME gate evidence.

### Deliverables
- `MAGIC_LOOP_RESULT.json`
- `MAGIC_LOOP_REPORT.md`
- `SIM_RESULTS.json`
- `RISK_REGISTER.md`
- `REVISION_NOTES.md`
- `BUY_LIST.csv`, `BUY_LIST.locked.csv`, `PROCUREMENT_LOCK_REPORT.md`

### Acceptance Criteria
- No `block` findings in final accepted iteration OR explicit documented blocker rationale.
- Pricing lock file produced and editable.
- Reproducible run command included.

### Revisions
- Up to 3 revision rounds.

## SKU-3: Execution Support Retainer

### Scope
- Ongoing adaptation for client feedback and manufacturing prep handoff.
- Weekly benchmark/evidence refresh.
- Optional Circuit-AI validator integration checkpoints.

### Deliverables
- Rolling `REVISION_NOTES.md`
- Updated design/evidence bundles per sprint.
- Priority risk register updates.

### Acceptance Criteria
- Weekly artifact delivery cadence met.
- Open risk delta tracked from previous cycle.
- Scope deltas and decisions documented.

### Revisions
- Continuous during retainer period.

## Commercial Guardrails
- Out-of-scope: certification signoff, safety-critical legal compliance, guaranteed manufacturing yield.
- Any physical fabrication/logistics is separate unless explicitly included.
- Client approval required for final supplier substitutions.
