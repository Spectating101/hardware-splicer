# HS Salvage-to-Working-Product — Taiwan Acquisition Pilot, 2026-11-05

## Phase II (2026-11-05): verified supplier channel and live workstation probe

[**Real Zhongli commercial recycler/supplier channel screen**](channel_20261105/README.md) now checks a published NT$140 complete-PC **scrap BUYBACK** (not a supply price) and uses a working-claimed Acer TC-865 as a market control. Five-PC batch risk sensitivity and a qualified Chinese supplier inquiry are preserved. We also ran a **read-only probe of an already-owned Optiplex** as a calibration of real-hardware collection, explicitly not a salvaged product. No supplier has offered or transferred stock. This is the current actionable work.



**Purpose:** identify a physically obtainable, lawfully transferable **junk electronics lot** and decide which COMPLETE FUNCTIONAL PRODUCT is worth building or recovering, considering profitable resale versus part-out. Do not call a software demonstration a recovered physical product.

**Current result:** **zero legally/commercially obtained lots, zero observed functioning parts, zero verified profitable products.** Executed on authorized Optiplex; native HS Circuit-AI `SalvageSplicePlanner` invoked with the true *empty owned/tested inventory* and produced verdict `collect_more_evidence`, zero build candidates. This is correct; don't use description-only imaginary components or the planner's nominal USD product value estimates to claim a sale.

## 1. Source ownership / resale restrictions change the opportunity set

