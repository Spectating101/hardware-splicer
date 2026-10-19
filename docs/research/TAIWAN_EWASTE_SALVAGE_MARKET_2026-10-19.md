# Taiwan broken-electronics sourcing: value vs real repair risk
**Research date:** 2026-10-19. **Currency:** TWD / NT$.
**Evidence status:** Public, unverified listing asking prices; zero live purchase, no same-model confirmed completed sales, no actual physical testing or success-yield measurements.

## 1. Source stock and valuable product pathways

The UN/UNITAR Global E-waste Monitor 2024 records 62 million tonnes of global e-waste in 2022, of which 20.4 million tonnes were small equipment and 4.6 million tonnes small IT/telecom. These are **global generation categories, not measured Taiwan marketplace supply**, available profitable devices or verified repair yields.

Three separate routes: **(A)** refurbish a damaged whole product into a functional same-model unit; **(B)** part-out economically unrepairable stock for already verified components; **(C)** create a new specialized product using reclaimed hardware. The third might sell for more, but it requires independent demand, integration and physical/safety validation. You cannot treat the retail price of an unrelated high-end product as a resale forecast for a prototype.

## 2. Concrete online price signals

| Target | Public asking evidence | Competing price evidence | Confidence / fault gate |
|---|---|---|---|
| TSC TTP-244 Plus label printer | Faulty parts-only variant: **NT$500-1,500** | Working/used related TTP-244 Pro / Plus listed **NT$1,960-3,115**; replacement head **NT$2,880** | **First conditional pilot**, if specific printhead already prints cleanly. Variant-price floor is not an accepted quote. |
| TSC TC200 label printer | Seller says cannot operate it, sells as broken **NT$500** | No reliable same-model completed sale verified | Watch. Ask exact model, actual power adapter, self-test and head evidence. |
| Brother QL-800 label printer | Power-on but function untested, **NT$500** | New QL-800 advertised **NT$5,390-5,690**; used QL-700 different model **NT$2,300** | New retail is NOT used resale; need QL-800 sold prices. |
| HP P1505N mono laser printer | Broken **~NT$300** | Some other used HP mono models with toner listed ~**NT$1,500-1,680** | Shipping, toner, repairs and returns erase apparent margin. |
| Acer SA241Y 23.8-in LCD monitor | Faulty **NT$250** | No exact-model successful resale comps | Heavy, breakable; if panel damaged, parts-only. |
| Older faulty laptops | Parts-only ASUS/Acer, **~NT$250-1,600** depending model | Many unrelated used business desktops/laptops for several thousand | Old chipsets, locks, missing RAM/storage, battery risk, poor comparability. |
| Fujitsu fi-6770 document scanner | One **NT$100 parts-only** listing, completeness not established | A3 scanners command much more across very different models and conditions | Invalid price-arbitrage claim until exact specimen and buyer established. |
| Specialist industrial scanner | Some used tested devices advertised **NT$4,000-28,000+** | Premium B2B replacement context | High asking prices NOT proof of fast actual sales or cheap matching dead donors. |

Source examples: Ruten public search links at bottom. Search-card asking prices can be minimum prices for parts selectors, quotation or different configuration. Listings marked 故障品 / 零件機 / 報帳機 / 殺肉機 / 不退貨 / 功能未測 are NOT diagnoses, and an NT$1 or NT$99,999 card is often a placeholder. Some Taiwan Ruten hits ship from mainland China. Seller photos may not depict the exact deliverable.

## 3. Unit economics, without the fake high margins

HS already has a DEVELOPMENT reuse-economics comparator; this research introduces a separate, explicitly hypothetical **production acquisition** screen. The screen includes procurement cost, both directions of shipping, successful/failure labor, parts, sales fee, packaging, returns/warranty reserve and residual scrap value.

    success_contribution = sale*(1-fee) - parts - outbound - packing - warranty_reserve - successful_hours*hourly_labor
    failure_contribution = failure_salvage_proceeds - failure_hours*hourly_labor
    profit_per_acquired_unit =
        p_success*success_contribution + (1-p_success)*failure_contribution
        - purchase_cost - inbound_shipping - intake_hours*hourly_labor

