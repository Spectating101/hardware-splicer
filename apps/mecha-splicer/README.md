# Mecha‑Splicer

Mechanical “splicing” engine + product pipeline: **signals → templates → DFM/BOM → 3D artifacts → bundle**.

This is the mechanical sibling to Circuit‑Splicer, built for:
- 3D‑printed enclosures, mounts, brackets, fixtures, jigs
- Electromechanical integration (EE constraints drive ME deliverables) — without needing “full ME” first

## Quickstart (local)

1) Generate a bundle from an explicit spec:
- `python3 scripts/mecha_splicer_spec.py --spec examples/enclosure_basic.json --out /tmp/mecha_bundle`

2) Generate bundles from RSS demand signals (prototype pipeline):
- `python3 scripts/mecha_splicer_mint.py --signals rss --max-categories 3 --max-results 6`

3) Run the API:
- `python3 scripts/run_api.py` (serves on `127.0.0.1:8085`)

## 3d‑splicer integration (optional)

If you run `3d-splicer` locally, Mecha‑Splicer can ask it for a CadQuery script or STL for PCB‑style enclosures.

- Set `SPLICER_API_URL` (default: `http://127.0.0.1:8000`)
- Use `--render-stl` to request `/v1/splice` (requires CadQuery in the 3d‑splicer environment)

## Docs

- `docs/ARCHITECTURE.md`
- `docs/SPEC.md`
- `docs/MINT_PIPELINE.md`
- `docs/COMMERCE.md`
- `docs/MECHANISMS.md`
- `docs/STATUS.md`

## High-ROI Operations

- Magic loop: `python3 scripts/circuit_mecha_magic_loop.py --max-iters 3`
- Capability benchmark: `python3 scripts/run_capability_benchmark.py --simulation-fidelity high`
- Pricing lock workflow: `python3 scripts/price_lock_workflow.py --spec examples/enclosure_basic.json --out /tmp/mecha_price_lock_demo --high-fidelity --seed-example-overrides`
- Proposal generation: `python3 scripts/generate_service_proposal.py --intake docs/business/INTAKE_TEMPLATE.json --out /tmp/mecha_proposal_demo`

See `docs/business/HIGH_ROI_CHECKLIST_2026-03-01.md` for status and validation commands.
