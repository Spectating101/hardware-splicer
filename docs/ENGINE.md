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

# General engine: netlist IR → KiCad (no module picker)
PYTHONPATH=src python3 scripts/hardware_splicer.py netlist-compile \
  --netlist examples/netlist_fixtures/json/usb_esp_dht22.json --out /tmp/out

PYTHONPATH=src python3 scripts/hardware_splicer.py compose \
  --netlist-json examples/netlist_fixtures/json/usb_esp_dht22.json --out /tmp/out

# Intake brief → salvage → compile
PYTHONPATH=src python3 scripts/hardware_splicer.py splice-build \
  --brief examples/intakes/scratch_compose_brief.json --out /tmp/out
```

## API

| Endpoint | CLI equivalent |
|----------|----------------|
| `POST /v1/compile-build` | `build` |
| `POST /v1/splice-and-build` | `splice-build` |
| `POST /v1/compose` | `compose` |
| `POST /v1/netlist-compile` | `netlist-compile` (general IR path) |

---

## Phase status (summary)

| Phase | Status |
|-------|--------|
| 0 Bootstrap compiler | Mostly done |
| 1 Bootstrap hardening | In progress — see [ENGINE_DONE.md §7](./ENGINE_DONE.md#7-phase-1-gates--bootstrap-hardening) |
| 2 General IR | **Done** — netlist IR, lowering, KiCad import |
| 3 General compile | **Done** — ERC, placement, cosmetic copper, DRC; 18 netlist fixtures |
| 4 Frontend | Blocked on gate **1.5** (TS compile fork) |

Detail and per-gate PASS/OPEN: [ENGINE_DONE.md](./ENGINE_DONE.md).

### General engine verify

```bash
make verify-netlist-engine
PYTHONPATH=src pytest tests/test_netlist_fixtures.py -q
```

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

## Headless digital engineering

The digital study engine runs directly from Python or the CLI. It uses the existing project store and job queue; it does not start an HTTP server, browser, or frontend. The current registered proving case is HS-3G-B, with representative CAD and native PyBullet dynamics. It is a bounded case inside the broader engineering engine, not an arbitrary hardware redesign interface.

Install the repository and native dependencies with `python -m pip install -e '.[drone-sim]'`. In this workspace the base environment can also use the native interpreter selected by `HARDWARE_SPLICER_DIGITAL_PYTHON`, or the prepared project-cache native environment. No model-service key or physical parts are required.

```python
from hardware_splicer.sdk import digital_engine

with digital_engine(project_root="/tmp/hs-digital-projects", job_db="/tmp/hs-digital-jobs.sqlite3") as engine:
    project = engine.create(name="Digital payload study")["project"]
    project_id = project["project_id"]
    completed = engine.run_revision(
        project_id, base_revision=1, change_request="Add 10 g of payload"
    )
    comparison = engine.compare(project_id, before_revision=1, after_revision=2)
    audit = engine.audit(project_id, 2, native=True)
    delivery = engine.export(project_id, "/tmp/hs-payload-study.zip", 2)
```

The equivalent CLI is `hs-digital`, or `python -m hardware_splicer.digital_engine_cli`. Pass `--project-root` and `--jobs-db` consistently across processes. `init` returns the project ID as JSON; use that ID for subsequent commands.

```bash
hs-digital --project-root /tmp/hs-digital-projects --jobs-db /tmp/hs-digital-jobs.sqlite3 init
# Substitute the returned project ID for PROJECT_ID below.
hs-digital --project-root /tmp/hs-digital-projects --jobs-db /tmp/hs-digital-jobs.sqlite3 revise PROJECT_ID --base-revision 1 --change 'Add 10 g of payload'
hs-digital --project-root /tmp/hs-digital-projects --jobs-db /tmp/hs-digital-jobs.sqlite3 compare PROJECT_ID --before 1 --after 2
hs-digital --project-root /tmp/hs-digital-projects --jobs-db /tmp/hs-digital-jobs.sqlite3 audit PROJECT_ID --revision 2 --native
hs-digital --project-root /tmp/hs-digital-projects --jobs-db /tmp/hs-digital-jobs.sqlite3 export PROJECT_ID /tmp/hs-payload-study.zip --revision 2
```

`revise` runs synchronously by default. Add `--enqueue` to persist the task and exit; a separate `work PROJECT_ID --max-jobs 1` process claims and executes it. `inspect`, `history`, `job`, `cancel` and `retry` expose durable state. A worker claims only the selected project's digital jobs. Opening an engine to inspect state does not recover, cancel or restart another worker. Failed or cancelled jobs can be retried while their base revision is still current; changing requirements after a completed run creates a new revision instead.

Payload changes support `Add 10 g of payload`, `Remove 5 g of payload`, or `Set payload to 10 g`. Structured Python requirements and CLI `--payload-g`, `--gust-scale` and `--max-mass-g` avoid prose parsing. Payload is bounded to 0–50 g, gust force scale to 0–3, and the mass limit to 150–500 g. Gust scale multiplies the declared force vector; it is not a wind-speed estimate. The solver recomputes geometry, mass, centre of mass, inertia and three physics cases using the resolved requirements.

Comparison is a backend result: it reports requirement changes, mass and tracking/current deltas, centre-of-mass/inertia changes, and resolved or regressed constraint checks. Audit validates revision ownership, execution-attempt identity, cached claims against their hashed model/contract/results, all artifact bytes, and the ZIP inventory/content. Native audit runs the separate native verifier on a temporary copy, preserving the published receipt. Historical summaries use their archived contract. A native recheck against changed source can fail source identity without changing the archived record.

A successful computation can fail its engineering requirements. Such a run remains saved and exportable. Completed `revise`/`work` commands return exit **0** for passed requirements, **2** for intact computations with failed requirements, and **1** for execution/data errors. Queuing, inspection, audit and export report the success of that operation; inspect the explicit `requirements_met` field for the design verdict. Nothing here grants physical validation, fabrication, power-on or flight authority. Exports verify the package and refuse to overwrite existing files.

Job attempts have durable random identities, independent of wall-clock timestamps. Completion, failure and publication from an old attempt cannot update a retry, even when timestamps are identical. Existing job databases migrate additively without discarding their records.

The canonical HTTP adapter uses this same engine. In addition to create/inspect/submit/artifact routes, it exposes `GET /v1/projects/{id}/digital/compare?before_revision=1&after_revision=2`, `GET /v1/projects/{id}/digital/revisions/{revision}/audit`, and `POST /v1/projects/{id}/digital/revisions/{revision}/verify`. The canonical MCP gateway discovers these through OpenAPI; no second MCP implementation owns their rules.

## Exact materials and InvenTree inventory

The backend compares a design's material requirements with available inventory and produces a reusable/missing/make list. It accepts a declared inventory or imports a direct assembly BOM and inventory from [InvenTree](https://github.com/inventree/InvenTree). The integration reads the upstream REST API. Local assessments work independently of an inventory server.

`hs-materials` operates on an existing saved project. Assessments are retained beside that project and bound to its exact revision and snapshot hash. They leave the design revision, simulation history and authority fields intact. Later design changes mark earlier assessments as historical. Opening a saved assessment validates its inputs, computed claims and source identity.

```bash
# Use the project ID returned by hs-digital init or the normal project API.
# Omitting --inventory explicitly declares that you have no parts.
hs-materials --project-root /tmp/hs-digital-projects assess PROJECT_ID \
  --expected-revision 1 \
  --requirements examples/materials/hs3g_b_requirements.json
