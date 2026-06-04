# Product Value Probe (2026-02-28)

## What was tested (technical)

All four candidates were generated with `--high-fidelity --include-pricing` and passed without simulation blockers:

- `meshtastic_rugged_case`
- `pi_outdoor_enclosure`
- `pan_tilt_camera_head`
- `linear_axis_module`

See: `PRODUCT_PROBE_SUMMARY.json` and `runs/*/mecha_splicer.bundle.json`.

## Market comps (live pages)

### 1) Meshtastic accessories / cases
- Tindie standalone Meshtastic accessory listing: **$5.99**
  - https://www.tindie.com/products/nootropicdesign/meshtastic-rak19007-base-board-with-pca9555-i2c-io/
- Tindie complete node listing: **$99.99**
  - https://www.tindie.com/products/roofless/meshtastic-all-in-one-esp32-lora--gps-gnss-usbc/
- Etsy Meshtastic market search (many case SKUs, mostly in the **$20–$70+** range)
  - https://www.etsy.com/market/meshtastic

### 2) Raspberry Pi enclosure
- eBay Raspberry Pi 4 model B case listing: **about $4.99** (very high-volume SKU)
  - https://www.ebay.com/itm/174172323671

### 3) Pan-tilt camera head
- eBay pan-tilt servo camera bracket listing: **about $13.99**
  - https://www.ebay.com/itm/276881264763

### 4) Linear-axis / rail module
- eBay MGN12 + 300mm rail + block listing: **about $7.48–$8.26**
  - https://www.ebay.com/itm/393022545843

## Value interpretation

- Commodity hardware-only SKUs are price-compressed (especially generic Pi cases and rail kits).
- Best monetization path is **"verified design + evidence"** rather than only printed part sales.
- Good package strategy:
  - digital files + parameterized variants + validation reports,
  - optional fabrication add-on,
  - higher-ticket custom adaptation.

## Important note on local COGS output

Current `cogs_usd` in this probe uses internal catalog pack assumptions and can overstate per-unit cost for fasteners/small hardware. Use supplier overrides before final pricing.
