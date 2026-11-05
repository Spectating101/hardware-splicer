# HS salvage sourcing phase II — real supplier channels + batch decision

**Evidence snapshot:** 2026-11-05, Taiwan. **Physical outcome: NO salvage purchased, disassembled, electrically inspected or resold.** One *already-owned* Optiplex workstation was checked read-only as a tooling calibration control, not recovered merchandise.

## 1. A genuine reverse-supply-channel possibility, not permission to scavenge

- [神奇電腦 阿凱 (Zhongli)](https://www.ruten.com.tw/store/tao200639/) publicly advertises buying a **complete scrap desktop at NT$140**, a motherboard at NT$30, a laptop at NT$80; thousands of used-part listings are in its shop. **Those are rates paid by the recycler to the original owner, NOT prices at which we can buy junk from it.** No wholesale lot or sale quote obtained. Confirm lawful inventory resale authorization before any transfer.
- [登豐e倉庫 (Daxi)](https://www.ruten.com.tw/store/j3806316/) publicly offers many used computer components and repair services and asks buyers to confirm live stock before ordering. Not a confirmed junk-lot supplier.

Draft **not sent** for 3–5 computers: [SUPPLIER_RFQ_ZH.md](SUPPLIER_RFQ_ZH.md), requesting legal title, models, defects, photos, 3–5-unit selling price, inspection access and sanitized storage status.

Two real *individual product controls* were checked:
- [Acer TC-865 i5-8400/8GB/120GB/GT720](https://www.ruten.com.tw/item/22642901029861/) NT$2,800 + listed postage NT$200–250; seller reports it functions, but it was never independently checked and has not been acquired. A same-family [TC-865 at NT$6,300](https://tw.carousell.com/p/%E3%80%90%E8%89%BE%E7%88%BE%E5%B7%B4%E4%BA%8C%E6%89%8B%E3%80%91acer-aspire-tc-865-i5-8400-8g-1tb-gt1030-%E4%B8%BB%E6%A9%9F-%E5%A4%A7%E9%87%8C%E5%BA%97b9600-1462348803/) has **superior GT1030/extra hard drive and potentially different service**. Do not assume it establishes this unit's sale price.
- [Taoyuan Bade unidentified defective desktop DDR4](https://tw.carousell.com/%E9%9B%BB%E8%85%A6%E5%8F%8A%E7%A7%91%E6%8A%80%E7%94%A2%E5%93%81/%E9%9B%BB%E8%85%A6/%E6%95%85%E9%9A%9C%E5%93%81/q-6391/) NT$400, seller says it stops host booting and does not know whether it is 8GB. Not viable unverified inventory; reject.

## 2. Economic comparison of two distinct procurement paths

The scripts use only explicitly labeled assumptions: *an imagined* five-machine batch purchased at NT$250 per PC (this is **NOT** a seller quote), NT$600 lot transport, NT$2,200 per working rebuilt PC *hypothetical* sale, 10% fee, NT$500 successful labor, NT$150 repair parts/cleaning, NT$150 packaging/outbound, NT$250 warranty, NT$200 failed triage and NT$150 failed disposal. Unknown yield modeled from 25% to 80%.

| Hypothetical recovery rate | Successful PC profit | Failed PC loss | Expected profit / unit | Whole 5-PC batch expected |
|---|---:|---:|---:|---:|
| 25% | +NT$560 | -NT$720 | **-NT$400** | -NT$2,000 |
| 50% | +NT$560 | -NT$720 | **-NT$80** | -NT$400 |
| 65% | +NT$560 | -NT$720 | **+NT$112** | +NT$560 |
| 80% | +NT$560 | -NT$720 | **+NT$304** | +NT$1,520 |

At 65% **assumed** success, a bid of **NT$212 per computer** (NT$1,060 for 5) is the maximum to target **NT$150 expected contribution per acquired machine**. At 50%, the maximum is **NT$20**, making this unattractive without observed recovery yield. None of this supports buying at NT$140; that rate is a *recycler buyback*, not a sale quote.

The **already-working-claimed Acer** is a control: after assuming NT$225 inbound shipping, NT$400 check labor, NT$150 minor parts, NT$150 outward logistics, NT$250 warranty and 10% selling fees, **NT$5,000 speculative resale yields only +NT$525 IF it genuinely functions**. At assumed 80% success, expected contribution is **-NT$245**. NT$4,500 gives +NT$75 conditionally and -NT$605 EV. NT$6,300 gives +NT$1,695 conditionally and +NT$691 EV at 80%, but the same-family comparator has better hardware; that price is too weakly justified for a buy recommendation.

All prices are *asking values*; success rates are made-up risk parameters. Taxes, seller-funded returns beyond reserve, opportunity cost and holding time are not calibrated. The model does not approve purchases or acquisitions.

Run:

```bash
python3 examples/arbitrage_lab/salvage_lot/channel_20261105/channel_pilot.py
```

Outputs are frozen in [evidence/channel_decision.json](evidence/channel_decision.json) and [evidence/batch_sensitivity.csv](evidence/batch_sensitivity.csv). The code *actually invokes the existing* `Circuit-AI SalvageSplicePlanner` with **zero** inventoried real devices and records its `collect_more_evidence` response.

## 3. Live workstation instrumentation — actual runtime, not a manufactured salvage result

Rather than another pretend test, we ran [read_only_bench.py](read_only_bench.py) on the **existing authorized Optiplex** via the connected computer. It read **/proc/cpuinfo**, **/proc/meminfo** and read-only **lsblk** metadata, reporting generic i5-8500 CPU, six logical threads, ~31.15 GiB memory and two physical block devices (approx. 477 GiB and 1.86 TiB). Output [evidence/optiplex_control_readonly.json](evidence/optiplex_control_readonly.json) contains **NO disk serial, hostname, IP, MAC, mount path, personal files, unique hardware ID or owner's data**.

This proves the *read-only capture path operates on genuine running hardware*. It does **NOT** prove PSU/thermal health, RAM memtest, SMART, secure wipe, a salvage source, a repair, or a product sale. All such release gates remain explicitly false.

## 4. Decision, not a new series of meaningless CI checks

**Pursue a negotiated, legally saleable 3–5-PC batch only if** the supplier confirms models, conditions, title and a written selling quote, and the realistic recovery yield/ASP supports the target margin. Inspect before accepting. Reject speculative no-return single broken CPUs/RAM and no-resale PTT gifts. **No physical salvage product exists yet.**

Current action: an unsent, concrete Chinese request for a lawful commercial batch and testing terms; the platform can't represent it as sent. First actual proof would require a source device in hand with POST+memory/storage evidence and documented transfer.
