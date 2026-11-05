# Supplier inquiry v2 — inspect-before-pay lot (DRAFT, NOT SENT)

Replaces nothing in `salvage_lot/channel_20261105/SUPPLIER_RFQ_ZH.md`; it is the same inquiry rewritten around what
`staged_economics.py` says matters. Nobody has been contacted. Sending is the owner's decision.

**Owner-only (never tell a supplier):** the walk-away numbers in `evidence/staged_economics.json`. Quoting your ceiling
turns it into the price. Ask for *their* price first and compare.

## 中文

您好，我在中壢做小規模的二手電腦整新（檢測、清除資料、換裝 RAM/SSD 後轉售），想詢問貴店是否有 **可合法對外出售** 的汰換桌機，數量 3–5 台即可先試單。

我們比較需要的條件：
1. **第 8 代 Intel Core i5 以上**的商用機（Dell OptiPlex／HP EliteDesk／Lenovo ThinkCentre 等，小型機或直立式皆可）；無 RAM、無硬碟可以接受。
2. **付款前可以逐台現場開機檢視**（接電、確認能進 BIOS／畫面），沒通過的不購買。
3. 單台價格（不要整批含稅統包），以及是否可開收據／發票、是否有所有權或處分權的書面（來源：企業汰換、租賃退回等）。
4. 硬碟／SSD 是否已移除或已清除資料；若仍有資料，是否同意我們依標準方式清除，並出具書面同意。
5. 若購買後發現與現場檢視不符，可否退換。

先詢價，不會直接下單。方便的話請提供型號、台數、CPU 世代、缺件狀況、單台價格與可到場看貨的時間。謝謝。

## English sense

Small refurbisher in Zhongli. Looking for 3–5 legally resellable retired desktops, ideally 8th-gen Core i5+ business machines (OptiPlex/EliteDesk/ThinkCentre), missing RAM/disk acceptable. We need: (1) per-unit on-site power-on inspection BEFORE payment, no obligation to buy units that fail; (2) per-unit prices, receipt/invoice, written title/disposal rights and origin (corporate/lease returns); (3) whether drives are removed/wiped, with written consent to sanitize any that hold data; (4) a return/exchange path if a unit differs from what was inspected. Inquiry only, not an order.

## Why these asks (each maps to a model input)
| Ask | Model effect (`staged_economics`) |
|---|---|
| Per-unit inspection before payment | `policy: inspect_each`: failed units are never bought. Raised the scrap-lot ceiling from NT$222 to NT$345 |
| 8th-gen business class | `resale_twd` basis; survives a NT$500/h labor valuation where the scrap class goes to NT$0 |
| Per-unit price + receipt | A lot price hides the per-unit number the ceiling is compared against; receipt is the `title_transfer_document` gate |
| Written data release | `rights:data_owner_release` gate; privacy law exposure for undeclared personal data |
| Return path | lowers `disposal_on_fail_twd` and tail risk |
