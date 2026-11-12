# HS hardware-commercial portfolio — expanded execution checkpoint

**As of 2026-10-25, development snapshot. No purchase, shipment, manufacturing, buyer order, physical acceptance or earned margin claimed.**

This work responds to the failure of the fixture-first and single-BenchHMI approaches. Hardware Splicer is a *general engineering-to-economic-value system*: e-waste/salvage is a strong information-asymmetry wedge, but the business may also acquire surplus equipment, manufacture new products with OEM/ODM suppliers, operate productive assets, or sell improved open-hardware systems under applicable licenses. A generator is an **example** of an operating asset, not a predetermined product.

## Executed source coverage

The deterministic CLI, `scripts/replay_hs_commercial_portfolio.py`, consumes:

| Input | Records | What the evidence means |
| --- | ---: | --- |
| Taiwan secondhand donor listings from PR #148 | 17, 10 device families | Ruten *advertised asking prices*, Oct 19; no verified condition, yield or sales |
| Taiwan salvage acquisition economics from PR #147 | 5 | Illustrative risk-adjusted per-acquisition screens and nine-point sensitivities, not receipts |
| Product Factory PF-001, PF-002, PF-003 from open PR #109/#110/#111 | 3 | Engineering/price hypotheses, no physically validated manufactured product |
| Taiwan/China Product Factory expansion from open PR #109 | 6 | Three TWD and three CNY product opportunities, target selling price and assumed COGS, NOT complete landed contribution |
| **Source records** | **31** | **30 named concepts** after a manually documented BenchHMI alias |

The separately itemized PF-002 case in the CLI is a priced *alternative route for an already counted concept*, **not a 32nd product**.

### Five historical acquisition screens (NT$, per donor)

| Opportunity | Advertised acquisition ask (modeled) | Expected contribution (model) | At-target-profit maximum bid | Review decision |
| --- | ---: | ---: | ---: | --- |
| TSC TTP-244 Plus faulty printer | 500 | **+339** | 539 | **Research only**, verify printhead and matched completed sales |
| Brother QL-800 untested label printer | 500 | **+24.25** | 224.25 | **Below NT$300 target**; model says no at listed ask |
| HP P1505N broken laser printer | 300 | **−476** | −476 | Reject under current assumptions |
| Acer SA241Y damaged LCD | 250 | **−480** | −530 | Reject under current assumptions |
| Old parts-only laptop | 800 | **−667** | −167 | Reject under current assumptions |

The TSC's original reported nine-point test is **positive in six of nine** hypothetical sale-price/yield combinations, not robust evidence from actual repairs. Buying at the modeled NT$500 ask leaves just NT$39 of modeled headroom over its NT$300 profit goal. A printhead replacement can destroy the economics entirely. No acquisition authorized.

The QL-800's +NT$24.25 positive spread does **not** pass the earlier NT$300 target: screening must not call it a winning opportunity.

### Six broader Taiwan/China product hypotheses

| Concept | Operating market and native currency | Target retail assumption | Effective COGS assumption | Key gap |
| --- | --- | --- | --- | --- |
| BenchHMI | Taiwan NT$ | 8,990 | 4,000 | Actual donor yield, full part and labor cost, buyer interest |
| BenchGateway | Taiwan NT$ | 5,990–7,990 | 3,200–4,200 | Exact working thin-client lot, I/O reuse and differentiation |
| Refurbished Lab Controller | Taiwan NT$ | 6,990–9,990 | 3,000–5,000 | Model identity, industrial compatibility, warranties |
| TouchLab | China ¥ | 999–1,299 | 500–650 | Qualified POS lots, touch-panel test yield |
| ThinEdge | China ¥ | 699–899 | 280–380 | Commodity pressure and true customer application |
| M720q Instrument Node | China ¥ | 1,699–2,199 | 850–1,100 | Specialized I/O and meaningful productive workload |

These are September 2026 hypotheses, **not** updated local retail prices, supplier quotations or verified willingness to pay. Several descriptions overlap with PF branches. No RMB-to-NTD conversion is performed.

### Seventeen Taiwan donor opportunities

