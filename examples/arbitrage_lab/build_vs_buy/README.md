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
python3 -m pytest -q examples/arbitrage_lab/build_vs_buy/tests        # offline: pack parsing, filters, comparison maths
```
Each line's `dropped` field records why listings were rejected, with examples; read it before trusting a thin line.

## Next
1. Price the **FieldDeck donor build** properly: AIM8I + dock + isolated RS-485/CAN I/O, against what field-service terminals sell for.
   That is the route where the numbers favour splicing.
2. For the drone, stop treating the whoop as the product: pick a function a commodity BNF does not have and price that.
3. Physical checks that no listing can answer: Matrix II hole positions, motor connector, AIM8I dock pinout and battery health.
