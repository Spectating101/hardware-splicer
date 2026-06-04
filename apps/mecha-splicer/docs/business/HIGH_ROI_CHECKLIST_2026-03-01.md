# High-ROI Checklist (2026-03-01)

## Completed

- [x] Circuit+Mecha magic loop with automated revision.
  - `scripts/circuit_mecha_magic_loop.py`
- [x] Live Circuit-AI endpoint gate path (`/api/v2/workflow/validate-kicad`) when URL is provided.
- [x] High-fidelity dynamics runtime enabled (`pybullet` installed + used).
- [x] Pricing lock workflow with SKU override template generation.
  - `scripts/price_lock_workflow.py`
  - `scripts/generate_sku_overrides.py`
- [x] 3 commercial SKU contract definitions with acceptance criteria.
  - `docs/business/SKU_CONTRACTS_2026-03-01.md`
- [x] Intake -> proposal automation.
  - `docs/business/INTAKE_TEMPLATE.json`
  - `scripts/generate_service_proposal.py`
- [x] Capability benchmark pack + pass/fail reporting.
  - `scripts/run_capability_benchmark.py`

## Verification Commands

```bash
cd ../Mecha-Splicer
PYTHONPATH=. pytest -q
python3 scripts/circuit_mecha_magic_loop.py --max-iters 3
python3 scripts/run_capability_benchmark.py --simulation-fidelity high
python3 scripts/price_lock_workflow.py --spec examples/enclosure_basic.json --out /tmp/mecha_price_lock_demo --high-fidelity --seed-example-overrides
python3 scripts/generate_service_proposal.py --intake docs/business/INTAKE_TEMPLATE.json --out /tmp/mecha_proposal_demo
```

## Remaining Optional Upgrades

- Circuit-AI full manufacturing package API invocation (`/api/v2/manufacture/package`) with real KiCad inputs.
- Supplier API adapters (Shopee/Taiwan vendor feeds) for auto-priced overrides.
- Frontend intake form + dashboard for non-CLI operations.
