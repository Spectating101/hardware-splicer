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

- `POST /salvage/pipeline`: images/listings to workflow report and build package
- `GET /salvage/workflow`: current persistent inventory and decision report
- `GET /salvage/build-package`: current build package only
- `POST /salvage/analysis`: ingest an existing analysis result
- `POST /salvage/listing`: ingest a listing
- `POST /salvage/assets/{asset_id}/test`: update test status and condition

## Decision Model

The workflow ranks:

- build-from-salvage opportunities
- known recipe matches with missing parts and ROI estimates
- recovered part stocking/resale
- e-commerce arbitrage after shipping, labor, fee, and failure-rate adjustment

Every build package includes validation gates. Salvaged electronics remain
untrusted until power, continuity, connector labels, and thermal behavior are
verified.