The **maximum rational bid** is the purchase price yielding zero modeled profit; the **target-profit bid** deducts the required profit per acquisition. Negative bid means even a free unit would be uneconomic under the specific assumptions.

### Illustrative modeled outputs — NOT achieved profit

Assumptions include **NT$250/h labor** and **10% hypothetical selling fees**; these are sensitivity inputs, not known commercial terms. Success probabilities and modeled resale prices are not observed. The report keeps same-model sold comps marked missing or imperfect.

| Target | Modeled buy | Modeled resale | Modeled success yield | Expected net **per bought item** | Max bid to target **NT$300/item** |
|---|---:|---:|---:|---:|---:|
| TSC TTP-244 Plus with **usable printhead** | 500 | 2,800 | 70% | **+339** | **539** |
| Brother QL-800 untested | 500 | 2,000 | 65% | +24 | 224 |
| HP P1505N faulty | 300 | 1,500 | 55% | **-476** | -476 |
| Acer SA241Y damaged LCD | 250 | 1,200 | 50% | **-480** | -530 |
| Old laptop parts machine | 800 | 2,500 | 45% | **-667** | -167 |

TSC sensitivity at NT$500 acquisition:
- Modeled sale **NT$2,800**, success **70%** => **+NT$339/unit**.
- Modeled sale **NT$2,400**, success **70%** => **+NT$87/unit**.
- Modeled sale **NT$1,960**, success **70%** => **-NT$190/unit**.
- Modeled sale **NT$2,800**, success **40%** => **-NT$102/unit**.

A defective NT$2,880 TSC printhead invalidates the recovery hypothesis. This is why HS must screen actual critical components rather than trust the price wedge.

Run the transparent model:
    PYTHONPATH=src python -m scripts.screen_tw_salvage_opportunities
    PYTHONPATH=src python -m pytest -q tests/test_salvage_purchase_screen.py

Raw scenario definitions and machine-readable results are in this folder. Screen returns **purchase_authorized=false** irrespective of an attractive modeled surplus. Sold price, yield and correct seller quote must be empirically verified before procurement approval.

## 4. Shortlist, and what HS should actually build

**Tier 1: single business-label-printer pilot (conditional).** Try to screen a genuine TSC TTP-244 Plus / Pro or Brother QL-800, not 10 random printers. Ask seller for the exact SKU, serial obscured in public outputs, all included peripherals, external power-adapter rating and provenance, a self-test label, evidence of uniform printhead heating/print quality, USB/driver compatibility, label/ribbon feed, paper sensor and visible fault codes. Reject obviously broken heads, burnt mains circuitry, uncertain ownership and “generic parts” listings. The conditional TSC bid ceiling for NT$300 modeled contribution is **NT$539**, only if the optimistic resale/yield scenario later holds. Do not issue a bid on current evidence.

**Tier 2: professional ADF scanners / POS optical readers.** Potentially higher value density than home printers, but no robust *same-model broken buy versus verified completed-sale* pairing yet. Seek an affordable particular unit, known consumable roller, matching current software support and local buyer. A premium scanner listing is not evidence that its shell or internals can be monetized at that figure.

**Tier 3: business mini-PC → industry appliance.** Reuse low-cost retired office PCs as local data collection, maintenance kiosk, vision/OCR or factory terminal. The extra product value is new, buyer-validated workflow software and service, not the cheap motherboard. Selling the same old computer with branding cannot command a premium reliably. Test B2B willingness-to-pay separately.

**Reject/defer:** low-value old laptops, cracked LCD panels, consumer inkjets, bulky mono laser machines, phones with unknown locks/batteries, CRTs, UPS, appliances with capacitors/high voltage, and industrial high-power controls without test equipment or qualified operators. These are not suitable first physical-agent cases.

## 5. Sourcing pipeline and seller diligence

Public platforms:
- **露天 Ruten:** search exact model + 故障品, 零件機, 報帳機, 未測試, 清倉, 殺肉機; save timestamp, seller region, variant, actual delivered model, condition and shipping.
- **蝦皮 Shopee:** compare exact new/used model, printhead/roller/adapter costs, shipping; beware variant selector minimums and incompatible consumables.
- **旋轉拍賣 Carousell / local pickup:** potentially lower transport risk but still verify legal ownership and actual specimen; no implicit live-availability claim.
- **Business decommission / campus-surplus purchase:** only with authorization and written ownership transfer, responsible secure storage/data wipe, and suitable recycling/waste-handling legal position. Do not take from regulated collection/recycling streams without confirming permits and applicable category.