| Lead | Source / date | Evidence of components | Right to commercially resell? | Decision |
|---|---|---|---|---|
| [Hsinchu owner giveaway](https://www.ptt.cc/bbs/give/M.1784598671.A.A64.html) | PTT Give, July 21 2026 | *Seller reports* chassis, motherboard, PSU; GPU sold, CPU/RAM/storage uncertain. Historical listing, availability unknown. | **NO** under PTT Give resale rules | Noncommercial reuse demonstration only, not for resale |
| [Sanchong giveaway](https://www.ptt.cc/bbs/give/M.1793295736.A.E7B.html) | PTT Give, Oct 30 2026, deadline ~Nov 5 | "Computer odds and ends," no inventory, uncertain condition, poster explicitly **禁轉售** | **NO** | Reject from commercial sourcing |
| [Taoyuan damaged i5-7400+Z170M](https://www.ptt.cc/bbs/HardwareSale/M.1792988675.A.1FC.html) | PTT HardwareSale, Oct 26 2026 | CPU condition unknown; seller suspects moisture damage on motherboard. Asking NT$600. | Ordinary sale could transfer title **if actually purchased**, but none acquired | Reject: worst known material margin |
| Directly transferred retired complete desktop | **HYPOTHETICAL** (no identified owner/listing!) | Potential i5/DDR4/SSD only if physically transferred and independently verified | **UNCONFIRMED** | Candidate for outreach, never an available lot |

The [PTT Give board's July 27 2026 v1.45 terms](https://www.ptt.cc/bbs/give/M.1785164326.A.BD3.html) prohibit reselling obtained gifts for profit. Do not harvest commercial stock from this venue. Municipal/authorized recycler stock is also NOT open-access public property. A direct owner-signed transfer permitting resale, or lawful paid scrap lot, is the relevant route. Consent must explicitly cover commercial disposition, data wiping and safe recycling of leftovers.

## 2. Existing HS stack, used instead of a new imaginary recycler engine

Run from repo root:

```bash
python3 examples/arbitrage_lab/salvage_lot/salvage_pilot.py
```

The pilot invokes **existing** `apps/circuit-ai/src/intelligence/salvage_splice_planner.py` (non-LLM) with zero real assets. `salvage_decision.json` records the planner's `collect_more_evidence` verdict, explicitly distinguishing *reported* and *verified* components.

The pilot then evaluates **actual listing data** and **strictly labeled hypothetical product routes** under Taiwan-dollar costs; outputs: [salvage_decision.json](evidence/salvage_decision.json) and [route_sensitivity.csv](evidence/route_sensitivity.csv). The expected profits use arbitrarily chosen 25/50/75% recovery probabilities to illustrate risk, not empirical yield. It does not grant repair authority or product release.

### Comparative economics — when the owner DONATES a COMPLETE machine directly with commercial resale permission

This is a **counterfactual** example, not an identified stock lead. Resale benchmark: [i5-7500 system with 4GB/120GB SSD asked NT$2,200 in Aug 2026](https://www.ptt.cc/bbs/HardwareSale/M.1788169513.A.0E3.html); CPU [i5-7400](https://www.ruten.com.tw/search/intel%2Bi5-7400/) asks NT$450-600; [DDR4 2666 8GB](https://www.ptt.cc/bbs/HardwareSale/M.1792395575.A.D74.html) asks NT$850; SSD 256 GB NT$700 is a **different-interface proxy** from a previous marketplace case, not a validated same-model resale comp; a complete [6-bay i3-8100 NAS](https://www.ptt.cc/bbs/HardwareSale/M.1788427462.A.B3E.html) asks NT$2,600 but has DIFFERENT hardware.

| Recovered end product | Conditional contribution **after modeled parts/labor/transport/fees/warranty**, NT$ | Failed lot loss, NT$ | EV at *assumed* 50% yield |
|---|---:|---:|---:|
| Tested/refurbished complete desktop sold at NT$2,200 | **+630** | -600 | **+15** |
| Tested CPU + DDR4 + SSD sold separately (requires all three working!) | +495 | -600 | -53 |
| Fully configured NAS from an old machine, sold at unverified NT$2,600 | **-160** | -600 | -380 |

The same model at **assumed 75%** successful recovery produces expected +NT$323 on a complete desktop. All are unrealized, before seller-specific taxes and the opportunity cost of scouting. Selling a new NAS as if it commands a premium is **not** justified without buyers and functional drive testing. If the donor unit lacks CPU/RAM/SSD, those routes cannot be executed without extra procurement.

**Real paid Taoyuan damaged lot:** CPU-only market ask ~NT$500. Even if the CPU tests good, modeled net **-NT$720**, due to NT$600 acquisition, NT$200 transport, NT$200 diagnosis, packaging, fees and returns. A 50% recovery assumption yields **-NT$910**. Buy neither just because the label says "junk."

## 3. Real routes to stock, not scavenging from someone else's bin

Two **verified existing organizations**, with NO contact made and NO promised free stock:

- **大川實業中壢桃園電腦回收站** — [桃園市中壢區新中北路217號](https://recycle.tyoem.gov.tw/G_Treasure_Map.aspx); phone **0985-229-558**. Ask whether *commercially transferable* obsolete computers, motors or electronics are sold as a separately quoted scrap lot, and whether an authorized workshop can purchase them. Never assume collection bins are open.
- **木匠的家修惜站** — [桃園市中壢區中北路二段387-1號](https://recycle.tyoem.gov.tw/G_repair_station.aspx); phone **(03)468-3836**. Public reuse/repair station, NOT verified source of discarded electronic parts. Ask about public repair collaboration or lawful sales only.

For owner-direct pickups, use [`owner_transfer_checklist.md`](owner_transfer_checklist.md). Obtain documented explicit consent before transporting anything. For institutional discarded equipment, obtain official disposal/transfer approvals; don't work around government or university asset rules. Keep owner identities, account details, machine serials and storage images **outside public GitHub**.

## 4. Actual complete-product acceptance, not green CI theater

A legally obtained complete PC should have a documentable acceptance sequence: owner rights → photo/asset inventory → qualified unplugged inspection → known-good manufacturer-compatible PSU → real POST/CPU identity → RAM memtest → SSD SMART and secure data wipe → stress thermals/fan → functional I/O and network → customer listing/warranty disclosure. A working NIC alone does not make a saleable edge router or NAS. No failed unit should be powered if there is water ingress, damaged PSU, exposed mains or swollen battery.

An **actual HS experimental product** for this phase is a fully working, verified refurbished desktop, not the PC shell or motherboard. The alternative products HS may investigate after physically seeing components are computer/NAS, robotic motion equipment (requires salvaged motors/driver), or low-voltage test machinery. Nothing with missing motors/actuators should be passed off as an invented robot.

**Next physical dependency:** acquire a documented transferable lot. This pilot can prioritize leads and refuse bad cases; it cannot discover circuit truth or legal transfer by pretending an item was thrown away.
