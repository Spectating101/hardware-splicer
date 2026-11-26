# Where salvage donors come from in Taiwan, and what they cost (2026-11-26)

Prices are Ruten (露天) listings read through its public search on 2026-11-26: the lowest-priced matches, each unopened
and untested, so some will be dead on arrival. Shopee blocks scripts and was not read. Each Ruten seller ships
separately (convenience-store pickup), which is not included below.

## Donors: what they give and what they cost

| Donor (search term) | What it gives a build | Price seen |
|---|---|---|
| Broken phone that still powers up (二手手機 螢幕破, 故障機) | Camera, Wi-Fi, battery, charger, a whole computer | NT$100-250; a phone confirmed to boot NT$700 |
| Broken robot vacuum (掃地機器人 二手 / 零件機) | Two drive wheels with gearmotors and springs, bumpers, cliff sensors, battery bay, chassis; Roomba 500/600 accept serial commands (iRobot Open Interface) | NT$230-800; Roomba 571 "powers up, won't run" NT$800 |
| Broken RC toy (遙控車 故障) | Small gearmotors, wheels or tracks, chassis | NT$100-200 broken; NT$400-540 for a new mini tracked tank |
| Dead laptop battery packs (筆電電池 拆機) | 18650 cells (test and sort: some are dead or weak) | NT$99-128 per lot |
| Neck fans and similar (18650 鋰電池 拆機) | One 18650 cell plus a small motor | NT$56 |
| Hoverboard (平衡車 故障) | Two hub motors, 36 V pack, frame (big rovers) | NT$2,000 (one listing) |

New parts a salvage build still needs are cheap: ESP32-C3 board NT$73, DRV8833 dual motor driver NT$14-22, two-cell
18650 holder NT$4, 2S protection board NT$12-18, TP5100 two-cell charger NT$25.

## The rover, salvaged, against the US$30-50 Blinky Bot (hs_bom_check, rover ledger steps 33-34)

| Variant | Total | New parts | Replaces (new-part value) |
|---|---|---|---|
| A: broken phone + broken toy car + ESP32-C3 + DRV8833 + laptop 18650 cells | NT$561 (US$17) | NT$162 | about US$77 |
| B: broken phone + broken Roomba 571 driven over its serial port + ESP32-C3 + laptop cells | NT$1,139 (US$35) | NT$140 | about US$170 |
| Blinky Bot, new | about NT$1,000-1,600 | | |
| HS-ROVER-A, all new parts | NT$8,670 (US$263) | | |

Both salvage variants pass the check under the Blinky Bot's price, and the new-parts rover does not. What is not in the
numbers: shipping from several Ruten sellers; donors that turn out dead (buy a spare phone); the phone app for
streaming (an old Android such as the Note 3 needs an app that still installs on it); and assembly hours, which decide
whether this is a product or only a demonstration. None of it has been bought or tested.

## Free and near-free sources (not priced)

University dorm move-outs (YZU Male Dorm 1 clears at the end of January 2027), giveaway groups (送物/贈物),
neighbourhood recycling points and scrap dealers selling by weight, and repair shops' unclaimed devices. These need a
person on site; they are leads, not quotes.
