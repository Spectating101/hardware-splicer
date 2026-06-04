# Architecture

Core parts:
- Spec schema: `src/mecha_splicer/spec.py`
- Deterministic generators:
  - DFM checks: `src/mecha_splicer/engines/dfm.py`
  - BOM heuristics: `src/mecha_splicer/engines/bom.py`
  - OpenSCAD emitters: `src/mecha_splicer/engines/openscad.py`
- Bundle writer: `src/mecha_splicer/bundle.py`

Pipelines:
- Spec → bundle: `scripts/mecha_splicer_spec.py`
- Signals → bundles: `scripts/mecha_splicer_mint.py`

Optional external engine:
- 3d‑splicer: `src/mecha_splicer/engines/splicer3d_client.py`

API:
- FastAPI app: `src/api/main.py`
- Bundle endpoint: `POST /v1/bundle`
- Mint endpoint: `POST /v1/mint`