Before any payment record (a) listing and exact model photos, (b) quote including fees/freight, (c) seller reply/return terms, (d) fault evidence, (e) matching verified successful-sale comparable, (f) parts availability and warranty, (g) actual bench test plan and consent, (h) residual-value fallback if unusable. Only then run acquisition underwriting.

**Market failure modes:** retail asking price is not an actual transaction; listing “sales” count need not represent the shown variant; sellers who say “untested” may know the unit fails; missing printhead can cost more than restored product; imported repair parts may lack support; used-device returns eliminate margin. Community flip/repair anecdote corroborates risk, not Taiwan success rates.

## 6. Regulatory, privacy and safety limits

Taiwan official rules cover registered collection/processing of regulated waste and requirements for facilities. Purchase of a lawfully owned *used product* for lawful reuse may have a different legal position from collecting and processing regulated waste, but do not assume all reclaimed electronics are exempt. Consult the Ministry of Environment and professional legal guidance before operating a waste-collection, dismantling, processing, resale or cross-border channel. Do not salvage from designated e-waste collection bins without authority. Wipe user data appropriately; comply with product electrical/consumer and radio/industrial obligations where applicable. No software result proves that a restored device is physically safe.

Official laws:
https://oaout.moenv.gov.tw/law/LawContent.aspx?id=FL020203
https://oaout.moenv.gov.tw/law/LawContent.aspx?id=FL042369

## 7. Web evidence index — URLs, not completed-sale confirmations

Global source (UNITAR): https://unitar.org/about/news-stories/press/global-e-waste-monitor-2024-electronic-waste-rising-five-times-faster-documented-e-waste-recycling

- Broken printer inventory: https://www.ruten.com.tw/search/%E9%9B%B6%E4%BB%B6%E6%A9%9F/?cateid=00110028
- TSC faulty and printhead/spares: https://www.ruten.com.tw/find/?q=tsc+244+plus&sort=ords%2Fdc
- Used TSC label printers: https://www.ruten.com.tw/search/%E4%BA%8C%E6%89%8B%E6%A8%99%E7%B1%A4%E6%A9%9F/?sort=ords%2Fdc
- Brother QL series incl. new/untested/older used: https://www.ruten.com.tw/search/brother%20ql/
- Faulty laptop stock: https://www.ruten.com.tw/search/%E6%95%85%E9%9A%9C%E7%AD%86%E9%9B%BB/
- Faulty LCD stock: https://www.ruten.com.tw/search/%E6%95%85%E9%9A%9C%2B%E8%9E%A2%E5%B9%95/?cateid=00110025&sort=new%2Fdc
- Fujitsu scanner stock and replacement rollers: https://www.ruten.com.tw/search/fujitsu/?cateid=001100030004&sort=prc%2Fac
- Business scanners (used): https://www.ruten.com.tw/search/%E4%BA%8C%E6%89%8B%E6%8E%83%E6%8F%8F%E5%99%A8/?sort=new%2Fdc
- Mini PCs: https://www.ruten.com.tw/search/%E4%BA%8C%E6%89%8B%E8%BF%B7%E4%BD%A0%E4%B8%BB%E6%A9%9F/?cateid=0011&sort=new%2Fdc
- Used printer competing asks: https://shopee.tw/search?keyword=%E4%BA%8C%E6%89%8B%E5%8D%B0%E8%A1%A8%E6%A9%9F
- Community risk, NOT pricing benchmarks: https://www.reddit.com/r/Flipping/comments/nmls5a/why_do_so_many_sellers_of_electronics_not_test/ and https://www.reddit.com/r/Flipping/comments/xu53jd

## 8. Commercial milestone

**First practical result is an accurate reject list**, not more optimistic resale ads. Next do two distinct validations: a verified sold-price / sell-through check for a precise printer model, and a lawful physically inspectable seller unit at/below a bid ceiling that survives downside sensitivity. Only then could HS generate a human-reviewed procurement request and a donor mission.

**No physical purchase, inspection, payment or readiness promotion occurred in this research.**