hs-materials --project-root /tmp/hs-digital-projects history PROJECT_ID
hs-materials --project-root /tmp/hs-digital-projects csv PROJECT_ID ASSESSMENT_ID
```

The [drone requirements example](../examples/materials/hs3g_b_requirements.json) derives from the retained HS-3G-B BOM and native hardware calculation. It expands bundled hardware into individual fasteners and separates the frame parts to make. Purchase quantities include the source BOM's spare battery and prop packs. The unitemized wiring allowance, discontinued controller sourcing and unspecified laminate grade remain visible issues. Manufacturer/model identifiers and standard material specifications are declared source identities; this file supplies no new supplier quote or stock check.

Each requirement has `material_id`, `description`, `quantity`, `unit` (default `ea`), and either `manufacturer` plus `mpn`, or an explicit `specification`. `source_ref` identifies its basis. `acquisition: "make"` identifies a custom item. `unresolved` preserves missing specifications. A declared inventory has `source: "declared"`, a timezone-aware `captured_at`, and `lots`; each lot supplies its exact identity/specification, quantity, allocated amount, unit and condition. Only `condition: "ok"` stock covers requirements. Matching uses an explicit InvenTree part binding, exact manufacturer/model, or exact material specification. Units and any additional specifications must agree.

The Python SDK exposes the same service:

```python
from hardware_splicer.sdk import assess_materials

assessment = assess_materials(
    "PROJECT_ID", project_root="/tmp/hs-digital-projects", expected_revision=1,
    requirements=required_materials, inventory=declared_inventory,
)
```

For InvenTree, configure `HARDWARE_SPLICER_INVENTREE_URL` and `HARDWARE_SPLICER_INVENTREE_TOKEN` in the backend process. Use a user/token with view permissions. Remote connections require HTTPS; loopback HTTP supports local development. Credentials stay outside project records and CLI arguments.

```bash
hs-materials --project-root /tmp/hs-digital-projects import-inventree PROJECT_ID \
  --expected-revision 1 --assembly-part-id 123 --build-quantity 1
```

The connector reads the assembly's direct BOM, component identities, stock lots and cached supplier references. It deducts server-reported allocations and excludes damaged, unchecked, expired, installed and unsupported custom-status stock. It consumes all pages within bounded requests and rejects incomplete or conflicting pagination. Duplicate BOM requirements share one planned stock balance. It never allocates or reserves remote stock.

Supplier quantities remain cached inventory-server information; they do not count as owned parts or establish a live vendor quote. Nested assemblies and unsupported BOM quantity adjustments remain review issues. Captures older than 24 hours, more than five minutes in the future, or marked simulated do not cover owned-stock requirements. Saved results retain their original evaluation; reads also report current inventory age and whether the design revision has changed. Exact inventory identity does not establish electrical, mechanical or firmware compatibility.

The canonical API provides `POST /v1/projects/{id}/materials/assess`, `POST /v1/projects/{id}/materials/import-inventree`, `GET /v1/projects/{id}/materials`, `GET /v1/projects/{id}/materials/{assessment_id}`, and a `/csv` download on that assessment. MCP discovers the same operations from OpenAPI. Assessments record whether the inputs came from a provided snapshot or an actual InvenTree HTTP read. Assessments and exports do not grant purchase, fabrication or physical authority.
