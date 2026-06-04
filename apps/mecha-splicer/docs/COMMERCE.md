# Commerce + Costing (v1)

Mecha‑Splicer outputs mechanical artifacts; **commerce is optional** but strongly recommended
if you want to “mint” products that are actually profitable.

## Two sellable shapes

1) **Digital design pack (recommended)**
- Deliverable: OpenSCAD/CadQuery script + variants + print settings + assembly/test checklist
- Costs per sale: platform+payment fees + your support time (no physical COGS)

2) **Physical kit (harder)**
- Deliverable: shipped hardware (fasteners, inserts, maybe printed parts)
- Costs per sale: COGS + labor + fees + chargebacks + support + shipping/returns

## What Mecha‑Splicer does today

- Adds a conservative **digital pack** estimate to the bundle output: `commerce.digital_pack`
  - Implemented in `src/mecha_splicer/runner.py`
  - Based on `src/mecha_splicer/engines/economics.py`

- Adds a **procurement lock** workflow (Circuit‑Splicer style):
  - `BUY_LIST.csv` (unlocked)
  - `SKU_OVERRIDES.json` (editable mapping)
  - `BUY_LIST.locked.csv` + `bom.locked.json`
  - `PROCUREMENT_LOCK_REPORT.md`

- Reports COGS in USD and a chosen reporting currency (default: TWD) using cached FX:
  - FX engine: `src/mecha_splicer/engines/fx.py`
  - Cache: `data/fx_cache.json`

- Includes a starter mechanical catalog (placeholder pricing):
  - `data/catalog/mechanical_catalog.jsonl`

## What you should do (Taiwan)

Replace the placeholder catalog items with your actual sourcing (e.g., Taiwan Shopee):
- Keep the same `sku`, update `price_usd` and add your link/notes.

Once you have real costs, we can:
- generate a real kit COGS estimate,
- add “variant pricing” (e.g., M2 vs M3, insert vs self-tapping),
- produce a procurement CSV suitable for ordering.
