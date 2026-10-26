# HS source-backed hardware procurement diligence — 2026-10-26

**Scope:** 21 external observations (17 Taiwan, 4 mainland China), 8 active first-wave concepts, native TWD/CNY; **0 actual purchases, verified completed sales, written supplier quotations, authenticated stock, customer contracts or measured profit**. Seller adverts are not execution authority.

Source snapshot: [commercial_external_market_observations_2026-10-26.json](../../examples/commercial_external_market_observations_2026-10-26.json). Machine grader: `src/hardware_splicer/commercial_external_evidence.py`. To replay: `PYTHONPATH=src python scripts/replay_hs_commercial_portfolio.py --output-dir artifacts/commercial`.

## Market evidence we actually gathered

| Route / source kind | Native currency | Observed advertised price | Scope and warning |
| --- | --- | ---: | --- |
| Taiwan TSC TTP-244 Plus, seller-described functioning with bundled scanner | NT$ | 3,500 | Carousell ad in Taoyuan Pingzhen; **bundle**, not a standalone tested resale comparable and certainly not a settled sale |
| TSC 244 PRO/PLUS dismantled printhead | NT$ | 1,450–1,800 | Daidai used replacement head, different one-port/two-port choices; cannot assume interchangeability |
| Taiwan used LS2208 with USB cable, category offers | NT$ | 540–600 | Several advertisements; another long-standing seller asks 1,500; ask dispersion is not net arbitrage |
| Taiwan QNAP TS-219P II (power response only, untested) | NT$ | 800 | Listing says parts/not checked and no accessories; **not working NAS** |
| Taiwan Advantech ARK-1123 J1900 plus power adapter | NT$ | 2,499 | Ruten seller advertises 50 units, Shopee cross-list about 44 at index capture; **same merchant, not independent supply** |
| Dell Wyse 3040 Taiwan marketplace offers | NT$ | 1,130–1,380 | Different memory, accessory and seller configurations; verify unit and seller country |
| Used HP t620 Taiwanese price aggregator | NT$ | 1,472 | June 2026 cached offer; model/CPU must match OEM AMD family; not currently verified |
| Taiwan Waveshare isolated RS-485/422 FT232RNL at Meiya | NT$ | 588 | Source claims 7 units in stock and 3-month warranty, pending true fulfillment check |
| Taiwan Waveshare isolated USB RS485 at iCShop | NT$ | 390 | The same category but different product. Listed **out of stock**, with 4–10-day preorder description |
| Generic non-isolated USB-RS485 adapter | NT$ | 39 | Cheap competing *simple protocol adapter*, **not** industrial isolated gateway |
| STLINK-V3MINIE, DigiKey Taiwan | NT$ | 859 | Identified genuine STM32 probe at 1 pc price; is a **competitor/reference**, not ProofPod's full BOM |
| STLINK-V3MINIE, Mouser Taiwan | NT$ | 926.36 | Same SKU at another independent distributor, not a second product or complete power/test station |
| Mainland-China Wyse 3040 bare/repairable offer observations | ¥ | 107, 154.09 | Taobao **third-party aggregator**, not confirmed direct order or tested units |
| Mainland-China Wyse 3040 enthusiast article | ¥ | 80–100 | April 2026 commentary on bare and 2/16 models; outdated as a supplier quote |
| Mainland-China NEC N8910 retired POS | ¥ | 200+ | April 2026 commentary only, no identified current offer or fixed comparable spec |

**Important:** The NT$2,499 ARK listing on both Ruten and Shopee is likely the same merchant/device pool. The apparent NT$39 simple USB/RS485 module and NT$588 isolated FT232RNL are not functionally identical. A working TSC unit bundled with a scanner cannot serve as an exact unbundled resale price.

Sources (examples):
- <https://www.ruten.com.tw/item/22539061463944/> — ARK-1123 used seller, NT$2,499.
- <https://www.ruten.com.tw/search/wyse%2B3040/> — Taiwan Wyse 3040 market offers.
- <https://daidai.tw/product/x2024121601/> — used replacement TSC printhead and exact connector warning.
- <https://tw.carousell.com/p/%E8%B3%A3%E4%BA%8C%E6%89%8Btsc-ttp-244-plus%E6%A1%8C%E4%B8%8A%E5%9E%8B%E7%86%B1%E6%84%9F%E5%BC%8F%E7%86%B1%E8%BD%89%E5%BC%8F%E5%85%A9%E7%94%A8%E6%A2%9D%E7%A2%BC%E5%88%97%E5%8D%B0%E6%A9%9F-1465184795/> — seller claims TSC functionality, NT$3,500 with scanner.
- <https://www.ruten.com.tw/item/22636527582255/> — untested QNAP TS-219P II, NT$800.
- <https://www.ruten.com.tw/search/%E4%BA%8C%E6%89%8B/?cateid=001100030004> — used scanner offers, including LS2208.
- <https://www.meiyagroup.com.tw/product/%E5%B7%A5%E6%A5%AD%E7%B4%9A-usb-%E8%BD%89-rs485-422-%E8%BD%89%E6%8F%9B%E6%A8%A1%E7%B5%84-%E9%9A%94%E9%9B%A2%E5%9E%8B/> — quoted online catalog NT$588, not negotiated bulk quotation.
- <https://www.icshop.com.tw/products/368031700377> — NT$390 alternative, marked sold-out.
- <https://www.digikey.tw/en/products/detail/stmicroelectronics/STLINK-V3MINIE/16284301> — genuine debug probe, indexed price.
- <https://tao.hooos.com/search?w=Wyse3040> — third-party Chinese listing aggregator.
- <https://post.smzdm.com/p/a709xd8o/> — NEC retired POS commentary.

