# PCB Engine Data Contract

Hardware Splicer keeps one curated module-library source of truth in the frontend:

- `apps/circuit-ai/circuit-ai-frontend/lib/modules/module-library.ts`
- `apps/circuit-ai/circuit-ai-frontend/lib/modules/module-footprints.ts`

The Python PCB engine consumes a generated, versioned deployment resource:

- `src/hardware_splicer/data/engine_pcb_data.json`

Generate it from the repository root after installing frontend dependencies:

```bash
cd apps/circuit-ai/circuit-ai-frontend
npm ci
cd ../../..
node scripts/export_engine_pcb_data.cjs
```

The generated JSON is committed intentionally. Python deployments do not include the frontend TypeScript runtime, so generating the file only during local setup would leave wheels, containers, and clean CI checkouts incomplete.

`pyproject.toml` includes `data/*.json` as `hardware_splicer` package data. The focused test `tests/test_pcb_module_registry_data.py` verifies that:

- the packaged file exists;
- its schema is `hardware_splicer.engine_pcb_data.v1`;
- the module library is nontrivial;
- the `usb-power-5v` module required by the planner is resolvable;
- footprint metadata remains available.

When either TypeScript source changes, regenerate the JSON in the same pull request and inspect the resulting diff. The JSON is a deterministic deployment artifact, not an independent catalog to edit by hand.
