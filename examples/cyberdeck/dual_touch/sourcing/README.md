# Taiwan component sourcing — HS dual-touch cyberdeck

**Observed November 6, 2026. Read-only supplier research, no order, no quotation, no stock reservation.**

This sourcing report is for **PR #292's dual Waveshare ESP32-S3-Touch-LCD-4.3 (touch SKU 25948)** and **not** PR #291's Raspberry Pi 5 pricing exercise, another ESP32 4.3B/4.3C version, or the Waveshare **non-touch SKU 30493**.

The original HS `evidence/native_mecha/budget.json` is preserved at **NT$2,965** (largely hypothetical). This is a **new, source-audited purchasing exercise**; its higher estimate is **not** a cost escalation from an actually quoted original BOM.

## Buyer-facing source candidates

| Component | Taiwanese reference / original supplier | Unit price | Availability / qualification |
| --- | --- | ---: | --- |
| 2× Waveshare ESP32-S3-Touch-LCD-4.3 capacitive touch **25948** | [iCShop SKU 368031700131](https://www.icshop.com.tw/products/368031700131) | NT$1,250 each | **SOLD OUT** according to page; `NT$2,500` is an unavailable reference, not orderable. iCShop marketing summary conflicts on flash memory; Waveshare manufacturer specifies N16R8. |
| Exact touch module alternative | [Ruten mixed-variant listing](https://www.ruten.com.tw/item/22629113316589/) | NT$1,371–1,650 **across variants** | Lists touch **25948** and non-touch **30493**. Use **NT$1,650 as conservative price envelope**, NOT a confirmed SKU-specific touch price or in-stock quotation. Contact seller / select variant to get exact total. |
| Waveshare original manufacturer | [Touch SKU25948 product page](https://www.waveshare.com/esp32-s3-touch-lcd-4.3.htm?sku=25948) | US$32.99 / board | Currency **USD**; import shipping, FX rate, tax and Taiwan delivery not quoted. Supplied kit normally contains **2× HY2.0 2P 10 cm cables per board**, plus other cables and standoffs. Ask seller to confirm full kit is supplied. |
| 2× 0.5 m USB-A to USB-C cable, 3A | [UGREEN/Yahoo](https://tw.buy.yahoo.com/gdsale/%E7%B6%A0%E8%81%AF-USB-C-Type-C%E5%BF%AB%E5%85%85%E5%82%B3%E8%BC%B8%E7%B7%9A-%E9%BB%91%E8%89%B2-%E5%8D%87%E7%B4%9A%E7%89%88-0-5%E5%85%AC%E5%B0%BA-9191445.html) | NT$99 each | Asking price; cart and delivery not verified. |
| Bench 5 V dual-output adapter | [Linktech AC-D11](https://www.linktech.tw/product/ac-d11-%E9%9B%99%E5%AD%94-20w-%E5%85%85%E9%9B%BB%E5%99%A8-4711075641475) | NT$249 | Both ports share **5 V 3 A max**. The two boards are **4.5 W nominal together** per manufacturer, but peak draw, startup and cable voltage drop not measured. |
| PETG printed two-shell set | [萬彩 printed PETG pricing](https://www.wancai-3d.com/fabrication-services-1) | NT$1.40/g; minimum NT$150/order | **Scenario only:** 150 g total for two shells = NT$210 **if actual sliced mass is 150 g**. The existing STLs have not been slicer-quoted for grams, support, time, geometry or reprints. |
| M2 mounting accessories | [iCShop screws/nuts category](https://www.icshop.com.tw/categories/screws-nuts) | NT$25 allowance | Category-level screws/nuts price; mounting-hole dimensions still not verified, not a final fastener spec. |
| Heatshrink | [Double Sun 2.0 mm pack](https://double-sun.com.tw/product-detail/1114) | NT$20 / pack | Public asking price; actual connector and cable insulation diameter to be verified. |
| 2 mm metal hinge pin ≈120 mm | [Shopee Taiwan rod search](https://shopee.tw/search?keyword=%E5%AF%A6%E5%BF%83%E5%9C%93%E6%A3%92&page=0) | NT$45 **allowance** | Search has 2 mm rods from around NT$30, but specific **2 mm × ≥120 mm stainless** checkout not confirmed. Require cut/retention, tolerances, no exposed sharp edges. |
| Included RS485 pair wiring / extra ground | [Waveshare FAQ](https://docs.waveshare.com/ESP32-S3-Touch-LCD-4.3/FAQ) | Included RS485 cable NT$0 conditional + NT$50 allowance for extra conductor/strain relief | **RS485 uses HY2.0 2P**, distinct from **PH2.0 battery connector**. Verify seller kit, common reference, A/B polarity and bending fatigue. |

## Recalculated scenarios (TWD)

| Scenario | Hardware cost estimate | What it does and does not prove |
| --- | ---: | --- |
| **ONE board bench** | **NT$2,058** | One not-yet-confirmed NT$1,650 touch board + NT$99 USB cable + NT$249 supply + NT$60 shipping reserve. No hinge/second screen. |
| **TWO boards bench** | **NT$3,827** | Two touch boards at conservative Ruten upper-bound assumption, two USB cables, bench adapter, included HY2.0 cables if seller includes full kit, NT$80 freight reserve. Not a functioning SSH application. |
| **Folding two-board test article** | **NT$4,277** | Above plus 150g PETG estimate (NT$210), 2 mm pin (NT$45), extra cable/ground (NT$50), fasteners (NT$25), heatshrink (NT$20), and a larger NT$180 combined freight allowance. Not measured assembled Z, battery or fit. |
| **iCShop reference ONLY** | **NT$3,477** | Same two-screen folding scenario but uses **sold-out NT$1,250** board reference, **not a currently purchasable cost**. |

**Printing cross-check from HS's own CAD:** `design_evidence.json` records a 32.443 cm³ base and 32.620 cm³ lid, **65.063 cm³ total closed-mesh volume**. Using the [Polymaker PolyLite PETG technical reference](https://wiki.polymaker.com/polymaker-products/more-about-our-products/documents/technical-data-sheets/petg-pet/polylite-tm-petg) at 1.25 g/cm³, an ideal **fully solid equivalent** would be about **81.3 g**, before slicer-specific support/raft/purge and fabrication conditions. The **150 g** budget input is therefore a conservative *scenario allowance*, **not** actual sliced grams or an offer from a printer. Have the supplier slice the two exact STLs before treating NT$210 as a real quote.

[Traditional Chinese supplier RFQ, **not sent**](SUPPLIER_RFQ_ZH.md) asks for exact touch SKU25948, 2-unit stock, included HY2.0 cables, shipping to Zhongli and a printer quote after shell fit corrections.

Each value can be recomputed via `PYTHONPATH=src python3 scripts/hs_taiwan_sourcing_budget.py`. The machine-readable observations are in `taiwan_snapshot_20261106.json`. **All estimates exclude rechargeable batteries, BMS/charging integration, engineering labor, physical-test failures, shell reprints, shipping uncertainty above reserves, and compliance.** No supplier has issued an exact delivered quote.

## Practical procurement gate / next step

**First test only needs one exact touch board, an appropriate known-safe USB supply and cable**. Avoid buying the second board, fabricated shells or Li-ion cells before on-bench software/RS485/SSH security investigation. Required actual purchase check (not performed): select **25948 touch** in Ruten, verify **2 units** available and the final checkout amount; separately request iCShop restock/ETA or Waveshare delivered Taiwan quote. Manufacturer includes HY2.0 2P male-tail cables, so do not pay twice unless additional approved flexible hinge wiring is actually necessary.

Physical build/operational release remains denied by canonical HS `MachineProject`: six blockers, no powered device, no authenticated SSH or mechanical tolerance proof. **This file neither authorizes ordering nor claims an actual supplier quote.**
