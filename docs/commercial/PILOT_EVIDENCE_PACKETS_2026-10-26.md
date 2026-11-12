# HS commercial pilot packet — 2026-10-26

Status: **SOURCE VALIDATION ONLY; no purchase, working device, measured profit, verified quote, buyer order or production authorization.**

This operationalizes the 30-concept commercial portfolio into eight **specific** preliminary evidence packets. The code used to generate them is `src/hardware_splicer/commercial_validation_packets.py`. Run `scripts/replay_hs_commercial_portfolio.py` to regenerate the machine-readable `commercial_validation_packets.json`.

## First eight evidence investigations

| Concept | Local market | First technical blocker | Quotes/materials required | Product/use proof |
| --- | --- | --- | --- | --- |
| Faulty TSC TTP-244 Plus | Taiwan, TWD | Printhead, platen, feed and USB; variant condition | Correct printhead revision, platen/motor, repair time, shipping | Same-model settled sale or justified internally useful label throughput |
| ProofPod | Original product (native design economics) | Approved voltage/current, SPI/I2C functional acceptance, protocol identity | PCB assembly MOQ1/10, enclosure, firmware and QA | Paid specialist workflow or metered own use |
| LS2208 barcode scanner | Taiwan, TWD | Cut cable/pinout, decoder/optics | Cable/connector, safe 5V test fixture, recovery labor | Scanning utility or same-model sold comparables |
| QNAP TS-219P II board | Taiwan, TWD | Exact board revision and absent PSU | Rated power/test setup, storage/interface costs | Energy-adjusted internal compute/storage or qualified parts buyer |
| TW BenchGateway | Taiwan, TWD | Thin-client identity; seller HP T620/J1900 discrepancy | Matching donor lot, isolated I/O board, assembly/QA, landed cost | Working production gateway that beats local alternatives |
| TW Refurbished Lab Controller | Taiwan, TWD | Exact Advantech ARK variation and rated supply | Storage/PSU/rework, tests, warranties, shipping | Controlled low-risk lab use or specific approved buyer |
| CN TouchLab | China, CNY | Exact NEC N8910 touch POS model, panel/driver yield | 1/10 unit donor lot, conversion, local freight, rework | Practical test/monitoring workflow and customer evidence |
| CN ThinEdge | China, CNY | Exact HP/Dell donor and uncertain local commodity competition | CNY donor/sidecar/test prices and commodity comparables | Actual value-add beyond a ¥50–235-class adapter |

No CNY figures are converted into Taiwan dollar margin claims. Indonesia's IDR supply chain is not represented in this frozen initial sample. The business can also consider manufacturing from new components and own-operated assets; the above wave is *not* a claim that e-waste alone defines HS.

## Taiwan TSC: price-risk stress, not proof of a bad business

The original PR #147 source model estimated NT$339 expected contribution/acquisition under:

- Approximate NT$500 historical faulty-device advertised ask;
- 70% repair success *assumption*, NT$2,800 hypothetical selling price;
- NT$300 successful repair-parts allowance, and state-dependent labor;
- NT$300 minimum target contribution.

Thus it had only **NT$39** above the target margin.

Taiwan Ruten aggregation advertises TSC TTP-244 PRO/PLUS head replacements at **NT$1,450–1,800**, with selectable head types: <https://www.ruten.com.tw/find/?q=tsc+%E7%B6%AD%E4%BF%AE>.

If every otherwise-successful repair *needs* a full replacement head and its price **replaces** the original NT$300 parts allowance, holding all other old assumptions constant:

`model_net = 339 - 0.70 × max(0, replacement_head_price - 300)`

- NT$1,450 head → **−NT$466** expected contribution per acquired donor.
- NT$1,800 head → **−NT$711**.
- Maximum parts spend for maintaining NT$300 expected contribution under those assumptions: **NT$355.71**.

This is an **adverse-condition scenario**, not an unconditional forecast or a likelihood of printhead failure. The listings are not confirmed exact-variant parts quotes. Minimum rational step: verify head condition and exact revision before any donor acquisition. Reject if the source/model/condition cannot be verified.

The TTP-244 Plus [service manual](https://www.manualslib.com/manual/785828/Tsc-Ttp-244-Plus.html) contains technical self-test and repair/printhead sections; mechanical and electrical work still requires proper tools, power safety and qualified handling.

## Taiwan thin client: price is irrelevant until device identity agrees

One Ruten listing has configurable options labeled **HP T620 J1900**, alongside a broad NT$446–2,178 range that **includes accessories and different options**: <https://www.ruten.com.tw/item/22641820631780/>.

The documented HP t620 processor family is **AMD GX-series**, rather than Intel J1900, in the published HP t620 specs reproduced at <https://manualzz.com/doc/2470816/hp-t620-specification>.

This is a discrepancy between seller text and product-family specification, **not evidence of seller fraud**. Device identity, exact CPU/board label, included PSU, item-option price and BIOS reporting must be checked before treating that listing as a valid BenchGateway donor or comparing it against working alternatives.

`commercial_identity_audit.reconcile_identity_claims` produces **HOLD_IDENTITY_CONFLICT** for this example. It never authenticates the listing or authorizes buying.

## Mandatory information for a real product transaction

A potential asset record must include current offered unit, exact model/variant, seller identity and date, condition/serial/photo, safe test requirements, actual parts/assembly/labor, freight and taxes, failure recovery and expected yield, legal ownership/compliance, end-user demand or measurable productive use, then confirmed settlement and warranty costs.

A seller ask is not a fulfilled sale. An arbitrary target MSRP is not an accepted buyer order. A passed software test is not a physical manufacturing test. A supplier price without the exact option and quantity cannot enter the bill of materials as a definitive landed cost.

## Execute and review

```bash
PYTHONPATH=src python -m pytest -q tests/test_commercial_value_routing.py
PYTHONPATH=src python scripts/replay_hs_commercial_portfolio.py --output-dir artifacts/commercial
```

Expected CI artifacts: `commercial_cohort_replay.json`, `commercial_cohort_replay.md`, and `commercial_validation_packets.json`. All remain **research documents**, not authority to procure or sell.

## Current stop conditions

- No matching product variant or compatible electrical source → **hold**.
- Key component fault or replacement part erases positive economics → **reject or price a different use**.
- No native-market sale comparables, buyer intent or useful operating output → **hypothesis only**.
- Unverified seller inventory, environmental status, batteries/mains hazards, export restrictions → **no acquisition**.
- Passing code tests with no physical pilot or cash outcomes → **software milestone only**.
