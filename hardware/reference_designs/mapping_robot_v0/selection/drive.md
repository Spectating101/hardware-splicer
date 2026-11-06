# Drive: motors, wheels, caster (Build 1, test 1)

Searched Ruten 2026-11-06 (read-only, 13 requests): `JGA25-370 編碼器 12V`, `GA25 霍爾編碼器 減速馬達`, `JGB37-520 編碼器`,
`Pololu 25D 編碼器` (no results), `JGA25-371`, `牛眼萬向輪 智能小車`.

| Candidate | Best listing | Sold | Why not / why |
|---|---|---|---|
| **JGA25-371 12 V 110 rpm, Hall encoder, set with 65 mm wheel, bracket, coupling** | [21205165759474](https://www.ruten.com.tw/item/21205165759474/) NT$550 | 2 | **Chosen.** The seller's description publishes speed options, the six-wire pinout, encoder supply and pulses, shaft and mass. Its speed list matches Precision Microdrives' NFP-JGA25-370-1285 (12 V, 8,500 rpm motor) ratio for ratio, and NFP publishes no-load, rated and stall figures for each ratio. |
| JGB37-520 12 V with encoder | [21817931267131](https://www.ruten.com.tw/item/21817931267131/) NT$670 | 87 | **Alternative.** Best-selling, also sold with wheel and bracket, but 37 mm and heavier, and no source found with stall current or stall torque (vendor pages give rated torque only for some ratios). |
| GA25-370 / 25GA-370 with Hall encoder | [21911282115070](https://www.ruten.com.tw/item/21911282115070/) NT$490 | 21 | Same motor class; no published stall data found. |
| JGA25-371 with 360-line optical encoder | [22635472113916](https://www.ruten.com.tw/item/22635472113916/) NT$485 | 0 | Higher resolution, but no published specs for its encoder. |

Variant: the seller offers 12 V at 1930, 915, 400, 250, 190, 110, 85, 50, 39 and 17 rpm. NFP's 8,500 rpm 12 V motor gives
1931, 915, 399, 242, 188, 108, 82, 50, 37 and 17 rpm on its gearboxes, so the seller's 110 rpm part is taken as NFP's 78:1
row: 108 rpm no-load, 0.1 A no-load, 0.4 A at 2 kg·cm, 2.6 A and 8.6 kg·cm at stall. At the pack's 9.9 V minimum that is
89 rpm against 88 needed (speed margin 1.52), and within a 1.2 A driver limit the motor gives 0.37 N·m against 0.31 N·m for a
10 mm threshold. 85 rpm would be too slow.

Correction (2026-11-06, final review): an earlier version took stall figures from Open Impulse's JGA25-371 pages. That is a
4,300 rpm winding (977 rpm x 4.4, 126 rpm x 34), not the seller's 8,500 rpm one, so its 1 A stall current understated this
motor by a factor of 2.6. Open Impulse is now cited only for its encoder count.

Open on the bench: encoder pulses (11 or 12 per motor revolution), gear ratio (1:78 inferred) and so counts per wheel revolution, gearbox
length, wheel width and bore, caster height and mount.

Caster: [22424722682045](https://www.ruten.com.tw/item/22424722682045/) 25 mm ball variant, NT$25, 50 sold. Only the ball
diameter is published; height is set by a printed spacer in the chassis plan.
