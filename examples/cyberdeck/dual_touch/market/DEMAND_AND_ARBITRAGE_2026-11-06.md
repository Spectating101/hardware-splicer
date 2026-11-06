# Pocket cyberdeck market: demand, sourcing and buy/build arbitrage
**Evidence date:** November 6, 2026 | **Markets:** global enthusiast hardware; Taiwan; Indonesia | **Project:** HS dual-touch clamshell draft [PR #292](https://github.com/Spectating101/hardware-splicer/pull/292)

**Question:** Is there *paying demand* for a cheap, calculator-size, fold-shut SSH pocket terminal (possibly two 4.3-inch touchscreens), and if so should HS build it, resell existing hardware, sell kits, or stop?

**Verdict:** There's **strong evidence that a global niche purchases specialized pocket/open-hardware computers**, but **no identified transaction data or preorder cohort proving demand for our exact two-glass-screen SSH device**, and **no verified Taiwan/Indonesia volume** for that device. Do **not** stock finished custom products yet. The best business next action is **qualified demand validation at stated price points** and a **real one-screen SSH usability prototype**, while separately studying import/reseller/firmware-service margins.

## Evidence strength ladder (do not add these as TAM)

| Signal | Dated observed evidence | Evidence strength | What it cannot establish |
|---|---|---|---|
| **PocketMage PDA** | [Crowd Supply](https://www.crowdsupply.com/talisman-design/pocketmage), Aug 20 2026: **1,205 backers**, **US$463,365 pledged**; current public kits US$210 / assembled US$260; **manufacturer Oct 29 update** says parts ordered, shipment anticipated March 2027 ([update](https://www.crowdsupply.com/talisman-design/pocketmage/updates/production-status)) | HIGH: cash pledges in an adjacent product | Not dual touch; uses tactile keyboard + e-paper/OLED. Pledges aren't shipped units/profit. Total raised includes reward mix, not the product ASP. |
| **MNT Pocket Reform** | [Crowd Supply](https://www.crowdsupply.com/mnt/pocket-reform): **~432 backers**, US$632,984 pledged, US$1,200–1,469 current purchase; Aug 19 2024 [all crowdfunding units shipped](https://www.crowdsupply.com/mnt/pocket-reform/updates/all-crowdfunded-mnt-pocket-reforms-have-shipped) | HIGH: paid and physically delivered niche pocket/Linux buyers | Fundamentally higher-end Linux computer; cannot infer cheaper gadget demand |
| **KeyGo Gen2 Pro** | [Kickstarter](https://www.kickstarter.com/projects/1794064432/keygo-gen2-ultra-slim-folding-keyboard-with-4k-touch-screen): campaign Feb 10–Mar 7 2026, **1,770 backers**, **HK$4,965,010 pledged** | HIGH: cash pledges for a folding screen/keyboard interaction device | Much larger foldable keyboard/display accessory, not cheap miniature SSH nor dual capacitive glass; fulfillment not independently verified |
| **Taiwan T-Deck Plus retail** | [Ruten category search](https://www.ruten.com.tw/search/t-deck/?cateid=0011), Nov 2026: most basic T-Deck Plus **NT$2,959–3,300 asking**; one listing shows **3 recorded sales**, other sampled listings show **0** ([zero-sale listing](https://www.ruten.com.tw/item/22636550243143/)) | MEDIUM: public asking price and limited visible marketplace sales count | Not market-wide volume. Counts don't prove sustained demand or wholesale availability |
| **M5Stack Cardputer ADV** | [Manufacturer](https://shop.m5stack.com/products/m5stack-cardputer-adv-version-esp32-s3), US$29.90, **251 posted reviews** in current product page; [Taiwan Ruten](https://www.ruten.com.tw/item/22623843241692/) lists a product/variant range **NT$1,038–2,058** | MEDIUM/LOW: actual offering + public reviews | Reviews are not purchase counts; Ruten listing has multiple variants and can't establish a like-for-like wholesale flip |
| **ClockworkPi uConsole** | [Official shop](https://www.clockworkpi.com/shop) and [Oct 2026 forum/Reddit delivery discussion](https://www.reddit.com/r/ClockworkPi/comments/1x1e8r5/uconsole_wait_time/). Users report months of waits; Amazon resellers ~US$30–40 premium claimed in thread. | MEDIUM: anecdotal observed demand/fulfillment friction | Waiting time could reflect limited manufacturing, not a vast waiting buyer pool; premium not verified sales |
| **Cyberdeck form factor social** | [Feb 2026 Reddit](https://www.reddit.com/r/cyberDeck/comments/1r8kmhu/i_dream_for_this_form_factor_again/) ~1,064 votes for pocket keyboard/sliding form; [Oct 2026 SolarOS T-Deck](https://www.reddit.com/r/LilyGO/comments/1xeyiye/solaros_on_lilygo_tdeck_plus/) ~192 votes for SSH handheld firmware | LOW: qualitative interest | Likes, stars and comments ≠ willingness to pay at NT$6k–8k |

**Crucial distinction:** The crowdfunding examples validate **niche purchasing, openness, tactility and hardware identity**, not the prediction that a two-touchscreen device will sell. Physical keys repeatedly appear in the paid comparators; a virtual glass keyboard has a usability handicap for shell commands.

## Taiwan / Indonesia product price and channel findings

**Taiwan:**
- T-Deck Plus Ruten basic asking band **NT$2,959–3,300**, with visible near-zero/single-digit sales on sampled offers; sellers exist and buyers can already import gadgets.
- Cardputer ADV multi-option Ruten asking range **NT$1,038–2,058** is not a single SKU price. Need actual checkout and verified SKU before concluding anything about price differences.
- Our dual-touch build uses **two** exact Waveshare 4.3 touch modules; Taiwanese [ICShop listing](https://www.icshop.com.tw/en/products/368031700131) **NT$1,250 each** in engineering case, listing availability unconfirmed / previously reported sold out. BOM price is **not a delivered supplier quote**.

**Indonesia:**
- [Blibli M5Stack brand page](https://www.blibli.com/brand/m5stack) advertises **Cardputer ADV Rp1,425,000**; the broader [Blibli category](https://www.blibli.com/jual/keyboard-stack) surfaced an **Rp999,990** seller offer. This destroys any claim that Rp1.425M is the universal clearing price.
- [Mouser Indonesia SKU K132-Adv](https://www.mouser.co.id/en/ProductDetail/M5Stack/K132-Adv) has surfaced a **Rp548,545** unit list; its scraped description inconsistently labels Cardputer v1.1 rather than ADV despite SKU string. **Do not treat it as verified identical stock until manufacturer SKU, VAT, delivery and invoice are reconciled.** Even if identical, gross ask-price gap **Rp451k–876k** before freight, tax, duties, marketplace fees, returns, potential wireless-certification obligations and unsold inventory.
- [Shopee Indonesia uConsole](https://shopee.co.id/ClockworkPi-uConsole-Kit-V3.14-for-Indie-Developers-And-Hobbyists-Compatible-with-Raspberry-Pi-CM4-i.1807115142.53961427974) asks **Rp7.66M–14.95M** across distinct variants; **no verified sell-through** or unit condition. A price range alone cannot support retail arbitrage.
- Indonesia's [Permen Kominfo No. 3/2024 device certification](https://jdih.komdigi.go.id/produk_hukum/view/id/892/t/peraturan%2Bmenteri%2Bkomunikasi%2Bdan%2Binformatika%2Bnomor%2B3%2Btahun%2B2024) and [US International Trade Administration guidance](https://www.trade.gov/country-commercial-guides/indonesia-standards-trade) flag extra obligations for commercial Wi-Fi/Bluetooth products. Check exact device and import pathway; a personal evaluation unit is not a commercial authorization.
- Taiwan battery-enabled wireless products may also involve applicable NCC/BSMI certification/labeling obligations, dependent on device/product classification. Do not assume a pre-certified ESP32 module confers finished-product approval.

**Do not confuse a shipping backlog, listing, review count or crowdfunding backer with completed local retail sell-through.**

## Who is *likely* to buy? Distinguish demand from hypotheses

| Buyer segment | Primary desired outcome | Likely barrier | Confidence |
|---|---|---|---|
| Open-source, cyberdeck and retro-PDA enthusiasts | Distinctive physical form, programmable, repairable, uncommon | Fit, appearance, reliability, price relative to PocketMage, competition | Higher interest; paid niche comparators |
| Remote Linux operators, homelab owners, agent supervisors | Instant authorized SSH/tmux to persistent machines | Text readability, glass keyboard, security, reconnection; phone works already | Need proof of WTP |
| Security/field techs | Reliable terminal with proper modifiers, battery and network tools | Requires robust physical keyboard, possibly wired Ethernet, weatherproofing | Weak for all-glass variant |
| Maker kits/education | Learn ESP32 firmware, engineering, source/modifiable case | Wants **lower price**, toolkit, manual, components preassembled | Interest plausible, no sales demonstrated |
| Nostalgia/collectors | Folding gadget, unusual dual-screen interaction | Price, battery life, commercial finish | Interest plausible; may pay premium if polished |

**Hypothesis to test:** for *paid professional SSH use*, physical controls may outperform two glass screens; for *collectible pocket computing*, dual touch + aesthetics may justify a premium. **No cohort purchases have verified this split.**

## Competitive routes ranked for commercial experiment

1. **Open-source case + verified SSH software bundle / maker kit:** no major hardware inventory upfront. Can price individual designs, finished prototype kits or verified software setup; but free CAD/firmware substitutes exist. Need actual users and legitimate licenses.
2. **Local value-added configuration of an existing T-Deck Plus/Cardputer:** procure exact unit from a seller at confirmed delivered cost, solve secure SSH and keyboard semantics, charge for tested functionality and support. Very low hardware differentiation and margin; not a guaranteed sell.
3. **Small, deposit-validated run of fully functioning HS dual-touch devices:** recognizable differentiated product, but costs, keyboard UX, Z fit, battery, compliance, QA, warranty and demand all unverified.
4. **Pure Taiwan→Indonesia cross-border retail arbitrage:** possible price gaps but many SKU/tax/compliance gaps and existing local sellers. No pre-buy without two fulfilled-source quotes, sell-through and legal route.

## 2026-11-06 per-unit cost sensitivity (not actual prices or hours)

Use the frozen [HS CAD+parts case](../evidence/native_mecha/budget.json), **NT$2,965** parts benchmark. For a 1-unit hand-built commercial scenario we separately assume:

| Variable | NT$ / unit | Evidence |
|---|---:|---|
| Parts | 2,965 | HS seller ask + BOM estimates |
| Freight and procurement slippage | 350 | Hypothetical |
| Assembly: 2.5 hours × 200 | 500 | Hypothetical labor rate |
| Flash, QA and diagnostic 2 hours × 200 | 400 | Hypothetical labor rate |
| Print retry/finishing beyond the existing BOM | 60 | Hypothetical |
| Packaging/outbound handling | 150 | Hypothetical |
| Warranty/DOA returns reserve | 350 | Hypothetical |
| **Total variable cost before selling fees** | **4,775** | Scenario |

Assume **13%** effective transaction/platform/payment fees. Revenue after fees = \`sale_price × 0.87\`.

| Customer retail price | Modeled unit contribution after variable cost | Comment |
|---|---:|---|
| NT$4,490 | −NT$869 | Loss even without fixed R&D |
| NT$5,490 | +NT$1 | Essentially break-even |
| NT$5,990 | +NT$436 | Weak buffer against error |
| NT$6,490 | +NT$871 | Candidate if 2-digit unit volume exists |
| NT$6,990 | +NT$1,306 | Comparable to specialist product premium |
| NT$7,490 | +NT$1,741 | More attractive margin but WTP unproven |

**Fixed costs excluded:** CAD/firmware hardening, prototype failures, testing equipment, photography, customer acquisition, returns over reserves, certification and business overhead. Hypothetical **NT$30,000** fixed R&D at **NT$6,490** requires ~**35 sales** to break even *before* any further fixed costs. With only 10 sold, break-even retail price would be about **NT$8,937** at these exact assumptions. These are *not* forecast volumes or profit.

### Arbitrage math is not the same as original-product economics

- **Retail flip:** margin = *actual resale proceeds* − *delivered exact-SKU acquisition price* − platform fees − compliant logistics − warranty/returns − overhead. A US$29.90 MSRP and an Indonesian posted price cannot alone establish margin.
- **HS build:** margin = *realized buyer ASP* − *actual BOM* − assembly/test/shipping/fees/returns; absorb substantial one-time design work.
- **HS tool/service:** value of reproducible CAD, diagnosis, firmware, integration: can be monetized with little hardware stock, but consumers may prefer existing free/open-source tools.

## No-inventory validation design

**Do not order batches and do not take money or imply finished devices while hardware and radio/battery safety are unproven.**

1. Build one legitimate proof: authenticated, pinned-host-key **SSH and tmux** over the exact single Waveshare panel. Demonstrate screen readability and real latency.
2. Make a side-by-side, honest demo: **(A) NT$3,990–4,990 physical-key compact terminal** versus **(B) NT$5,990 / NT$7,490 dual glass clamshell**. The prices are *survey propositions*, NOT live offers and NOT established unit costs; mark lead times, weight and firmware readiness unknown.
3. Recruit **20 qualified potential buyers** from non-overlapping communities: Linux/homelab, retro computing/cyberdecks, field developers, TW/ID makers. Ask price ceiling, use frequency, keyboard trade-off, willingness to give up phone, and whether their purchase is conditional on real video proof.
4. Run a public interest list **with stated prices** and location/shipping preferences. A like/email is weak evidence. **10+ qualified buyers willing to confirm purchase at ≥NT$6,490 after real demo** is a working *screening threshold*, not a statistical demand forecast. Legitimate refundable deposits could be explored only **after** prototype, commercial eligibility and clear consumer terms.
5. Use actual checkout/fulfilled-sale data and support issues from the first small authorized batch to decide whether another production run is justified. Separate Taiwan and Indonesia; don't infer one market from the other.

### Red-team triggers / stop conditions

- If buyers say the 4.3-inch terminal text is too small or glass key action unusable, **pivot to physical keyboard/single-screen**.
- If real BOM + safety/compliance + QA makes fully compliant unit economically exceed NT$7,490 and leads refuse that price, **do not manufacture**.
- If the premium only comes from shipping backlog and no fulfilled buyers, do not buy inventory to exploit it.
- If merely selling unconfigured modules, substantial demand already has cheaper open retail channels; compete on genuine tested value or pass.

**Recommended decision:** **HOLD on physical stock, CONTINUE product/market discovery.** Demand exists in an adjacent collector/developer niche; profitable dual-touch cyberdeck production or regional retail arbitrage is **not yet proven**. Prioritize a single working SSH proof, buyer price tests, and exact delivered procurement comparisons.
