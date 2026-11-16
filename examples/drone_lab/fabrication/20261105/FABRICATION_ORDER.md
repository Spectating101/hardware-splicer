# HS65 physical prototype — fabrication request (2026-11-05)

**Purpose:** One experimental, unpowered, unassembled 65 mm microdrone airframe + removable battery-cradle fit specimen. This is a dimensional/print-process trial, **not** a flight-ready drone. It must not be sold or certified as an airworthy UAV.

## Quote actually calculated

Provider: 3DEX / 三德列印 (Taiwan) — https://3dex.tw/quote/

At 2026-11-05, their browser-side quotation engine processed BOTH original STL files as a single quote. Parameters selected: **FDM PETG, light grey (超淺灰), 50% infill, quantity 1 each, default 1.2 mm wall and ±0.2 mm tolerance, no finish, no marketing photo consent**.

| Part | Model envelope | Source STL solid volume | 3DEX estimate | Before-tax price |
|---|---:|---:|---:|---:|
| Original HS65 ducted frame | 82.962 × 82.962 × 16 mm | 7.1164 cm³ | 10.0 g | NT$327 |
| Removable battery cradle | 20.8 × 23 × 8.7 mm | 0.8657 cm³ | 1.1 g | NT$174 |

**Browser quote:** NT$501 before tax + NT$25 tax = **NT$526**, default postal delivery selected. The webpage estimated ~2 working days production, excluding delivery. This is a live *estimate*, not an accepted formal order or paid invoice. The files were processed locally in the quote browser; they were **not sent to the vendor**. A full-page screenshot is `3dex_quote_petg_50pct.png`.

For context, our **solid geometric** PETG estimates at assumed density 1.27 g/cm³ are 9.04 g (frame) + 1.10 g (cradle). A vendor's 50% infill, shells/supports, actual PETG density and printer settings may produce a different *measured* mass. Commercial BETAFPV Air65 PP frame: 2.67 g (manufacturer claim), **not a like-for-like material comparison**. https://betafpv.com/collections/brushless-frame/products/air65-brushless-whoop-frame

## Fabrication instructions / 給代印廠商

請協助以原始 STL 檔進行 PETG FDM **實體功能打樣**，各 1 件：
- `aerial_frame.stl`：四旋翼保護框、一體成型，外框約 83 × 83 × 16 mm。
- `battery_cradle.stl`：獨立電池槽，約 20.8 × 23 × 8.7 mm。
- 顏色：超淺灰（或一般淺灰），填充率 50%，無噴漆／拋光。
- **不得自動縮放**模型。請確認 STL 的單位為 mm、兩件分開列印、平面朝下。
- 關鍵位置：每組馬達 **3 × Ø1.6 mm 螺絲孔，6.6 mm PCD**；飛控孔位四孔旋轉配置 **26 × 26 mm**，孔徑 Ø2.0 mm；31 mm 槳葉需要足夠保護框間隙。小孔 FDM 成形可能受 0.4 mm 噴嘴／擠出補償影響。**請先人工審圖確認能否實現孔位／細柱**，若不行請回報方案與另行報價，勿默默改圖。
- 框架側壁 nominal 1.2 mm，16 mm 高框內含細柱；請留意細柱列印與拆支撐時會斷裂的風險。不要在框內增加無法移除的支撐。請先確認擺放方式與支撐策略。
- 原尺寸／層高（若需建議可先試 0.12–0.16 mm）與實際公差請標註；模型最初指定 FDM、無實體校正。不要假設公差一定可達。
- 若可行，請附列印完成照片、兩件**實際重量（g）**、使用材料、噴嘴尺寸、層高與有無支撐；若無法提供，請在報價前說明。
- 這是未通電的尺寸測試件，不需焊接、安裝電子設備或裝機試飛。

## Independent mesh audit (not a slicer or print test)

Both as-exported binary STL files have exact byte counts consistent with triangle records, closed 2-manifold triangulation (every undirected triangle edge has valence exactly 2, with vertices rounded to 0.0001 mm); frame has 29,980 triangles, cradle 92. That is **not** evidence of support-free slicing, dimensional accuracy, impact resistance or flight performance.

**Important fit risks**:
1. M1.4 motor screws through nominal Ø1.6 mm printed holes with vendor ±0.2 mm generic tolerance could require cleanup; do not post-drill before documenting actual printed size.
2. The battery channel nominal 12.4 × 7.5 mm internal area is from an unmeasured proposed pack envelope; actual pack fit requires calipers and safe handling.
3. PLA/PETG FDM parts differ mechanically from thin injection-molded polypropylene. Do not assume crashworthiness or adequate mass.
4. Frame + cradle nominal 10.14 g at material density 1.27; this is already a substantial mass penalty against a 2.67 g commercial PP frame.

## Acceptance after the parts arrive

Only a **delivered printed part and measurements** can move the physical gate. Save:
- Full-package photos and both pieces front/side, ideally with printed ruler for scale.
- Actual measured mass of frame and cradle separately (0.01 g scale if available), material and slicing settings.
- Calipers: frame bounding box, 26 mm FC hole pitch, motor 6.6 mm PCD/hole diameter, duct clearance, battery channel dimensions, compared with intended values and uncertainty.
- Unpowered mechanical fit with **real, specified** 0702 motors, FC and battery (if sourced). Photos of interference or broken pillars count as results; don't alter a prototype silently.
- Record failure/success before updating CAD. No live battery, motors, propellers or flight on this first fabrication gate.

## Order status

**NOT SENT / NOT PAID / NOT IN PRODUCTION.** Checkout requires a recipient name, mobile number, email, tax-invoice preference, Taiwan delivery address and payment. None is embedded in this public repo. Any additional vendor review or shipping surcharge must be confirmed before payment.