## Actual independent technical sources

- Zebra LS2208 official specification: <https://www.zebra.com/us/en/products/spec-sheets/scanners/general-purpose-scanners/ls2208.html>. **1D laser scanner, supported 4.5–5.5V, nominal operating 175mA, available USB/RS232 and other variants**; requires correct cable/interface, safe low-voltage testing and an actual working sample. This confirms utility constraints, **not seller condition**.
- QNAP TS-219P II official hardware: <https://www.qnap.com/en-ph/product/ts-219p%20ii/specs/hardware>. **Marvell 2GHz, 512MB RAM, external 60W adapter, two drive bays**, operation reported 16W with two 500GB drives. Model is old and cannot be treated as high-throughput modern compute or automatically safe internet-facing NAS. No PSU is included in the NT$800 suspect listing.
- HP t620: verify actual AMD-GX OEM family against seller options describing Intel J1900. No model-exact unit identity proof in current sources.
- Advantech ARK-1123: J1900 claim agrees with published model-family specs, but BIOS, port variant and physical condition still require test.

## Quote requests: ready to use, **none sent**

**TW–ARK1123 (seller Ruten / Shopee, same apparent merchant):** 請確認 ARK-1123 的完整型號及版號，CPU/BIOS、RAM/SSD、電源規格與變壓器是否包含，並提供單台/5台/10台的實際可供數量、含稅發票價格、測試項目及實測紀錄、保固或故障退貨條件，以及配送至桃園的運費與交期。可否提供序號貼紙、I/O 埠及開機畫面照片？ **Do not count two cross-listings as two inventory pools.**

**TW–WYSE3040 (Taiwan sellers):** 請提供 Wyse 3040/N10D 的實際 CPU、RAM、8G或16G eMMC、BIOS鎖定情況、外觀照片、原配電源是否包含，以及 1/10/30 台分級報價、可驗收工作單位數、故障率或退貨條款、桃園運費與交期。請分別列出已測試可正常啟動及未測試機種，不要混同。 **Exact configuration matters.**

**TW–TSC head (Daidai):** 請問 TTP-244 Plus 主機板單口與雙口列印頭各自現貨、實際含稅價格、接頭照片及列印測試樣張？此商品為拆機件，是否有保固、退貨與寄送桃園費用？請確認適用的主機板版號。 **Our break-even repair depends heavily on the head.**

**TW–LS2208 (used Taiwan sellers):** 請確認 Symbol/Zebra LS2208 序號/版本、USB線是否隨附，可否提供 Code39/Code128/EAN13 實際掃描結果，以及 1台/5台/10台含稅價格、保固、退貨及桃園運費？ **Cable-less goods cannot be compared with bundled working goods.**

**TW–QNAP (parts listing):** 請提供 TS-219P II 主機/主板版號、電源輸入標示、配件與電源供應器是否附贈，能否示範開機與 SATA/網路埠檢查、存取資料已清除，以及故障退貨或零件品不退的明確條件？ **Absent PSU, no assumed boot.**

**TW–ProofPod + Taiwan electronics distributors:** Only after engineering approves a revision-bound BOM, request exact manufacturer part numbers, quantity tiers 1/10/50, RoHS/part authenticity, delivery, tax, import and PCBA/firmware/test/packaging. A STLINK-V3MINIE is a competitor comparison, **not** a ProofPod BOM line by default.

**CN–TOUCHLAB:** 请确认 NEC N8910-011BZ0B 的完整型号、J1900 CPU、触控面板/显示器状态、主板/接口/电源，以及 1/10/30 台按实际可用情况的人民币含税报价、国内运费、交货期、售后与故障退货规则。请提供通电与触控测试视频。 **Generic '¥200+' posts aren't quotations.**

**CN–THINEDGE:** 请确认 Wyse 3040 或 HP t620 的精确型号、CPU、内存/板载存储、BIOS 锁、5V电源是否附带、实际可出货数量，以及 1/10/30 台已测试正常机器（不混入可维修/配件品）的人民币含税单价、交期、运费和故障退货条件。 **China pricing must stay CNY and not be disguised as guaranteed cross-border savings.**

## Preliminary selection and stop decisions

