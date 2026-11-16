# build_vs_buy: is building (or splicing) cheaper than buying the finished thing?

The mission doc asks HS to compare build vs buy vs salvage before choosing a route. This directory answers that for the
two proving products already in flight: the printed 65 mm whoop from PR #276 and a Pi 5 cyberdeck (the cyberdeck lane
of PRs #111/#165/#183). `priced_bom.py` prices each parts-list line from Ruten listings (read-only, ~1 req/s, 104 requests
for the final run) and compares against finished products doing the same job.

**Boundary:** Ruten asking prices on 2026-11-06. Each cheapest listing is recorded in `evidence/` with its URL so a person can
open it. Nothing was ordered or contacted. The shell print price for the cyberdeck and its small-parts allowance are assumptions,
labelled as such.

## Result

| | Build from new parts: cheapest listing per line / p25 | Finished equivalent: cheapest real listing |
|---|---|---|
| **65 mm analog whoop** (radio and charger excluded from both sides) | NT$4,036 / **NT$6,591** | Happymodel Mobula6 **NT$2,950** (with 4 batteries), BETAFPV Air65 NT$4,944, Meteor65 Pro NT$5,370 |
| **Pi 5 cyberdeck** (7" touch, mini keyboard, 2x18650 UPS, printed shell) | NT$6,505 / **NT$8,057** | ClockworkPi uConsole kit **NT$7,600-7,800** (one listing shows 8 sold), used ThinkPad i5 from NT$3,200 (p25 NT$5,668) |
| **Donor for the deck: Advantech AIM8I rugged tablet** (PR #111) | n/a | **NT$2,000** (3 listings, one seller, sold "as write-off parts") |

**Building from new parts loses on cost for both products.** Even at the cheapest listing on every line, the whoop costs more
than a finished Mobula6 that includes batteries, and the Pi 5 deck costs about what a finished uConsole costs and more than a
used laptop that does more.

**Where splicing does create value: the donor route.** The AIM8I at ~NT$2,000 already contains an 8" 1920x1200 touch panel,
battery, compute and an IP65 enclosure. The same functions bought new for the Pi deck cost about NT$6,700 at p25 (screen 1,533 +
Pi 5 2,639 + UPS 1,411 + cells 240 + shell 900). That NT$4,700 of integrated hardware is the case for PR #111's FieldDeck.
Two caveats: the Atom x5-Z8350 / 2 GB is much weaker than a Pi 5, and all three listings are "write-off parts" from one seller,
so donor yield and battery health are unknown: that is exactly what the `pc_refurb` casefile gates (PR #289) are for.

**So HS's value is not cheaper parts; it is (a) donor integration, where a retired device supplies most of the BOM, and (b)
function the market does not sell** (PR #111's isolated RS-485/CAN field I/O, a payload-carrying or sensor whoop). A plain
whoop or a plain Pi deck is a commodity you should buy.

## FieldDeck (PR #111) priced end to end

`fielddeck_aim8i.json` prices the #111 splice: used AIM8I + keyboard dock + USB 3.0 Gigabit Ethernet + hub, plus the field
I/O (2x isolated RS-485, CAN, isolated DI/DO). The field I/O is a **shared** line: a laptop or a Toughbook bought instead
also needs those adapters, so it is left out of the build-vs-buy difference and added back for cost of goods. Retail USB
adapters stand in for the unbuilt FieldIO board. Ruten asking prices on 2026-11-06, 61 requests.

| p25 unless noted | NT$ |
|---|---|
| AIM8I donor (3 listings, one seller, "write-off parts") | 2,000 |
| Dock-only parts: keyboard 615, GbE 343, hub 348, adapter 350\*, printed dock 1,200\*, dock connector 300\* | 3,156 |
| Field I/O: RS-485 985 x2, CAN 531, DI/DO 751 | 3,252 |
| **Parts per unit** | **8,408** |
| #111's own overheads, unchanged (shipping, 80% donor yield, rework, warranty, labour; its 6,633 minus donor and the 2,500) | 2,133 |
| **Cost of goods** (#111 modelled 6,633 by assuming the dock and I/O cost 2,500) | **10,541** |

\* assumed, labelled in the product file; no dock design, connector part or print quote exists.

At the NT$12,900 target that is an **18% gross margin, against #111's 45% floor** (40% if every line hit its cheapest
listing; 10% at median). The 2,500 assumption was low by about 2.6x.

**What a field engineer can buy instead** (adding the same field I/O, NT$3,252, to each):

| Route | Unit | With field I/O |
|---|---|---|
| Used Panasonic Toughpad FZ-M1, 7" rugged Windows tablet, i5 (3 sold at this price) | 7,500 | **10,752** |
| Used Toughbook CF-31, rugged, i5, native RS-232 and Ethernet (2 domestic listings) | 6,500 | **9,752** |
| Used business laptop, not rugged | 5,668 | **8,920** |
| FieldDeck at #111's target price (Atom x5-Z8350, 2 GB) | 12,900 | already included |

So FieldDeck would sell above what a buyer pays to assemble the same function from used rugged hardware that has a faster
CPU. The donor saving that beats a Pi deck (above) does not beat the used rugged market, which is FieldDeck's real
competitor. New IP65 tablets (p25 NT$13,040, cheapest 8" Android units about NT$7,000) bound it from above.

What would have to be true for FieldDeck to clear 45%: dock plus field I/O at about NT$2,500 per unit (a custom FieldIO
PCB, not retail adapters, which needs its own NRE quote), *and* buyers paying NT$12,900 for one integrated unit over a
used Toughpad plus adapters at about NT$10,750. Neither is evidenced. Thin spots: the Toughbook and Toughpad prices rest on
two to three domestic listings (most CF-19/CF-54/CF-20 listings are cross-border at NT$12,000-19,000); the CAN line
includes non-isolated boards; asking prices only.

## Compatibility checked against published specs (not against parts in hand)

Drone (PR #276 build):
* **FC mounting:** the board sold now is BETAFPV's revised Matrix 1S "5IN1 II" (12 A ESC; Ruten titles say 12A / O4). Retailers list
  it as **26x26 mm, 3-point mounting**; the printed frame is the designer's `65mm_26x26_whoop`. Likely compatible (3 of the 4 holes),
  **unconfirmed** until the hole positions are checked on BETAFPV's drawing or the board. The original Matrix 1S is listed at 25.5 mm
  by one retailer and was built on this frame by its designer.
* **Motors:** the cheapest 0702 listings are Happymodel SE0702 (1 mm shaft, 23000-26000 KV), not the RCinPower GTS V3 0702 27000 KV the
  source build used; same size, a labelled substitute. Motor max 4.2 A vs the board's ESC rating: OK. Motor connector type vs the
  board's plug: **unconfirmed** (may need soldering).
* **Props:** Gemfan 1210-2 31 mm is made for 1 mm shafts; the 0702 motors have 1 mm shafts: OK.
* **Camera:** BETAFPV C03, 3-5.5 V, JST-0.8, standard on BETAFPV whoops: likely OK.

Cyberdeck:
* **Power is the binding constraint.** Raspberry Pi 5 asks for 5 V/5 A; with anything less (most 18650 UPS boards) it limits *all*
  USB ports together to 600 mA (Raspberry Pi whitepaper on Pi 5 USB-PD). A USB-powered 7" touch panel plus a keyboard dongle can
  exceed that. Either feed the panel from the UPS 5 V rail directly, use the official DSI touch display (powered from the Pi's 5 V
  header, not USB), or buy a UPS that names Pi 5 support. The priced UPS line now only accepts boards that name Pi 5; the cheapest Pi 4
  boards (NT$262-330) were excluded because they cannot feed a Pi 5 plus a USB screen.
* **Pi 5 4 GB price is thin:** only one listing passed the filter (NT$2,639, a 4GB/8GB variant listing). Treat that line as approximate.

## Run
```bash
python3 examples/arbitrage_lab/build_vs_buy/priced_bom.py examples/arbitrage_lab/build_vs_buy/drone_whoop65.json
python3 examples/arbitrage_lab/build_vs_buy/priced_bom.py examples/arbitrage_lab/build_vs_buy/cyberdeck_pi5.json
python3 examples/arbitrage_lab/build_vs_buy/priced_bom.py examples/arbitrage_lab/build_vs_buy/fielddeck_aim8i.json
python3 -m pytest -q examples/arbitrage_lab/build_vs_buy/tests        # offline: pack parsing, filters, comparison maths
```
Each line's `dropped` field records why listings were rejected, with examples; read it before trusting a thin line.

## Next
1. FieldDeck is priced (above) and does not clear its margin floor at retail-adapter prices. Before any FieldDeck work, get a
   real quote for a 10-unit FieldIO board (2x isolated RS-485, CAN, DI/DO, USB hub, GbE) and check whether it lands near
   NT$2,500 with the dock. If it does not, drop the route; the used rugged market already sells the function.
2. For the drone, stop treating the whoop as the product: pick a function a commodity BNF does not have and price that.
3. Physical checks that no listing can answer: Matrix II hole positions, motor connector, AIM8I dock pinout and battery health.
