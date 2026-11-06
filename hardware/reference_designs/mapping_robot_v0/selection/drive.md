# Drive: motors, wheels, caster (Build 1, test 1)

Searched Ruten 2026-11-06 (read-only, 13 requests): `JGA25-370 編碼器 12V`, `GA25 霍爾編碼器 減速馬達`, `JGB37-520 編碼器`,
`Pololu 25D 編碼器` (no results), `JGA25-371`, `牛眼萬向輪 智能小車`.

| Candidate | Best listing | Sold | Why not / why |
|---|---|---|---|
| **JGA25-371 12 V 110 rpm, Hall encoder, set with 65 mm wheel, bracket, coupling** | [21205165759474](https://www.ruten.com.tw/item/21205165759474/) NT$550 | 2 | **Chosen.** The seller's description publishes speed options, the six-wire pinout, encoder supply and pulses, shaft and mass; Open Impulse publishes stall current and stall torque for the same motor family. |
| JGB37-520 12 V with encoder | [21817931267131](https://www.ruten.com.tw/item/21817931267131/) NT$670 | 87 | **Alternative.** Best-selling, also sold with wheel and bracket, but 37 mm and heavier, and no source found with stall current or stall torque (vendor pages give rated torque only for some ratios). |
| GA25-370 / 25GA-370 with Hall encoder | [21911282115070](https://www.ruten.com.tw/item/21911282115070/) NT$490 | 21 | Same motor class; no published stall data found. |
| JGA25-371 with 360-line optical encoder | [22635472113916](https://www.ruten.com.tw/item/22635472113916/) NT$485 | 0 | Higher resolution, but no published specs for its encoder. |

Variant: the seller offers 12 V at 1930, 915, 400, 250, 190, 110, 85, 50, 39 and 17 rpm. 110 rpm gives 102 rpm at the 11.1 V
pack (≥ 88 needed, `REQUIREMENTS.md`) with stall torque at least 0.38 N·m (≥ 0.25 needed). 85 rpm would give 79 rpm, too slow;
190 rpm would trade torque for speed the robot does not need. Open Impulse's own 126 rpm motor is not offered by this seller,
which is why stall torque is bracketed rather than read.

Open on the bench: encoder pulses (11 or 12 per motor revolution), gear ratio and so counts per wheel revolution, gearbox
length, wheel width and bore, caster height and mount.

Caster: [22424722682045](https://www.ruten.com.tw/item/22424722682045/) 25 mm ball variant, NT$25, 50 sold. Only the ball
diameter is published; height is set by a printed spacer in the chassis plan.
