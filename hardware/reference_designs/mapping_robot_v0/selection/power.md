# Power: battery pack and 5 V converter (Build 1, test 1)

Searched Ruten 2026-11-06 (read-only, about 20 requests): `3S 18650 電池組 保護板 12V`, `12V 鋰電池組 18650 3串 BMS`,
`11.1V 鋰電池組 18650 保護板 放電電流`, `12V 18650 鋰電池組 3S2P 保護板`, `12.6V 鋰電池組 18650 機器人`, `XL4015 5A 降壓模組`,
`5V 5A 降壓模組 UBEC`.

| Candidate | Listing | Sold | Why not / why |
|---|---|---|---|
| **3S2P 18650 pack, 6000 mAh, protection board, charger** | [22627027679167](https://www.ruten.com.tw/item/22627027679167/) NT$900 | 0 | **Chosen.** The only finished pack found whose seller publishes capacity, maximum discharge current (4 A), cut-off voltages and protections. 66 Wh against 25 Wh needed. |
| Same pack from other resellers | [22640776534275](https://www.ruten.com.tw/item/22640776534275/), [22629136856099](https://www.ruten.com.tw/item/22629136856099/) | 0 | Identical text from the same factory listing; one has an empty description. |
| 3C-certified 12 V 2550 mAh packs | [22641880464588](https://www.ruten.com.tw/item/22641880464588/) NT$528-916 | 0 | 28 Wh is enough, but nothing about the BMS or discharge current is published. |
| Bare 3S BMS boards (8 A) | e.g. [22534665268683](https://www.ruten.com.tw/item/22534665268683/) | 0 | Excluded: building a pack from cells is cell repacking. |
| **XL4015 5 A buck module** | [21519300644500](https://www.ruten.com.tw/item/21519300644500/) NT$40 | 235 | **Chosen.** Seller publishes input, output, current (4.5 A recommended), protections and size. |
| Holybro 5 A UBEC | [22640764586550](https://www.ruten.com.tw/item/22640764586550/) NT$1,069 | 0 | **Alternative.** Fixed 5.2 V output, so no risk of the 20 V factory setting, at 25 times the price. |

**Discharge requirement, recomputed with the chosen parts.** `REQUIREMENTS.md` asked for ≥ 4.5 A using a typical 1.5 A
stall per motor. The chosen motor stalls at 1 A, so the worst case is 2 x 1.0 A + (3.0 A x 5 V + 0.26 A x 5 V + 0.5 W) /
11.1 V / 0.85 = 2.0 + 1.78 = 3.8 A. The pack's 4 A passes with about 5% margin: thin, and a bench item. Both motors stalling
while the Pi draws its full rated supply is unlikely, but the firmware plan should limit motor current.

Safety notes for the bench checklist: the XL4015 ships set to about 20 V and must be set to 5.1 V before the Pi is
connected; it has no reverse-input protection; the pack's stated size is impossible for six cells and must be measured.
