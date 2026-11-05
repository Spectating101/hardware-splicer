# HS Functional Product Arbitrage Pilot 2: Industrial Label Printer

**2026-11-05 / Taiwan. Status: **research-only, no physical printer, no purchase, no customer, no print, no sale**.**

This tests a hardware product with **measurable functional output** (printed and scannable barcodes), not CAD-only plastic. Product pathway: purchase defective commercial Zebra ZT230 → diagnose electronics, mechanical feed, thermal head, media sensors, firmware/driver and connectivity → clean/calibrate or replace proven failed low-voltage parts → physically verify labels and scanner results → resell or offer B2B setup.

## Observed opportunities

- [Zebra ZT230, Ruten](https://www.ruten.com.tw/item/22529245521997/) **NT$1,200** single-unit variant; NT$1,800 may be two-unit bundle. Seller claims power-on based on pictured condition but *not actual printing*. Sold as defective/untested, no returns. Verify exact variant, actual printhead (authentic, 203 or 300 dpi), damaged rollers and stock prior to any offer. Local pickup/test offered.
- [Working-claimed ZT230, Ruten search](https://www.ruten.com.tw/search/zebra%2Bzt230/) **NT$7,900–8,000**. This is only an **asking-price range**, not achieved resale, and listings have different DPI, options and seller service.
- [Zebra original support](https://www.zebra.com/us/en/support-downloads/printers/industrial/zt230.html): ZT230 production discontinued **June 27, 2022**; **APAC service discontinued January 31, 2026**. Parts availability/repair guarantees are commercial risks.
- [ZT230 printheads](https://www.ruten.com.tw/search/zebra%E6%96%91%E9%A6%AC/?cateid=001100160019) listed around NT$7,000+ with highly variable listings, compatible heads and DPI. [Zebra authentic-head warning](https://support.zebra.com/article/ZT-Printer-PH-NOT-AUTHENTICATED-Error) explicitly notes counterfeit/incompatible heads trigger **PH NOT AUTHENTICATED** errors. Budget head replacement as a failure scenario, do not invent a cheap interchangeable part.
- **Negative control:** a [TSC TTP-245C](https://tw.carousell.com/p/%E5%8E%9F%E8%A3%9Dtsc-ttp-245c%E2%AD%90%EF%B8%8Fttp244ce%E6%A2%9D%E7%A2%BC%E6%A8%99%E7%B1%A4%E6%A9%9F-%E5%8F%AF%E9%80%9A%E9%9B%BB%E6%9C%AA%E5%AF%A6%E6%B8%AC%E5%82%99%E5%93%81-%E5%A0%B1%E5%B8%B3-%E9%9B%B6%E4%BB%B6%E6%A9%9F%E2%AD%90%EF%B8%8F%E4%BA%8C%E6%89%8B8%E6%96%B0%E9%96%8B%E6%94%B6%E6%93%9A-1468976721/) NT$495 expressly **missing printhead and external adapter**. Related same-seller offers show NT$435. A complete TTP-245C *seller-claimed* working listing asks NT$2,958. The missing head is NOT a confirmed affordable component. A TTP-245/247 head price of NT$2,988 is **NOT** evidence of 245C compatibility. Even with head cost = ZERO, our model predicts a **-NT$759** result after conservative cost allowances. **Reject TSC from acquisition.**

## Modeled Zebra unit economics (not profit achieved)

Using target NT$1,200 + assumed NT$300 inbound shipping, successful-repair consumables NT$250, cleaning NT$150, bench/validation labor NT$700, outgoing logistics/packing NT$450, warranty reserve NT$450, fee = 15% of sale, and failed-lot loss including NT$450 diagnosis, NT$150 storage/disposal, zero salvage:

| Hypothetical resale | Success without head replacement | Failed attempt | Expected at assumed 50% usable | Expected at assumed 65% usable |
|---|---:|---:|---:|---:|
| NT$4,500 | +NT$325 | -NT$2,100 | -NT$888 | -NT$524 |
| NT$6,500 | +NT$2,025 | -NT$2,100 | -NT$38 | +NT$581 |
| NT$7,900 | +NT$3,215 | -NT$2,100 | +NT$558 | +NT$1,355 |
| NT$8,000 | +NT$3,300 | -NT$2,100 | +NT$600 | +NT$1,410 |

The 25/50/65/80% probabilities are **not measured recovery rates**. Observed working asking prices are **not realized resale**. Model omits sales tax, overhead, extraordinary freight, higher repair complexity and selling delay. **Replacing a printhead at a NT$7,000 scenario cost loses money at every tested price even with 100% technical success.**

At **NT$6,500** realized resale (not observed) and **65%** recovery *hypothesis*, acquisition NT$1,200 achieves a modeled expected gain NT$581. Maximum bid to retain target NT$500 expected gain is **NT$1,281**. At **50%** hypothesis the max bid falls to **NT$662**. **No bid is authorized because the printhead test evidence and recovery probability are missing.**

## Existing HS technology, not a fictional repair

```bash
python3 examples/arbitrage_lab/industrial_printer/printer_pilot.py
PYTHONPATH=apps/mecha-splicer:apps/mecha-splicer/src pytest -q examples/arbitrage_lab/industrial_printer/tests/
```

The **actual** Circuit-AI `HardwarePlanOrchestrator` is invoked with this printer's goal and no LLM. Its generic repair planner **does not know this exact board**. We keep only its authority boundary and explicitly discard generic circuit/BOM hallucinations. The printer-specific diagnosis derives from the [real Zebra model support](https://www.zebra.com/us/en/support-downloads/printers/industrial/zt230.html) and [ZT200 sensor calibration guidance](https://support.zebra.com/article/ZT200-Series-Printers--Calibrating-the-Printer-and-correcting-Media-Errors?language=fr).

The engine generates *offline* `ZT230_BENCH_QC_OFFLINE.zpl`: fixed synthetic Code128 value `HSZT230QC001`, patterns for missing dots and an operator note. **The file was not sent to a device.** This is a pending acceptance fixture, not evidence of printing. The real acceptance requires (1) seller's actual nameplate/DPI and photos, (2) verified genuine installed printhead, (3) actual LCD/state, (4) manufacturer printhead self-test to expose dropped pixels, (5) roller and sensor feed/calibration, (6) real printed label scanned to matching value, (7) connectivity and sustained output, (8) customer-safe service/return disclosure.

### Engineering risks

Zebra has already [documented](https://support.zebra.com/article/000032429) simple platen-roller latch problems that prevent label feeding; a failed media path is not necessarily a bad PCB. But the same family can have expensive heads; visual powered-on proof does not prove that it can print. This printer may include an internal mains PSU; **do not open or probe live mains circuits** or send firmware/driver changes without an authorized bench and backup. We have **no** attached engineering interface on the remote Optiplex for this exact printer.

**Current decision: HOLD, NO PURCHASE.** Next real progress is acquiring **seller-provided printhead self-test results and correct variant** or using an authorized local repair bench. No assumed result can replace physical printer output.