1. **Best source-depth inquiry:** ARK-1123 and Wyse 3040. We now have identifiable used-device asks and at least some relevant component catalog prices. Need seller-confirmed units, exact I/O and productive task before choosing whether to own and operate or sell.
2. **TSC: conditional hold:** working bundle NT$3,500 versus hypothetical repair at a lower donor ask is not an arbitrage calculation. A used replacement head NT$1,450–1,800 could wipe out repair return. No device purchase before printhead inspection and verified matched sales.
3. **LS2208: commodity/operational-utility first:** offers already around NT$540–600; a historically low untested donor does not give enough information to assume resale profit. More attractive only if it demonstrably saves scanning/labeling effort in our own production.
4. **QNAP: lower initial priority:** parts-only NT$800, no demonstrated boot or PSU, aging limited compute. May be useful for board recovery, but not equivalent to a ready-to-run productive NAS.
5. **ProofPod: independent new-product track:** do not compare its intended functionality with the genuine STLINK price directly or count a competitor's catalog price as our margin.
6. **China TouchLab/ThinEdge:** qualify direct seller and SKU. Aggregator figures and enthusiast articles are too weak to underwrite a purchase.

## End-to-end evidence acceptance

For a **verified acquisition**: exact model and condition, latest seller offer, definitive quantity, tested sample/return terms, itemized all-in delivered cost and legal ownership. For a **verified product**: documented design, authorized parts, manufacturing quotation, physical tests, firmware acceptance and failure/warranty plan. For a **verified sale**: actual completed settlement with accepted customer unit and return exposure. For **own-operation**: measured output/usefulness, power, maintenance and the opportunity cost of occupying equipment/space. No future or current output is assumed merely because a machine powers on.

No outreach, payments, purchases or shipments were made. These texts are supplier contact drafts and must be reviewed before sending.


## Institutional surplus: second supply lane, NOT automatically eligible e-waste

The sourcing sweep also recovered three **separately classified public-auction references**; see `examples/commercial_taiwan_institutional_auctions_2026-10-26.json` and `commercial_institutional_auctions.py`. These are not mixed into the 21 item/catalog prices.

1. **National Taitung University**, Oct 22, 2026, disposal of obsolete computers and IT equipment: <https://dga.nttu.edu.tw/p/406-1008-180365%2Cr677.php?Lang=zh-tw>. The particular auction required a certified waste recycler, business registration and NT$10,000 deposit, with rapid removal after payment. The event is **closed**. We cannot simply call this accessible personal used-equipment arbitrage.
2. **Bureau of Labor Insurance**, notice May 28, 2026: <https://www.bli.gov.tw/0109912.html>. Mixed metal shelving and electrical goods lot, **NT$388,620 starting reserve**, the notice describes broader bidder eligibility including individuals. The reserve is an entire mixed lot—not an electronic device resale price, a final settled bid, or a suitable pilot-scale acquisition.
3. **Cross-agency surplus notices index:** <https://www.taiwanbuying.com.tw/Query_PTYCompany.ASP>, a discovery channel only. Lot qualification, asset inventory, deposits, transport and any recycler licensing depend on each tender's actual rules.

Taiwan's Ministry of Finance publicly documents the legal process for disposal/valuation of approved retired state property: <https://law-out.mof.gov.tw/LawContent.aspx?id=FL037175>. Institutional auctions may produce substantial supply, but lawful ownership, dismantling/recycling licenses, data wiping, bid eligibility and *whole-lot* freight dominate the economics. **Our recommended first pilot remains ordinary lawful secondhand intact hardware, not unlicensed e-waste handling.**

The auction feed is replayed, but currently it yields no eligible upcoming lot and no unit-level financial arbitrage claims.


## Phase 2: seller-written quote intake (consolidation update)

The first 21 price records cover **17 Taiwan and four China market observations**. This is not 21 independent sellers or units. In particular:

- `TW-EXT-007` (Ruten ARK-1123) and `TW-EXT-008` (Shopee ARK-1123) are tagged as the **same apparent merchant/inventory pool**.
- `TW-EXT-012` and `TW-EXT-018` are the **same Meiya Waveshare RS-485 product reference** reused in two HS workstreams.
- The remaining 17 records have not been independently established as separate seller inventories either. There are **19 known observation groups**, not 19 confirmed available asset lots.

`commercial_external_evidence.py` now preserves this source-linkage information. `commercial_procurement_quote.py` keeps marketplace observations as RFQ leads until a direct written quote supplies exact model, variant evidence, source, tested condition, dated offer, confirmed quantity, warranty and delivery commitments. For each quote, it requires explicit per-unit costs for hardware, shipping, tax/duties, inspection/test time, materials/repair, data sanitization, warranty and environmental handling. Missing expense fields do NOT become free costs.

The portfolio replay publishes `commercial_rfq_register.csv`, one row per price observation with `observed_offer_group`; this is a **source verification work queue**, not an order sheet. It also accepts repeated `--supplier-quote /path/to/dated_quote.json` inputs, but there are currently **zero actual signed/direct supplier quote files**. Synthetic test fixtures prove only the parser and rules, never ownership, contact, supply or profit.

A completed quote screen can at most be `QUOTE_REVIEW_READY`, and always reports `purchase_authorized: false`. Subsequent physical acceptance and validated end-use or sold-price evidence are still separate.
