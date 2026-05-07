# Salvage-To-Product Workflow

Circuit-AI's salvage workflow is the end-to-end path from electronic junk,
spare boards, modules, or market listings to a build, resale, or sourcing
decision.

## One-Command Run

```bash
python3 scripts/salvage_to_product.py assets/samples/test_pcb.png \
  --backend hybrid \
  --ocr \
  --no-commit \
  --output-dir eval/salvage_to_product
```

Artifacts written:

- `analysis.json`: scan, board understanding, OCR/marking, connector map, AOI
- `workflow_report.json`: inventory, opportunities, recipes, execution decision
- `build_package.json`: work order, BOM, validation, wiring, firmware, selling plan
- `README.md`: operator-readable summary

Use `--inventory data/salvage_inventory.json` to keep a persistent inventory.
Use `--no-commit` for dry runs.

## Listing Input

Listing JSON can be used for e-commerce arbitrage or sourcing checks:

```json
{
  "id": "lot-1",
  "title": "ESP32 relay board lot",
  "price_usd": 6.0,
  "shipping_usd": 2.0,
  "labor_usd": 1.5,
  "failure_rate": 0.15,
  "fee_rate": 0.13,
  "expected_capabilities": ["wireless", "actuator_driver", "power"],
  "expected_parts": ["esp32", "relay"]
}
```

Run:

```bash
python3 scripts/salvage_to_product.py --listing listing.json --output-dir eval/listing_run
```

## API Surface

- `POST /analyze`: scan a PCB/device image. For production AOI gates it can now
  accept `reference_counts`, `reference_topology`, `golden_file`, and
  `aoi_profile` together.
- `POST /salvage/pipeline`: images/listings to workflow report and build package
- `POST /salvage/splice-plan`: reusable blocks, safe measurements, adapter
  circuits, wiring steps, and value-proof fields for rewiring/reuse
- `POST /salvage/splice-case`: create a tracked reuse case with review,
  capture, measurement, and first-build tasks
- `POST /salvage/portfolio-plan`: combine a pile of junk devices into ranked
  builds, safety holds, allocated reusable blocks, missing capability gaps, and
  a first-week work order
- `GET /salvage/workflow`: current persistent inventory and decision report
- `GET /salvage/build-package`: current build package only
- `POST /salvage/analysis`: ingest an existing analysis result
- `POST /salvage/listing`: ingest a listing
- `POST /salvage/assets/{asset_id}/test`: update test status and condition
- `GET /board-sessions/aoi-calibration`: outcome-backed calibration report for
  production AOI release/hold decisions
- `GET /board-sessions/{session_id}/evidence-graph`: source/claim graph that
  shows which captures, measurements, reviews, gates, and outcomes ground each
  claim
- `GET /board-sessions/{session_id}/dossier`: operator-facing board dossier
  with identity, AOI state, component counts, repair/reuse summary, grounded
  claims, weak claims, and next actions

## Reuse / Splice Path

Repair tries to return a device to its original function. The reuse path asks
what useful functions can be extracted and recombined into a new machine,
fixture, gadget, tool, or resale bundle.

Example request:

```json
{
  "title": "USB fan salvage",
  "goal": "reuse as a fume extractor",
  "available_parts": [
    "5V USB cable",
    "small DC motor and fan blade",
    "on/off switch",
    "wire harness connector",
    "plastic enclosure"
  ]
}
```

The planner returns:

- reusable blocks and likely capabilities
- candidate builds
- safe entry points and splice points
- required voltage/current/continuity measurements
- adapter circuits such as fused MOSFET switches or protected power breakouts
- wiring and mechanical steps
- stop conditions
- fields needed to prove recovered value

Use `/salvage/splice-case` or the `/reuse` workbench when the item is in
hand. That converts the plan into a board session, review queue items,
measurement gates, and `reuse_cases.jsonl` training/export data.

For a real pile, use `/salvage/portfolio-plan` with `items`. Each item can have
its own title, goal, and available parts. The planner runs item-level safety and
reuse planning first, then aggregates reusable blocks into a ranked build
portfolio.

The frontend workbench is:

```text
/reuse
```

## Production AOI Certainty

The production AOI path is intentionally stricter than normal identification.
It does not treat a clear photo or a YOLO hit as enough for release. The scan
result now includes `production_aoi`, a release gate with:

- `disposition`: `release`, `release_with_sampling`, `operator_review`,
  `hold_for_capture`, `hold_for_reference`, `hold_for_calibration`, or `rework`
- `release_authorized`: true only when every production gate passes
- `certainty_score` and `certainty_level`
- per-gate status for capture quality, detector domain, component reference,
  golden visual reference, topology reference, defect severity, evidence
  ledger, and calibration traceability
- blockers, critical findings, required evidence, operator checklist, and audit
  packet fields

The gate expects production evidence:

```text
file                current board image
golden_file         known-good board image from the same fixture
reference_counts    JSON component-count/BOM reference
reference_topology  KiCad/netlist/topology JSON or text
aoi_profile         JSON with fixture_id, calibration_id, station_id, lot_id,
                    board_serial, board_revision, operator_id
```

Example `aoi_profile`:

```json
{
  "line_id": "line-a",
  "station_id": "aoi-1",
  "fixture_id": "fixture-2026-05",
  "calibration_id": "cal-2026-05-07",
  "operator_id": "operator-1",
  "lot_id": "lot-42",
  "board_serial": "pcb-0001",
  "board_revision": "rev-a"
}
```

Without golden/reference/topology/calibration evidence, the gate holds instead
of overclaiming. Failed golden, component, topology, or high-severity defect
gates produce `rework`, not release.

The `/scan` UI exposes these production gate inputs, renders the gate result
beside normal AOI readiness and the evidence ledger, and can save the result as
a board-session review case for calibration.

The review loop now records AOI actual status on outcomes and reports whether
past release decisions caused false accepts or false rejects. Use
`GET /board-sessions/aoi-calibration` before changing AOI thresholds. Any false
accept should freeze automatic release for that line until the case is reviewed.
The review UI also shows a compact evidence graph for the selected session so
operators can see grounded claims, weak claims, and the next evidence action.
Open `/dossier/{session_id}` from Review for the full board dossier.

## Coverage Evaluation

Run the reuse/splice coverage benchmark:

```bash
python3 scripts/evaluate_salvage_splice_coverage.py --output-dir eval/salvage_splice_coverage
```

The built-in benchmark covers low-voltage fans, motors, printer/scanner
mechanisms, router/network parts, audio boards, LED controllers, battery-power
gadgets, input devices, camera/sensor parts, mixed laptop/phone parts, and
high-risk appliances/battery packs. Outputs:

- `eval/salvage_splice_coverage/salvage_splice_coverage.json`
- `eval/salvage_splice_coverage/cases.json`
- `eval/salvage_splice_coverage/README.md`

## Decision Model

The workflow ranks:

- build-from-salvage opportunities
- known recipe matches with missing parts and ROI estimates
- recovered part stocking/resale
- e-commerce arbitrage after shipping, labor, fee, and failure-rate adjustment

Every build package includes validation gates. Salvaged electronics remain
untrusted until power, continuity, connector labels, and thermal behavior are
verified.
