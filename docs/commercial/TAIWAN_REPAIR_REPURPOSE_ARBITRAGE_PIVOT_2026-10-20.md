# Hardware Splicer — repair / refurb / repurpose arbitrage first

2026-10-20. This **supersedes the commercial-priority recommendation** in TAIWAN_LOW_COST_BUILD_AND_SELL_PILOT_2026-10-20.md (the robotics/product-factory premise was the wrong priority). Keep that earlier research only as background on workshop cost; **do not source components for a retail robotic arm**.

## What the user intends

A hardware-splicing *business*: find mismatches between seller-assessed salvage value and realistic repairable/repurposed device value. Buy a genuinely distressed but diagnoseable device below a risk-based bid ceiling; restore, test and resell, or use as workshop hardware if no buyer exists. Consider:
- iPhones/other phones and related devices
- Nintendo Switch Lite/PSP or other gaming devices
- Discarded or defective laptops and PC boards
- Portable Linux cyberdecks made from verified reusable components

DUM-E/robot arms are **tooling for our factory**, NOT the default SKU. Hardware Splicer's differentiation should be investigating the actual device, using schematics, visual inference, diagnostics, repair/salvage triage, custom CAD/firmware when helpful, and recording economically useful outcomes.

## Real Taiwan listings, not a hypothetical product invented to sell

Indicative seller asking prices from Ruten Taiwan and repair-service websites, available in October 2026, subject to availability and exact variant. No purchase, checkout, completed sale or physical inspection was done.

| Lane | Distressed observation | Comparable used condition | Competing repair/part evidence | Critical point |
| --- | --- | --- | --- | --- |
| iPhone 12 | NT$699 parts-only, doesn't charge/boot and cracked screen: https://www.ruten.com.tw/item/22637616116001/ | Used iPhone 12 128GB, functioning offers NT$3,500–5,200+: https://www.ruten.com.tw/search/iphone%2012%20128g%20%E4%BA%8C%E6%89%8B/?sort=new%2Fdc | Screen modules NT$990–1,629 advertised: https://www.ruten.com.tw/item/22631243371925/ | Apparent gross spread is NOT repair profit: no-boot board fault, screen, battery, previous-owner/Activation Lock, water and parts pairing; STOP until verifiable |
| Lenovo B51-30 | NT$850 *not powering on* parts-only: https://www.ruten.com.tw/search/%E4%BA%8C%E6%89%8B%2B%E6%95%85%E9%9A%9C%E7%AD%86%E9%9B%BB/ | Identical family working B51-30 offer about NT$2,300: https://www.ruten.com.tw/search/%E7%AD%86%E9%9B%BB%20%E4%BA%8C%E6%89%8B/?cateid=001100020009&isauth=1&location=tw&sort=ords%2Fdc&user=tw | SSD/adapter/spares unknown; quoted NT$300 materials in model is an **assumption** | Low enough to investigate as organ donor for a cyberdeck, but non-power state cannot validate panel, keyboard or board reuse |
| PSP 1007 with UMD problem | NT$1,000, claimed controls work, no battery/charger and optical/UMD fault: https://www.ruten.com.tw/search/psp%20%E4%B8%BB%E6%A9%9F/ | Other functional PSP models advertised NT$1,790–3,200; model and kit mismatch affect comparability: same search | PSP battery NT$159–189 and charger around NT$89: https://www.ruten.com.tw/search/psp%20%E9%9B%BB%E6%B1%A0/ | Generally too little spread at NT$1,000 unless personally useful, discounted or the fault proven isolated; other PSP series are not perfect comparators |
| Switch Lite *single joystick drift target* | **NO confirmed live defective donor listing at the required price** | Working used offers NT$3,000–4,300: https://www.ruten.com.tw/search/%E4%BA%8C%E6%89%8Bswitch%2Blite/ | Licensed independent repair market Switch Lite joystick work NT$700–800 (Dr.A): https://www.dra-3c.com/repair/switch-repair . Another provider lists NT$300: https://shop.happytvgame.com/price_switch.php | Best **search target**, not presently executable trade. Must prove game/charge/boot/screens/buttons are good and the failure truly is stick drift. Don't buy unknown charging-board/screen faults. |

**Important locked-device and buyer-protection controls.** Apple specifically says **do not buy** a used iPhone with Activation Lock still enabled; it must be erased and removed from the previous owner's Apple account: https://support.apple.com/en-au/108794 . Parts & Service History can show non-genuine/unknown/unverified repairs and replacement component issues: https://support.apple.com/en-us/102658 . Never bypass owner/security locks, purchase dubious provenance, copy or retain previous users' data, or call an unknown iCloud-locked motherboard a repair opportunity.

## Expected-value screen vs misleading headline spread

The executable screening algorithm is in scripts/evaluate_repair_arbitrage.py, with exactly sourced ask/comparable/parts URLs and **unmeasured, replaceable** probability, labor and salvage assumptions in examples/procurement/taiwan_repair_resale_arbitrage_20261020.json.

Formula:

    expected unit contribution = p_success × (sale ask × (1-fee)
       - purchase - paid parts - inbound/outbound shipping - repair labor - warranty reserve)
       + (1-p_success) × (salvage-if-failed - purchase - inbound shipping - diagnosis labor).

A seller's used **ASK** is not an executed sale: actual sale values may be lower. The model conservatively targets **at least NT$250 positive expected unit contribution before fixed overhead/tax** and **no acquired goods are assumed**.

