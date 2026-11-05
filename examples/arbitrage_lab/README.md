# Hardware Splicer — legal salvage and functional-product economics

**Agent handoff:** [Optiplex Claude — exact current mission and evidence/acceptance gates](../../docs/SALVAGE_TO_PRODUCT_CLAUDE_HANDOFF_2026-11-05.md).
Check out **draft PR #286** before assuming the following modules exist in `main`.


## Current lead: dumpster-diving economics without unauthorized collection

[**Salvage-to-product owner-transfer and commercial-provenance pilot**](salvage_lot/README.md), with a [**real Zhongli recycler and five-PC batch sourcing screen**](salvage_lot/channel_20261105/README.md) is now the controlling next research milestone. Real public PTT free-donation and damaged-lot leads were checked against **PTT's explicit no-resale rules**, actual local used component prices and the existing Circuit-AI salvage planner. **No legally transferred commercial stock or verified working hardware exists yet.** The modeled functional endpoints are a tested desktop, individually validated parts or a NAS; none has been produced or sold. The intake rejects phantom components, unowned rubbish and unconsented donation resale.


## Primary next product: industrial barcode printer refurbishment

The new [**Zebra ZT230 industrial-printer rehabilitation case**](industrial_printer/README.md) extends the real functional-product arbitrage program from mini-PCs into **industrial electromechanics, firmware communications, sensors, thermal printing and independently scannable output**. A real for-parts Taiwan listing was screened, with a cheap but **missing-head** TSC printer as an explicit trap. Both remain **NO PURCHASE / NO PRINT / NO SALE**. We generated only an **offline future ZPL acceptance fixture**, not a real printer test.

## Prior product: broken mini-PC → genuinely refurbished or upgraded computer

The [**NUC11PAH no-power real Taiwan listing case**](refurb_nuc11/README.md) supersedes the bracket as the **main HS engineering-profit case**. It uses real seller fault claims, Intel/ASUS technical specifications, live local RAM/SSD/PSU listing benchmarks, the **existing Circuit-AI HardwarePlanOrchestrator's repair-authority gate**, and independently reproducible downside/upside trading economics.

**NO BUY** at the observed NT$1,470 broken-unit asking price until exact CPU/board condition and recovery probabilities are supported. No physical machine was purchased, repaired, booted or sold.

## Archived negative-control: Indonesia 3D-printed bracket

The following old router-bracket study remains to test how the arbitrage model can *reject* low-margin commodity fabrication. It is **NOT** the primary Hardware Splicer product strategy. Actual functional systems, electronics repair/verification and refurbishment are the priority.

This is **one actual HS-native CAD product and an auditable margin screen**, not a storefront, unverified profitability claim, physical test, a proposed purchase, or an outsourced rendering exercise.

## Decision

**Do NOT launch any of the eight off-the-shelf 3D-printed product candidates at benchmark competitor asking prices on the currently modeled one-off outsourced-print economics.** All fail the modeled downside case, and none reaches a 20% contribution-margin gate at the chosen conservative costs. More importantly, the products have not been manufactured, test-fitted or sold by HS.