The Ruten source catalog includes four thermal printers, four robot vacuums, two barcode scanners, and individual dot-matrix-printer, network-board, NAS-chassis, wireless-AP, human-input, laptop and LiDAR-spares listings. The source dates to **October 19, 2026**. Individual offers may no longer exist, and several are incomplete or untested; cheap ask prices are **not a profit signal** without function and yield evidence. The full individual source URLs and asks are printed in the generated cohort report and underlying JSON.

### Broader resource allocation

Do not default to building a tester, selling a salvaged component, operating a generator, or reproducing a cheap Chinese adapter. Candidate-specific financial decisions must compare: buy/resell, repair, harvest, integrate/build, own/operate, replicate and reject/recycle.

- **Taiwan:** native TWD listings and margins, qualified technical tests and lawful procurement.
- **Mainland China:** native CNY supplier/competitor floor; avoid treating cheap commodity modules as a moat.
- **Indonesia:** native IDR sources **not yet covered by this frozen portfolio**. No import economics or resale margins may be inferred without locally verified records.
- **Productive assets:** only credit measured operating output or honestly modeled net cash savings after usage, power, maintenance, rent and depreciation. No free electricity or passive-profit claims.

## Actual engineering improvements in PR #214

1. The purchase/transform/operate commercial route evaluator rejects missing costs, invalid arithmetic and currency mixing.
2. Itemized BOM and outsourced fabrication service must reconcile to the financial model for new/replicated hardware.
3. Repair yields and failure salvage proceeds are included; the specialized PR #147 model remains authoritative for **state-dependent labor** rather than duplicating its arithmetic.
4. Native operating NPV is distinct from one-off resale contribution, and neither grants purchase authority.
5. Perfect-information value is a **theoretical upper bound** on diagnosis spend, not an expected realized return.
6. Source adapters ingest PF-001/002/003, 17 Taiwan donor observations, five already-computed salvage screens and six regional hypotheses while preserving original evidence tiers.
7. Receipt-backed settled commercial outcomes cannot turn preliminary prices or an invoice into earned profits.
8. An execution CLI produces a 31-record JSON dossier and human-readable Markdown with 32 independent evidence tasks (PF-002 also has an evaluated alternative route).

## First commercial validation waves

**Wave A — source quality:** Verify exact model and current seller terms for 3–5 inspectable Taiwan donors; obtain matched completed sale records, not merely asking prices. Reject regulated or unsafe waste handling. No unapproved purchases.

**Wave B — productive/industrial hardware:** Evaluate BenchGateway, Refurbished Lab Controller and a low-risk mechanical/compute project for their own usefulness; obtain real compatible donor prices and user output measures before proposing sale prices.

**Wave C — licensed new/OEM hardware:** Add at least two non-salvage manufacturing routes only after itemized supplier quotations and use/sales economics exist. A BOM alone is not a complete product.

**Wave D — cross-market:** Collect actual CNY and IDR procurement, shipping/customs and selling records in their native currency. Keep markets separate until auditable FX and landed-cost analysis.

**Investment gate:** No speculative inventory, fabrication, export, active waste handling or purchase contracts until the specific asset's ownership, technical safety, probable usable yield, full materials/service cost and either paying demand or measurable operating utility have passed review.

## Validation

Run:

```bash
PYTHONPATH=src python -m pytest -q tests/test_commercial_value_routing.py
PYTHONPATH=src python scripts/replay_hs_commercial_portfolio.py --output-dir artifacts/commercial
```

GitHub Actions workflow `HS Commercial Portfolio Replay` publishes the executed, source-traceable JSON and Markdown files as an artifact. The *previous* version of PR #214 passed core/full GitHub CI; new checks must be read separately before this version can be claimed green.

## Next blockers

1. Real completed transaction prices and observed supply depth remain missing.
2. No physical yield, refurbishment result, operator output or paid customer exists for the sample.
3. Some original PF-002 BOM sums are inconsistent: source TOTAL NT$1,726 versus rows NT$1,936 at one unit, and NT$1,357 versus NT$1,462 at ten-unit tier. A source-preserving regression test now catches both.
4. PR #147/#148 and PF #109/#110/#111 are still separately open; do not merge/rebase them without verifying their branch prerequisites.
5. External e-commerce sources need freshness checks; the current benchmark measures **software integrity and research coverage**, not a profitable hardware enterprise.


## Follow-on: transaction evidence and 30-case validation backlog

