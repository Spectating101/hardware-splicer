# Hardware-Splicer engine

**Target, gates, and Flux comparison:** [ENGINE_DONE.md](./ENGINE_DONE.md) (canonical).

**Production path:** `scripts/hardware_splicer.py` → `src/hardware_splicer/`.  
Browser `/build` is a demo client until Phase 1 gate **1.5** is PASS.

---

## Target pipeline (general engine)

```
intake | NL | parts | schematic | netlist
  → design IR (components, pins, nets)
  → ERC
  → placement + routing
  → DRC + safety
  → KiCad, Gerbers, BOM, fab zip
  → DESIGN_QUALITY gate
```

## Bootstrap pipeline (what runs today)

```
intake / archetype / phrase
  → plan_to_graph (recipe | compose | capability fallback)
  → build_graph.json (module nodes + wires)
  → pcb/ geometry → DRC → KiCad
  → BOM, firmware scaffold, Gerber, fab zip
  → DESIGN_QUALITY gate
```

Python-only on the success path. No Node required for compile.

| Data | Path |
|------|------|
| Recipes | `data/catalog_recipes.json` — `make export-catalog-recipes` |
| Module library | `data/engine_pcb_data.json` — `make export-engine-pcb-data` |
| PCB stack | `src/hardware_splicer/pcb/` |

Legacy Node scripts (`compile_geometry.cjs`, `compile_build_graph.cjs`) are parity/dev only.

---

## CLI

```bash
# Catalog build
PYTHONPATH=src python3 scripts/hardware_splicer.py build \
  --build-id automatic_plant_watering --out /tmp/out --no-gerber

# Scratch compose (NL or module list)
PYTHONPATH=src python3 scripts/hardware_splicer.py compose \
  --phrase "something that measures temperature" --out /tmp/out

# Intake brief → salvage → compile
PYTHONPATH=src python3 scripts/hardware_splicer.py splice-build \
  --brief examples/intakes/scratch_compose_brief.json --out /tmp/out
```

## API

| Endpoint | CLI equivalent |
|----------|----------------|
| `POST /v1/compile-build` | `build` |
| `POST /v1/splice-and-build` | `splice-build` |
| `POST /v1/compose` | `compose` — **not implemented yet** (gate 6.3) |

---

## Phase status (summary)

| Phase | Status |
|-------|--------|
| 0 Bootstrap compiler | Mostly done |
| 1 Bootstrap hardening | In progress — see [ENGINE_DONE.md §7](./ENGINE_DONE.md#7-phase-1-gates--bootstrap-hardening) |
| 2 General IR | Not started |
| 3 General compile (Flux engine bar) | Not started |
| 4 Frontend | Blocked |

Detail and per-gate PASS/OPEN: [ENGINE_DONE.md](./ENGINE_DONE.md).

---

## Tests

```bash
make verify-catalog
make test-golden-intakes
make test-compose-scenarios
make test-scratch-pipeline
PYTHONPATH=src pytest tests/ -q --ignore=tests/integration
```

Golden intakes: `examples/intakes/golden_compile_manifest.json` (6 cases today; gate 2.3 = 18).

---

## Catalog parity

`CATALOG_BUILD_IDS` in `src/hardware_splicer/catalog.py` must match `SUPPORTED_BUILD_IDS` in `lib/salvage/plan-to-graph.ts` until gate **1.5** removes TS from the compile path.

```bash
node scripts/verify_catalog_parity.cjs
PYTHONPATH=src pytest tests/test_catalog_parity.py -q
```

---

## Graph stage contract

Contract version: **3** (`GRAPH_STAGE_CONTRACT_VERSION` in `compile_stages.py`).

Success payload includes `quality.drc_pass`, paths to `build_graph.json`, `main_ctrl_build.kicad_pcb`, `DESIGN_QUALITY.json`.
