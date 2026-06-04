# Mint pipeline (signals → bundles)

`scripts/mecha_splicer_mint.py`:

1) Pulls RSS items from `docs/NEWS_SOURCES.json`
2) Categorizes them via `src/mecha_splicer/templates/categories.json`
3) Chooses the top categories
4) Emits bundles under `data/opportunities/mecha_splicer_mint/<timestamp>/<category>/`

This is a demand-signal prototype, similar to the Circuit‑Splicer approach.

## Options (Circuit‑Splicer parity)

- `--force-category <name>`: mint one category only
- `--list-templates`: print available templates (name + category) and exit
- `--force-template <name>`: mint a specific template (useful when a category has multiple templates, e.g. robotics)
- `--include-pricing`: emit `BUY_LIST.csv`, `BUY_LIST.locked.csv`, `SKU_OVERRIDES.json`, `PROCUREMENT_LOCK_REPORT.md`
- `--sku-overrides <path>`: provide your own overrides file (recommended for Taiwan Shopee links/prices)
- `--use-3d-splicer`: for electronics-anchored enclosures, call sibling `3d-splicer` for CadQuery script/STL
- `--render-openscad-stl`: attempt to render `.scad` outputs to `.stl` (local `openscad` or Docker)