PR #214 adds `commercial_market_evidence.py` and `commercial_validation_backlog.py`.

**Market evidence rules.** Records have an exact model and verified variant, date, market and native currency, condition, event type, and a reference. Only a record explicitly marked `verified_settled_sale` with price and settlement reference is admitted to the candidate's *preliminary* sold-comparable median. Even then, independent receipt review remains `false` until someone verifies the underlying proof. A marketplace 'sold' badge, generic listing ask, different model, stale evidence and cross-currency price are excluded. **Do not equate user-submitted settlement metadata with an independently authenticated sale.**

The historical faulty TSC record is included in `examples/commercial_market_evidence_tsc_historical.json`. Its original ask is NT$500, the option/variant is unverified, and it is therefore **not** admissible as a completed-sale comparable. The earlier +NT$339 profit is still only a hypothesis.

**Deduplicated backlog.** `build_validation_backlog` consolidates 31 source records to 30 named concepts, with an evidence status, references, validation task and no purchase authority. The diversified *first evidence wave* is:

| Concept ID | Workstream | Validation target |
| --- | --- | --- |
| tsc-ttp244plus-budget-fault | Historic Taiwan salvage hypothesis | Same-model settled-sale prices; printhead/failure condition |
| proofpod-v0 | Original Product Factory hardware | Native schematic/physical gates and priced BOM; actual use/sales case |
| ls2208 | Low-cost Taiwan donor | Confirm model/condition and recovered scanner-engine value |
| qnap-ts219pii | Taiwan used electronics | Confirm actual board revision/power and technical usefulness |
| TW-PF-EDGE-001 | Taiwan BenchGateway | Qualify thin-client lot, interface BOM, productive use |
| TW-PF-ARK-001 | Taiwan Refurbished Lab Controller | Verify donor variants, real quote and non-safety-critical tasks |
| CN-PF-HMI-001 | Mainland China TouchLab | Validate ¥ sourcing/finished-unit economics without implied Taiwan FX |
| CN-PF-EDGE-001 | Mainland China ThinEdge | Test against ¥-priced commodity substitutes |

This selection intentionally mixes product manufacturing, reuse, donor discovery and mainland Chinese sourcing. **These are market/engineering research targets, not purchase recommendations**, and are not ranked by imaginary profit.

### Fresh Taiwan seller-market signals (Oct 25 review)

The Ruten Taiwan listing aggregation presently displays **faulty TSC TTP-244 Plus asking at NT$500–1,500** and a separate **untested Brother QL-800 at NT$500**; a related TSC TTP244Pro appears at NT$1,960. These are seller offers/aggregated observations, not exact completed resale transactions or verified current inventory. The TTP244Pro must **not** substitute for TTP-244 Plus in price matching.

- TSC seller-market search: https://www.ruten.com.tw/search/%E4%BA%8C%E6%89%8B%E6%A8%99%E7%B1%A4%E6%A9%9F/?sort=ords%2Fdc
- Taiwan untested printer search: https://www.ruten.com.tw/search/%E4%BA%8C%E6%89%8B/?cateid=0011002800010007
- Mainland China HP T620 price observation of ¥60–70 was described in a March **2025** community article, not a verified October 2026 supplier quote; it is **too stale** to substantiate current sourcing. https://post.smzdm.com/p/az7n9ddo/

Nothing in those sources proves a gross or net margin for any repaired product.

### Running the extended replay

```bash
PYTHONPATH=src python -m pytest -q tests/test_commercial_value_routing.py
PYTHONPATH=src python scripts/replay_hs_commercial_portfolio.py --output-dir artifacts/commercial
PYTHONPATH=src python scripts/converge_commercial_sources.py \
    --donor-discovery examples/commercial_tw_donor_discovery_snapshot_2026-10-19.json \
    --purchase-report examples/commercial_tw_salvage_five_screen_snapshot.json \
    --regional-scan examples/commercial_tw_cn_regional_scan_snapshot.json \
    --market-evidence examples/commercial_market_evidence_tsc_historical.json \
    --as-of 2026-10-25
```

The full replay now emits market evidence screens and the 30-entry validation backlog, including an eight-concept evidence-first wave. Do not promote any opportunity to investment approval until procurement, ownership/compliance, test evidence, real selling price or metered usage, and all attributable costs are substantiated.
