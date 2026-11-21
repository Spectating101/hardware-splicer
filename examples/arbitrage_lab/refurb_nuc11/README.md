# HS product refurbishment trial — real Taiwan NUC11PAH no-power listing

**As-of 2026-11-05. Device NOT acquired, inspected, repaired, or sold.**

This supersedes the cheap-bracket market example as HS's **primary applied engineering-arbitrage pilot**. It's a real observed broken x86 mini-PC; the product target is a **fully functional restored computer**, with an optional *separately valued* software appliance build after validation. No unearned upgrade premium is incorporated in the resale pricing.

## Real, independently sourced case and comparators

| Source | Item | Amount / limitation |
|---|---|---|
| [Ruten listing](https://www.ruten.com.tw/item/22635470508103/) | **Faulty NUC11PAH** mini-PC from Hsinchu, Taiwan | **NT$1,470 + NT$50–80 shipping**, seller says **no power/light**, may be dismantled, **no RAM or SSD**, no returns. Adapter inclusion and CPU grade unknown. |
| [Shopee comparator](https://shopee.tw/intel-NUC11PAH-i5-WD-SN750-500GB-SSD-%E7%BE%8E%E5%85%89crucial-8-8GB-RAM-i.1816617.23130231703) | i5 Panther Canyon 16GB / 500GB | **NT$9,000 marked sold out**; not a verified sell-through transaction, no active supply or realized sale proof |
| [Carousell](https://tw.carousell.com/p/intel-nuc-11-pro-%E8%BF%B7%E4%BD%A0%E4%B8%BB%E6%A9%9F-i5-1135g7-16g-500g-ssd-%E5%85%A7%E5%BB%BA%E5%8E%9F%E5%BB%A0%E6%AD%A3%E8%A6%8Fos-%E5%8E%9A%E7%89%88%E5%8F%AF%E6%93%B4%E5%85%85-%E9%99%84%E5%8E%9F%E5%BB%A0%E9%85%8D%E4%BB%B6%E7%9B%92%E8%A3%9D-1468726906/) | **Different** NUC11TNHi5 / 16GB / 500GB | NT$8,000 **asking price**; same CPU family not same PC model, cannot silently call an exact comparator |
| [Used RAM market](https://only2nd.com/price/ram/ddr4-sodimm-3200-8g) | DDR4-3200 1.2V SO-DIMM 8GB | 30-day *asking* median NT$825, small sample |
| [Used SSD Ruten](https://www.ruten.com.tw/item/22640804516783/) | NVMe SSD 256GB | Offered NT$580–730 across condition/variants; NT$700 assumed |
| [Delta PSU offer](https://www.low-price.com.tw/delta-19v-4.74a-ac-adapters.html) | Externally approved-type **19V 90W 5.5×2.5mm** compatible adapter | NT$1,050 asking; only needed as a sale cost if not included; verify polarity/fit/model |

Intel [NUC11PA official technical specification](https://www.intel.com/content/dam/support/us/en/documents/intel-nuc/NUC11PA_TechProdSpec.pdf) confirms the **NUC11PAH label does not identify i3/i5/i7**; identifies i3-1115G4, i5-1135G7, i7-1165G7 boards and their AA numbers. Memory requires DDR4-3200 1.2V SO-DIMM; verified [ASUS adapter matrix](https://www.asus.com/support/faq/1052533/) states 19V/90W and 5.5×2.5mm for NUC11PAH. No board evidence is in the seller listing beyond seller claims.

A public [independent NUC11PAHi7 teardown/photo](https://nucblog.net/2021/02/panther-canyon-i7-nuc-review-nuc11pahi7/) provides visual orientation **only**, not photo evidence of the defective unit.

## HS existing engines actually used

This uses the **existing**, non-LLM `apps/circuit-ai/src/intelligence/hardware_plan.py` `HardwarePlanOrchestrator`, rather than inventing a replacement board detective. On today's seller-only input it reports **no repair authority**. The generic orchestrator may generate non-NUC specific suggested parts. We intentionally **discard** its generic BOM/cost and only use its authority status; the NUC-specific OEM sources and economic costs control this case.

```bash
python3 examples/arbitrage_lab/refurb_nuc11/refurb_pilot.py
# Case outputs (never physical proofs):
# examples/arbitrage_lab/refurb_nuc11/evidence/refurb_decision.json
# examples/arbitrage_lab/refurb_nuc11/evidence/sensitivity.csv
```

`bench_observations.template.json` is entirely null until an **operator with actual acquired hardware** records tests. The economics runner refuses to claim physical restoration or purchase from seller assertions.

## Economics of an original physical product, not a bracket

The fixed per-unit scenario starts with **NT$1,470 broken unit + NT$60 inbound**, then assumes **NT$1,050 adapter**, **NT$825 RAM**, **NT$700 SSD**, **NT$200 low-voltage consumables**, **NT$500 success labor and validation**, **NT$150 packaging**, **NT$350 warranty reserve**, **10% selling fees**. Failure incurs acquisition, shipping, NT$300 diagnostic labor, NT$100 disposal and **zero salvage recovery**. Selling prices and success probabilities are *scenario parameters*.

The **conditional** profit of a working i5 unit sold for NT$8,000 would be **NT$1,895**, but if repair fails the outcome is **-NT$1,930**. At a hypothetical 50% repair probability, expected result **-NT$18**; at 75% it's +NT$939. At NT$9,000 selling price, 50% EV is +NT$432, still below the illustrative NT$500 deal threshold. Neither success probability nor resale price is independently established.

**Decision: no purchase/offer**. Unknown actual CPU, no-board-power condition and no-returns terms prevent reliable purchase probability calibration; lower i3 resale could destroy even the conditional margin.

## Safe fault-isolation and physical acceptance

Pre-purchase seller request: photos of exact model/AA board markings, close-up DC jack and motherboard, original PSU label and connector, proof of prior test (outlet, meter, PSU), and disassembly history. These are **not** evidence of function; they only narrow the risk.

1. **Unplugged inspection:** case/board integrity, damaged DC entry, missing or reworked parts, corrosion. Do not touch mains PSU internals.
2. **Power baseline with qualified bench operator:** documented known-good, manufacturer-compatible 19V 90W external adapter, correct polarity and barrel dimensions; observe actual front LED. If no LED after proper checks, power off and escalate board-level diagnostic; do not assert the cause.
3. **Symptom-specific diagnostics:** [ASUS official no-power](https://rog.asus.com/support/faq/1052686/) and [failed boot classification](https://www.asus.com/support/faq/1052510/) distinguish dark LED, blinks, solid/no video. Do not equate them or blindly flash BIOS.
4. **Only after verified POST:** fit approved SO-DIMM and SSD, perform real memory test, SMART/disk integrity checks, sustained thermal/stability run, ports/network/display checks, sanitized storage, accurate repair/warranty disclosure.
5. **Optional appliance conversion after hardware success:** a Linux edge gateway, local NAS or repair-shop test controller may add utility, but revenue is not increased without actual buyer willingness to pay and a tested instance.

The machine must stay in state **NO_PHYSICAL_PROOF** until real hardware and measurements exist. Avoid sharing identifiable old owner data on public GitHub, and obtain qualified assistance for solder/rework and testing as needed.

## Independent same-model diagnostic-replay control

[Actual April 2026 NUC11PAH owner's support thread](https://community.intel.com/t/intel-nuc11pah/138113): **power LED lit, storage activity LED lit, no HDMI picture**; eventually user reported remote login but HDMI remained unresolved. This is a **different** real device and different failure category than our target seller's *no LED at all*. We recorded the source chronology in [`public_case_replay.json`](public_case_replay.json) and assert HS correctly routes **solid LED/no video** to POST/display investigation rather than the no-power-adapter path. Neither repair is proven.

## Next purchase decision criterion

Before spending money, require seller evidence of CPU identity and actual board/adapter condition, a bounded repair budget, and a confirmed market resale range for *that exact CPU*. If conditional success value cannot cover actual parts, labor, marketplace fees, returns and the realistic probability of scrapping the board, reject the unit. This is opportunity screening, **not permission to order on behalf of the user**.
