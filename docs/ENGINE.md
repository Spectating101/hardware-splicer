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

The digital study engine runs directly from Python or the CLI. It uses the existing project store and job queue; it does not start an HTTP server, browser, or frontend. Its server-owned registry contains three bounded device families:

| Case ID | Device and native engineering work |
| --- | --- |
| `hs3g-b` (default) | Existing drone assembly, native PyBullet dynamics, payload/gust/mass studies |
| `fielddeck-7` | Cyberdeck enclosure, checked mounts and fastener/tool envelopes, sourced display geometry, power/runtime/structural sensitivity studies |
| `fielddeck-5` | Five-inch display revision with retained source geometry, ribbon clearance and workload/runtime studies |
| `ender3-penplotter` | Published classic Ender-3 reference donor, parametric pen and hotend-parking mounts, emitted G-code and drawing-trajectory checks |

The plotter uses a documented reference donor inventory. The cyberdeck and plotter cases execute fresh native scripts before publishing revision 1. Later revisions use the cancellable job queue and compare-and-swap publication.

Install from a repository checkout with `python -m pip install -e '.[digital]'` for the cyberdeck and plotter. Use `python -m pip install -e '.[drone-sim]'` for the drone case. `HARDWARE_SPLICER_DIGITAL_PYTHON` can select a separate native interpreter. See the [backend install and service setup](PACKAGING_AND_DEPLOYMENT.md#current-headless-backend).

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

Use `engine.cases()` to inspect supported numeric requirements. For a cyberdeck study, select `engine.create(case_id="fielddeck-7")`, then pass explicit overrides to `run_revision`, such as `requirements={"minimum_work_runtime_h": 3, "pi_work_current_a": 2.2}`. An intact computation can correctly report unmet engineering requirements. The fixed module layout is checked explicitly; unsupported dimensional edits are rejected instead of being hashed over unchanged solids.

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

### Selecting and reproducing another device case

`hs-digital cases` lists each case's numeric keys and ranges. Select one with `init --case fielddeck-7` or `init --case ender3-penplotter`. To revise a new device case, write overrides to a JSON file, for example `{"minimum_work_runtime_h": 3, "pi_work_current_a": 2.2}`, then run `revise PROJECT_ID --base-revision 1 --requirements changes.json`. Free-text changes label these studies; their explicit numeric overrides define the computation. The drone's existing payload phrases and flags continue to work.

Every new-case ZIP contains `STUDY_README.md`, selected requirements, frozen source inputs and licenses, generated CAD/simulation files, quantitative constraints and independent verification. The entry document gives the exact included script sequence. Captured source documentation may also describe a separate standalone delivery; use the study entry document when rerunning the backend ZIP.

Historical studies retain their original input bytes. Native audit reruns the included verifier in scratch, including calculation or emitted-trajectory checks, without changing the saved revision. The case registry and nested-file allowlist reject unknown cases, arbitrary executable paths and symlink traversal. `GET /v1/digital/cases` exposes the same case descriptions through HTTP, and `POST /v1/digital/projects` accepts an optional `case_id`.

The [dated device execution record](status/generated/device-engineering-20261117.json) retains actual cyberdeck and plotter revision results, native audits, source hashes and remaining physical unknowns. Its proof records distinguish model requirements from artifact integrity.

## Native source editing and splicing

Registered KiCad sources now connect to the existing editable-candidate workflow.
This path keeps supplied native geometry instead of recompiling it through generic
module footprints. It works on a selected project stem, with a PCB and/or schematic
and optional matching `.kicad_pro` and `.kicad_dru` files.

Create a normal project and upload each file through
`POST /v1/projects/{id}/sources/ingest`, using the current `expected_revision` for
each upload. Keep the returned source IDs and revision. Then call
`POST /v1/projects/{id}/sources/promote-to-editable` with `expected_revision` and
optional `source_ids` or `primary_source_id`. Multiple project stems require an
explicit selection. Only same-project, hash-verified upload bytes are used; callers
cannot supply output paths or executable commands. Original sources and prior
revisions remain unchanged.

Promotion copies exact bytes to a fresh controlled workspace and saves one project
revision. The SDK exposes the same operation and the existing candidate editor:

```python
from hardware_splicer.sdk import promote_source_bundle, propose_native_edit, export_native_edit

imported = promote_source_bundle(
    "PROJECT_ID", project_root="/tmp/hs-projects", expected_revision=4,
    source_ids=["PCB_SOURCE_ID", "PROJECT_SOURCE_ID", "RULE_SOURCE_ID"],
)
proposal = propose_native_edit(
    "PROJECT_ID", project_root="/tmp/hs-projects", base_revision=imported["revision"],
    kind="pcb", ops=[{"op": "move", "ref": "J1", "x_mm": 35, "y_mm": 22}],
    note="Move the supplied connector",
)
candidate = proposal["candidate"]
native_zip = export_native_edit("PROJECT_ID", candidate["candidate_id"], project_root="/tmp/hs-projects")
```

Use a reference/UUID actually present in the supplied design. Supported edits move
or rotate native objects, change properties/track widths, and perform the existing
bounded schematic edits. Moving a footprint does not automatically reconnect its
old copper; native checks report introduced violations. The proposal stays pending
and does not advance the active project revision. Existing review decisions govern
acceptance. Both candidate and general-review acceptance revalidate the exact
primary and rule bytes.

`GET /v1/projects/{id}/candidates/{candidate}/native-bundle` exports the edited
PCB/schematic, exact same-stem rule companions and a hash manifest. Repeated exports
of unchanged candidates produce the same ZIP bytes. Original `.kicad_pro` and
`.kicad_dru` settings are carried into native before/after checks and accepted
revision retention. Standalone files remain editable, with an explicit defaults-only
or custom-rules-only check scope. This does not close external library or
hierarchical-sheet dependencies; unresolved libraries remain visible in native
findings. Unsupported custom-rule directives such as includes are rejected.

`POST /v1/projects/{id}/native/check` accepts `expected_revision` and `kind`
(`pcb` or `schematic`). The SDK equivalent is `check_native_design`. These read-only
operations check the exact retained revision and rule bytes, including accepted
edits or an explicitly requested historical revision. Results distinguish check
execution from rule findings; an unavailable tool never reports a successful
check. The AI `run_drc`/`run_erc` actions use this retained design when present.
`inspect_registered_sources` continues to inspect the original uploads.

The project engineering executor now accepts `promote_registered_sources` and
`propose_kicad_edit`. Structured `run_compose` actions preserve explicit netlists,
canvas connections, resolved modules and splice plans. Action input schemas are
published by `GET /v1/engineering/ai/tools/schema`. Native edit execution uses an
immutable receipt without creating a bookkeeping revision that would stale its
review. `GET /v1/projects/{id}/ai-sessions/{session}/actions/{action}/execution`
returns the receipt and live review state. Repeated/concurrent retries reuse the
same proposal; changed source identities require a new action.

Each source change records `sourceRevisionImpact` for native checks, mechanical fit,
wiring, materials, firmware, 3D models and manufacturing packages. Inherited passed
or running canonical verifications become blocked, so the existing release
assessment requires new evidence. Historical evidence remains retained. Native
candidate checks record their own fresh result; other families require explicit
rechecks rather than an assumed enclosure or firmware regeneration.

The generic compile path also preserves supplied references, alphanumeric pad IDs,
singleton nets and named nets. Unresolved catalog IDs fail without disappearing
from the request record. Unfamiliar physical packages remain clearly labeled
logical previews with fabrication blockers; clean rule checks cannot turn generic
through-hole preview geometry into an exact QFN or connector footprint. Use the
native source path when supplied footprint geometry must be retained.

The [dated source workflow evidence](status/generated/source-workflow-connection-20261118.json)
records the real-board edit/recheck/export probe, generic package fidelity checks,
full-suite coverage and remaining limits.

## Part substitution across a declared assembly

Supply an assembly and one replacement profile. HS reports which interfaces
match, which require adaptation, and which specifications are missing. Profiles
can describe purchased parts or salvaged parts using the same fields for identity,
functions, dimensions, mounting points, connectors, contact functions, protocol,
voltage, current and stored energy.

The replacement inherits the original assembly slot and placement. HS checks
each connected load against the full supply voltage range and counts unchanged
loads in the current budget. It reports connector, pin, protocol, enclosure and
mounting conflicts. Power and runtime comparisons use steady-state declarations
and require a complete, compatible power path. The assessment scope excludes
timing, drivers, negotiation, transients and mechanical tolerances.

Use `GET /v1/engineering/parts/substitution/schema` for the typed request.
`POST /v1/projects/{id}/parts/substitutions` accepts `expected_revision`,
`specification` and optional `generate_geometry`. The assessment is stored
alongside that revision. A profile can bind its intrinsic specifications to a
JSON upload using `{source_id, content_hash, pointer}`. Placement and assembly
identifiers are design choices. Source binding verifies the supplied declaration
against the registered file.

```python
import json
from hardware_splicer.sdk import assess_part_substitution, export_part_substitution

with open("examples/part_substitution/cyberdeck-display-replacement.json") as source:
    specification = json.load(source)
assessment = assess_part_substitution(
    "PROJECT_ID", project_root="/tmp/hs-projects", expected_revision=2,
    specification=specification, generate_geometry=True,
)["assessment"]
bundle = export_part_substitution(
    "PROJECT_ID", assessment["assessment_id"], project_root="/tmp/hs-projects",
)
```

The bundle contains the report, revised assembly, BOM CSV, connection plan and
available native geometry. Optional CAD includes nominal assembly and replacement
STEP/STL. When a supported rectangular hole pattern needs an adapter, explicit
thickness and edge allowance can drive a plate proposal. Reimport checks confirm
body placement, volume and drilled hole geometry. Fastener access, plate strength,
adapter clearance inside the enclosure and physical fit require further evidence.

`GET /v1/projects/{id}/parts/substitutions/{assessment}/bundle` returns the
hash-checked ZIP. `POST .../{assessment}/propose` opens a pending review on a
normal project with a canonical `machineProject`. The SDK equivalent is
`propose_part_substitution`. Acceptance retains the revised `partAssembly` as
the baseline for the next assessment and marks inherited engineering checks for
recheck. Missing revised port mappings must be resolved before proposal.
Historical studies remain available for export. Registered digital cases use
substitution studies as separate assessments. Revised native electrical checks
require a retained board or schematic for the revised assembly.

The backend MCP discovers these operations through the canonical API. The
[example runner](../examples/part_substitution/run_declared_examples.py) compares
three independent cyberdeck swaps, an unidentified donor and a telemetry sensor
using fictional simulation profiles.
The [execution record](status/generated/part-substitution-proof.json) includes
the modeled power and runtime changes and the native export hashes.

### Fielddeck 5 display revision

The [Fielddeck display study](../projects/cyberdeck-real-trial-20261020/display_swap/build.py)
uses the retained Fielddeck 7 assembly and Raspberry Pi's manufacturer STEP for
the 5-inch Touch Display 2 (SC1975). It rebuilds the two rear face panels and two
rear tray panels around the smaller display. Four spacers represent the difference
between the STEP mounting seat and the deeper seat in the product drawing. The
case study retains both source dimensions in the report.

The backend compares the display interface using `evaluate_substitution`.
Its 10-inch control case must report a protocol mismatch against the existing
Pi 4 display port. The native study checks the bezel opening, screw paths and
reserved ribbon access from the Pi toward the display. Its centreline gives a
length budget. The detailed connector exits, bends, contact ratings and screw
engagement still need evidence. Power scenarios keep the original stress
allocation and use the published display consumption in the work scenario.

The headless engine lists this study as `fielddeck-5`. Start one with
`hs-digital init --case fielddeck-5`. Use its project ID with `inspect`,
`audit --native` and `export`. The sealed ZIP includes the exact prior
Fielddeck assembly, display source and substitution evaluator along with the
updated STEP/GLB, print parts, BOM and engineering results.

Submit a revision with `revise PROJECT_ID --base-revision 1 --requirements FILE`.
The four numeric fields are `minimum_work_runtime_h`,
`minimum_supply_margin_a`, `pi_work_current_a` and `keyboard_current_a`.
Changing them recomputes work power, runtime, and supply margin against the same
retained source geometry. A completed study with an unmet target can still be
inspected, compared and exported.

From the repository root, run the study with the project's CadQuery and trimesh
environment. Choose a fresh output directory.

```bash
PYTHONPATH=src python projects/cyberdeck-real-trial-20261020/display_swap/build.py \
  --output /tmp/fielddeck-5
python projects/cyberdeck-real-trial-20261020/display_swap/bundle.py \
  --build /tmp/fielddeck-5 --output /tmp/fielddeck-5.zip
```

The ZIP contains the revised assembly STEP/GLB, changed and retained print
parts, BOM, wiring notes, power comparison and source/geometry evidence.
The [standalone execution record](status/generated/fielddeck-display-swap-20261118.json)
retains the source hashes, modeled results and checks from the original display swap.
The [registered study record](status/generated/fielddeck-5-registered-20261118.json)
captures the baseline and higher-load comparison, the independent native audit and
both archive hashes.

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

## Project wiring and harness review

`hs-wiring` extends the same material assessment into an explicit pin-to-pin harness. The Python SDK, CLI, canonical API and OpenAPI-derived MCP operations use the same engine. Assessments live beside the project, bound to its revision, snapshot hash and material assessment. Creating a wiring assessment does not advance the design revision or alter a digital study.

```bash
hs-wiring --project-root /tmp/hs-projects assess PROJECT_ID \
  --expected-revision 1 --materials MATERIAL_ASSESSMENT_ID \
  --specification examples/wiring/hs3g_b_receiver.json
hs-wiring --project-root /tmp/hs-projects csv PROJECT_ID WIRING_ASSESSMENT_ID
hs-wiring --project-root /tmp/hs-projects export PROJECT_ID WIRING_ASSESSMENT_ID \
  --output /tmp/new-wiring-review.zip
```

The [receiver example](../examples/wiring/README.md) requires an additional conductor requirement in metres; the old bundled wiring allowance cannot substitute for an itemized wire. See that example's preparation code. It is a partial draft on the existing drone, with provisional lengths and unresolved physical pinout/rating evidence.

Each endpoint describes one component instance, its material ID, pin viewing orientation and explicit pin contracts. Pin roles are `power_out`, `power_in`, `ground`, `signal_out`, `signal_in` or `unknown`. Power `voltage.minimum/maximum` describes the operating range; `current_a` is output capacity or worst-case input demand. Signal `high` and `low` specify output level ranges or accepted input level ranges separately. `signal` identifies the intended signal family. Active pins name their endpoint's ground `reference_pin`. Pins marked `required: "yes"` must be connected. Unsupported bidirectional/open-drain behavior remains unresolved rather than becoming a single-driver signal claim.

Each wire supplies its exact endpoints, material ID, declared `length_m`, optional color and wire contract. Endpoint requirements use `ea`; wire requirements use `m`. Quantities aggregate across all endpoint instances and wire cuts. The engine rejects implicit unit conversions and flags mismatched identities, additional material specifications or quantities exceeding the attached assessment. An endpoint represents a component interface, so a native WireViz BOM's connector row does not independently establish the connector housing/contact/termination parts needed to construct it.

Checks operate on entire connected nets. They detect power-to-ground and incompatible role connections, multiple outputs, out-of-range supply voltage, aggregate load exceeding the selected output, incompatible digital high/low ranges and disconnected/different ground references. Supply and return conductor checks use declared net demand conservatively. AWG never supplies an inferred ampacity. Missing ratings, unknown pins, unbound contract sources and unassessed signal loading/timing stay explicit issues. Shared regulator budgets across separate output pins, transients, voltage drop, conductor routing/fit, terminations, protocol behavior and complete-device coverage remain outside this check.

Optional `source` on an endpoint or wire has `source_id`, canonical `content_hash` and an RFC 6901 `pointer` (empty means the root) into a retained JSON engineering source. It must belong to `engineeringSources` on this same project revision. HS rereads the registered bytes, verifies their hash, parses the selected contract and compares it to the supplied contract. This binds the declaration to retained data; it does not authenticate a manufacturer, prove that a human extraction is correct, or raise uploaded source authority. Omitted bindings remain `unbound_declaration`. Missing/mismatched supplied bindings are rejected. Rereading an assessment repeats the source, materials, report and generated-instruction checks; historical records remain readable with `current_for_project: false` after later revisions.

The default export requires no external renderer: JSON-formatted YAML for [WireViz](https://github.com/wireviz/WireViz), a conductor cut-list CSV and an assessment ZIP. Use `--render` to invoke a separately installed WireViz CLI and Graphviz locally and add a native SVG and TSV BOM. Set `HARDWARE_SPLICER_WIREVIZ_EXECUTABLE` to a dedicated executable, or place `wireviz` on `PATH`; `dot` must be on `PATH`. No third-party code is vendored and no renderer dependency is added to the core install. WireViz 0.4.1 was exercised; its GPL-3.0 CLI remains a separate optional tool. The existing [InvenTree WireViz plugin](https://github.com/inventree/inventree-wireviz) can consume `.wireviz` files, but HS performs no plugin upload or remote BOM mutation.

Only generated connector/cable/connection data reaches the renderer. HS does not accept arbitrary WireViz YAML, images, include paths or command arguments. Text is escaped, execution and output sizes are bounded, active/external SVG content is rejected and spreadsheet exports keep formula-looking values as text. The native diagram visibly includes its digital review status. A failed explicit render publishes no assessment; callers can retry without rendering.

```python
from hardware_splicer.sdk import assess_wiring, export_wiring

result = assess_wiring("PROJECT_ID", project_root="/tmp/hs-projects", expected_revision=1,
    material_assessment_id="materials-...", specification=harness, render=False)
package = export_wiring("PROJECT_ID", result["assessment"]["assessment_id"],
                        project_root="/tmp/hs-projects")
```

The API provides `POST /v1/projects/{id}/wiring/assess`, `GET /v1/projects/{id}/wiring`, `GET /v1/projects/{id}/wiring/{assessment_id}`, and `/csv`, `/wireviz`, `/export` downloads on that assessment. MCP callers can request `response_mode: "base64"` for the binary ZIP. Results distinguish `blocked`, `unresolved` and `passes_declared_checks`. All retain `construction_ready: false`, `complete_device_compatibility_verified: false` and `physical_authority_granted: false`.

### SO-ARM102 follower drive

Use this offline reference to choose a motor for the shoulder or elbow of the
Robonine SO-ARM102 follower. HS joins the purchase variant, bus ID, cable run,
shared printed arm and simulated joint at one upstream revision. The report
includes source links and the two purchase listings recorded by the project.
Stock and pricing require a current supplier check.

```bash
hs-digital so102-drive shoulder --passive-leader --angle-deg 120 > shoulder.json
hs-digital so102-drive elbow --angle-deg 120 > elbow.json
jq '.report | {drive, mount, travel_check, swap: .substitution.status}' shoulder.json
```

Both positions use the Feetech ST-3250-C002 on the 12 V follower bus. The passive
leader option omits the motor and gearbox and fails the powered-drive requirement.
The two lower-arm prints and sixteen M2×6 screws belong to the shared assembly
step. Counting that hardware once per servo would double the order. The STEP
envelope measures 113 × 34 × 20 mm for one print. A target of +120° from the
CAD zero pose exceeds the shoulder limit and fits inside the elbow limit.
Load, motion through obstacles and fit of a replacement servo remain open.

To try a different servo, pass a JSON PartProfile with the donor facts you have.
Use port IDs `power` and `bus` for the two logical interfaces on the servo cable.
An example profile below describes a hypothetical salvaged servo whose documented
input range ends at 8.4 V.

```json
{
  "part_id": "salvaged-servo",
  "name": "Spare serial servo",
  "functions": ["powered_joint_drive"],
  "ports": [
    {"port_id": "power", "kind": "power", "direction": "input", "voltage_range_v": [6, 8.4]},
    {"port_id": "bus", "kind": "signal", "direction": "bidirectional", "protocol": "Feetech TTL serial bus"}
  ]
}
```

```bash
hs-digital so102-drive elbow --candidate donor.json | jq '.report.substitution | {status, failed: [.checks[] | select(.status == "fail")]}'
```

The follower supply exceeds that donor’s declared range. A blank rating leaves
the electrical question open. A successful command means the assessment ran.
Read `substitution.status` for the donor decision and
`travel_check.within_joint_limits` for the position decision.

The installed package contains a small reference derived from Robonine’s
[SO-ARM102 source and license notices](https://github.com/roboninecom/SO-ARM102/tree/43252799d077e7f9971d7c695fd59f31413aa9b6).
From an HS checkout with the digital extra installed, rebuild it using the
upstream checkout at that revision. The recipe checks all six source digests
before opening the STEP solid and parsing the URDF.

```bash
python -m scripts.prepare_so102_drives /path/to/SO-ARM102 rebuilt.json
cmp rebuilt.json src/hardware_splicer/data/so102_follower_drives.json
```