| Case | Asking/potential test bid | Success chance (ASSUMED, not observed) | Expected contribution | Max bid for >=NT$250 expected contribution | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Nonboot broken iPhone 12 | Seller NT$699 | 20% | -NT$544 | NT$0 | Reject; owner lock, board, display all unknown |
| Nonboot Lenovo B51-30 | Seller NT$850 | 40% | -NT$420 | NT$180 | Reject at ask; only possible donor if tested and much cheaper |
| PSP1007 UMD fault | Seller NT$1,000 | 65% | -NT$357 | NT$393 | Reject at ask; may be useful if we accept hobby expenditure |
| Switch Lite *single-stick-only* | **NO seller identified**, hypothetical NT$1,600 bid | 85% | +NT$778 at hypothetical bid | NT$2,128 | Potential priority **ONLY when a real, inspected seller unit appears** |
| iPhone 12 *working/unlocked except screen* | **NO seller identified**, hypothetical NT$1,800 bid | 85% | +NT$76 at hypothetical bid | NT$1,626 | Even apparently simple phone flips can fail return-adjusted profit hurdle |

These are sensitive illustrations, **not calibrated empirical repair-success probabilities, transactions or pricing recommendations**. Unit downside from a failed repair is a key factor. The option of harvesting parts is not automatically worth the total asking price: salvage-component reuse must first be validated and sold/used at a supported value.

## Other, potentially stronger arbitrage business models

**Repair services using customers' legitimately owned devices:** no purchase risk and the customer already proves the device has value. Example published local service menu: NT$700–800 for Switch Lite stick replacement, around NT$3,600–4,000 for non-original iPhone 12 screen service depending on grade/repair shop, before warranty/parts/labor. At least initially, this might beat buying no-boot inventory, but price competition and customer expectations matter. Service pricing: https://www.dra-3c.com/repair/switch-repair and https://www.sogi.com.tw/shops/1804/repairs/products/323 . These are competitor prices, not our authorized service offers. Do not advertise commercial repairs without adequate tools, competence, legal/business arrangements, parts sourcing, privacy and warranty policy.

**Part-out and harvest economics:** for broken laptops, game consoles and printers, use donor *verified* parts instead of forcing a complete restoration. A working display, keyboard, motors, encoders, cooling hardware or speakers can be reused by HS projects. But only recognize saleable spare value after identity/testing/compatibility and actual resale quotes; otherwise record its opportunity as internal reuse with unpriced utility.

**Cyberdecks as personal-use salvage synthesis:** cheap proprietary hardware parts do not imply profitable new cyberdeck sales. A Raspberry Pi Zero 2 W is offered from roughly NT$590–920; a 7-inch HDMI touchscreen about NT$1,500–1,600; compute+screen alone already starts near NT$2,090. Sources: https://www.ruten.com.tw/search/raspberry%20zero%202%20w/?cateid=0011&sort=ords%2Fdc and https://www.ruten.com.tw/search/7%E5%90%8B%2Bhdmi/?cateid=0011 . Add keyboard, battery/charger safety, housing, power regulation and support. Build from salvaged keyboard/screen/known-working SBC first if genuinely cheap. Treat cyberdecks as a differentiated niche product only after actual demand testing, and as a useful portable HS diagnosis terminal even if sales fail.

## Buy/no-buy practical scan order

1. **Bring seller-discounted, booting single-fault units**, with complete photos/video and serial/model/ownership confirmation, to the top. Targets: joystick-only Switch Lite, battery-only laptop/handheld, known-working laptop with bad hinge/casing, cracked display only with functioning output verified. Avoid battery-swollen or liquid-damaged devices until equipped for them.
2. **Reject listed non-boot multi-fault phones** unless they are explicitly justified as low-cost *parts-only* stock with verified provenance and a credible salvage recovery path. A NT$699 nonboot iPhone is not a NT$3,500 arbitrage simply because a working iPhone is worth more.
3. **Put purchase ceilings in software before shopping**; if the seller asks above EV-based ceiling, automatically mark HOLD/REJECT, not 'buy cheap'.
4. **Only one pilot donor initially**, not a five-device basket. Record condition, seller answers, price, successful owner-unlock/bench tests, measured recovery time, replacement-part invoices, power/current results and post-repair functional diagnostics.
5. **Compare personal-use fallback honestly:** own spare test phone, a retro game device, a portable Linux cyberdeck, or compatible recovered workshop components. Never double-count 'usable to us' and its resale value as two realized benefits.
6. **Use HS as the value-creation engine:** identify device, inspect symptoms, collect public manuals, propose diagnosis and splice options, generate exact part identities and alternative recovery paths, run controlled repair, validate work and log costs. The robot is *optional workshop tooling*, not the main inventory being sold.

## Immediate bottleneck and work authorization

A storefront-scale business requires repeatable **inbound inventory at a sufficiently low discount**, not another layer of CAD. We have credible listings for damaged devices and market price anchors, but as of this review **no clearly documented, currently available, single-fault donor whose ask price and risk-adjusted margin justify a purchase**. Targeted local buy/sell groups, school secondhand markets, legitimate repair shops and buyback partners could supply those leads, but no vendor agreements or live inventory are verified.

The action we should perform next is a live source-monitoring pass for **specific booting/single-fault donors under HS bid ceilings**, then negotiate/inspect ONE, and only then spend on parts. The earlier DIY retail arm strategy is explicitly deprioritized.