An original **two-bracket indoor router support** design for the Starlink Router 3 *size class* was authored by the native Mecha-Splicer project spec/geometry engine. The official dimensional reference is a 43.4 × 298.6 × 120.4 mm router. This is not Starlink/OEM CAD and is not asserted to fit. [Official reference](https://starlink.com/gn/specifications).

## Direct original product execution

From repository root, with Python deps for Mecha-Splicer and OpenSCAD 2021 or newer:

```bash
PYTHONPATH=apps/mecha-splicer/src python3 examples/arbitrage_lab/produce_pilot.py --openscad /usr/bin/openscad
```

On the authorized Optiplex (2026-11-05), the native `mecha_splicer.bundle.generate_bundle` generated `indoor_router_mount.scad`, the correct quantity-two BOM and a **warning** about physical load, fit, anchors and heat. Upstream official OpenSCAD 2021.01 then rendered its native geometry to a genuine STL. The independent binary STL analyzer checked triangle count/bytes and every undirected edge's incidence.

Output: `outputs/native_router3/` with STLs, editable SCAD, geometry proof and BOM; `outputs/market_screen.csv` and JSON with scenario calculations; `outputs/HS_INDOOR_ROUTER3_MARKET_PILOT.zip`. The ZIP is *not a fabrication order, vendor quote or certified design*. Frozen Optiplex execution evidence is separately checked in at [`evidence/HS_INDOOR_ROUTER3_MARKET_PILOT.zip`](evidence/HS_INDOOR_ROUTER3_MARKET_PILOT.zip), plus mesh audit and ranked CSV; the executable regenerates those from first-party HS code.

Measured **CAD geometry only**: 42 × 53.4 × 65 mm *per bracket*, 564 mesh triangles, zero non-2-manifold edges, 24.13955 cm³ solid volume per bracket; PETG 1.27 g/cm³ density assumption → **30.66 g each / 61.31 g per pair**. Sliced weight including supports/waste and real printed mass are unknown. Machine print orientation, clearances and nominal M4 wall anchors have not been verified.

## Commercial sources versus hypotheses

See `market_snapshot_20261105.json`. Prices and some seller-reported *cumulative* sold quantities are citations to public Shopee/Blibli listings; they are **not verified transactions, demand growth, qualified sales leads or guaranteed achievable prices**. Candidate print weights for products other than the generated router design are **arbitrary screening assumptions** pending SKU-specific CAD/slicing. No third-party model is copied; the price comparisons are market data only.

**Competition extends beyond marketplace listings:** third-party printer models for Gen3 router holders already exist, such as [Cults3D](https://cults3d.com/en/3d-model/home/soporte-pared-router-y-fuente-starlink-gen3), and [SpeakCAD](https://speakcad.com/library/starlink-gen-3-router-wall-mount-bracket) offers prompt-to-CAD output for the same SKU. CAD generation by itself is not scarce. The latter listing even describes a device envelope inconsistent with the official published dimensions, underscoring the need for measured fit. We did not import or relicense their CAD.


- **Observed benchmark**: Starlink Router 3 compatible indoor wall bracket Rp175,700 (alternate observed seller price Rp156,415–185,700); seller displayed ~182–185 sold *cumulatively*.
- **Supplier**: [3D Print Jakarta PETG tariff](https://shop.3dprintjakarta.com/pricing) is **Rp1,000/g of sliced weight with 10g minimum**; shipping, special finishing and design repairs extra. Our calculated geometric solid density is merely a screen proxy, **not a supplier quote**.
- **Seller fees**: conservative model assumes 20% all-in marketplace deduction plus Rp1,250 processing. Confirm actual category/optional programs per Shopee's [official Terms](https://help.shopee.co.id/portal/4/article/71187-Syarat-Layanan?previousPage=other+articles) and [2026 take-rate tracker](https://cube.asia/shopee-take-rate-tracker/). Actual seller fees and revenue taxes could differ.
- **Other per-sale allowances**: Rp5,000 packaging, Rp12,000 picking/checking labor, Rp7,000 acquisition, Rp10,000 returns/warranty, Rp5,000 screws/anchors, Rp15,000 amortized design cost. These are proposed assumptions **not cost quotes**.

## Calculation

`contribution = listed_price - printed_mass_cost - 20% marketplace_fee - Rp1,250 process - Rp54,000 other allowances`.

Contribution is **before tax, seller-funded delivery, overhead, unrecovered setup costs and product-liability expenses**, so it is not net profit. Market prices may drop due to competition; customers may not buy a new listing.

| Candidate | Listing Rp | Model weight g | Base contribution Rp | Downside Rp | Decision |
|---|---:|---:|---:|---:|---|
| Raspberry Pi + HDD enclosure | 225,000 | 85 assumed | +39,750 | -36,988 | No release; heat/fit/sales unknown |
| HDD docking rack | 350,000 | 200 assumed | +24,750 | -116,175 | No release; high material cost |
| HS original router wall bracket pair | 175,700 | **61.314 CAD-derived** | **+23,995** | **-36,095** | No release; printing/physical proof missing |
| Starlink Mini wall bracket | 180,000 | 70 assumed | +18,750 | -45,440 | No release; outdoor safety risk |
| Starlink Gen3 pipe adapter | 119,000 | 55 assumed | -15,050 | -64,364 | Reject; outdoor safety risk |
| ESP32-CAM case | 29,000 | 18 assumed | -50,050 | -71,470 | Reject as individual marketplace SKU |
| Intel NUC VESA bracket | 35,000 | 25 assumed | -52,250 | -77,342 | Reject |
| Generic ESP32 DIN-rail clip | 8,990 | 10 assumed | -58,058 | -73,366 | Reject; bundle only if ever pursued |

**Downside assumptions:** sale price -15%; printed mass +40%; all-in fee 23%; additional Rp10,000 warranty reserve. These are plausible *stress parameters*, not empirical probability estimates.

For the router pair, **25% contribution margin requires ~Rp211,937 selling price** at the CAD-mass print assumption and other costs. That's higher than our observed benchmark, and before the missing taxes/delivery/overhead.

## Competition for CAD engineering services itself

Public providers already advertise [simple-to-complex 3D design at Rp75,000–500,000](https://execute3d.com/), [custom engineering CAD at Rp100,000/part](https://www.projects.co.id/public/browse_services/view/c62711/jasa-menggambar-teknik-mesin-3d-dan-2d) and [Rp150,000+ modeling with revisions](https://layerhaus.id/id/jasa-cetak-3d-jakarta). These are sellers' **asking prices**, not earnings or verified demand. Another service offers [reverse-engineered replacement parts and factory jigs](https://www.hir3dprint.com/). HS cannot monetize *CAD generation alone* on the assumption that nobody offers it.

## More profitable experiments to validate, NOT yet evidenced

1. **B2B problem-first custom repair/fixture work.** Sell a confirmed diagnosis + design + printed solution for a local shop's device-specific problem, ideally an order commitment first. Must prove willingness to pay **for engineering service**, not rely on cheap generic plastic margins.
2. **Local design licensing/partner production.** Let a local print shop produce; HS sells fit-validated parametric designs, documentation, quality control or volume and compatibility coordination. Avoid shipping printed plastic from Taiwan to Indonesia.
3. **Small-series bundling.** Combine several small installation adapters/printed parts per customer order to amortize Rp1,250 processing, design and picking time; pricing and demand must be confirmed.
4. **Repair/reuse products.** Source broken low-voltage equipment, restore, document before/after electrical or functional checks, and sell a complete working product. Requires actual hardware, safety gates and real procurement prices before it can be a trading strategy.

## Required next evidence

Ask local Indonesian fabricator for a **real sliced-mass/printed quote** using the included STL, and obtain a source device (or independent physical caliper measurements), then prototype/fit-test/load-test. Obtain 5–10 credible buyer conversations or paid test orders (no fake listings or fabricated demand) before stocking. Re-run at actual cost/ASP and reject failures. There is **no automatic manufacturing or sales authority** in this benchmark.

No order, payment, printing, device connection, sale, manufacturing certification or claimed realized margin occurred.
