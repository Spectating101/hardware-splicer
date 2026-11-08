# Hardware Splicer — dual-portrait local workstation, DS reference and compute challenge

**Research / native build**: 2026-11-09 (Taiwan).
**Purpose:** restore the *actual* user's product idea: **two independent high-resolution portrait touchscreens, no mechanical keyboard, enough compute for useful local Linux development**, with secure remote SSH as an additional capability. The Nintendo DS and modern RG DS family are **mechanical and integration references only**, NOT accepted screen or processor architectures. The assistant-proposed NT$8,000 and 155×80×18mm remain **research stretch goals, not user-approved build/purchase requirements**.

## Actual new work

1. Replaced a full, tiny 62-key 5-row phone-style virtual keyboard with an optional **wide-key portrait keyboard** with alphabet / symbols layers, touch terminal control keys and functioning SSH. The original full layout remains for other screen shapes; the 720×2560 viewport automatically enables the 8-key-wide layout. Uses the **existing xterm.js and OpenSSH** systems; no new VT100 renderer.
2. Ran **real Chromium** with virtual 720×1280 upper + 720×1280 lower portrait screens, a real SSH connection in a loopback sandbox and simulated touch events; measured xterm cells and CSS-to-manufacturer-active-panel projected button sizes against two gaming landscape references.
3. Used **OpenCascade BREP geometry** on the manufacturer-provided Waveshare `5inch-dsi-lcd-d_20241025.stp` (from the manufacturer's linked 3D archive), including **365 solid components**, to determine which assembly features dominate Z thickness. The measurement script and SHA receipt are included; the vendor's unmodified CAD is not republished.
4. Re-ran an evidence-linked **compute + 2 touch panel price competition**, including the stronger 4GB and 8GB *wireless* Raspberry Pi CM5 Lite modules, Radxa RK3588S2 CM5 and old CM4 baseline. Separates original currency, availability, SD storage, display driver and thermal risk; no fake landed BOM or fabricated device approval.
5. Added fail-closed HS regression tests and a reproducible report for all three evidence layers.

## Results

### Real portrait UI (browser, not fabricated device)

**Manufacturer-defined 5in LCD (D) active area 62.28×110.32mm** (outer glass 70.70×126.90mm). We simulated each 720×1280 screen by stacking them vertically in a single 720×2560 Chromium viewport, with **devicePixelRatio assumed 1**. Actual Android/Linux compositor scaling and human tactile behavior remain **unverified**.

| Reference per-screen display | 24px monospace terminal | Projected smallest letter-button width |
| --- | ---: | ---: |
| HS **2×5in 720×1280 portrait**, redesigned wide keyboard | **47 columns × 35 rows** | **7.28mm** |
| Original RG DS 2×4in 640×480 landscape, previous full keyboard | 42×12 | 5.13mm |
| RG DS Plus 2×4.3in 1024×768 landscape, previous full keyboard | 68×20 | 5.25mm |

**Within the same HS portrait viewport**, the previous full keyboard was projected at **3.53mm** letter keys. New wide layout yields **2.061×** wider letters. All full and wide layouts reach a **real pinned OpenSSH sandbox** with touch-generated `pwd`, and the portrait symbol layer typed a numeric command with **real touch events**. Legacy Nano, tmux and reconnect E2E was rerun successfully after the change. An arbitrary **7mm research target** is met in this simulation but **NO user ergonomics trial has been performed**. The wide layout has a different letter arrangement and may cost muscle-memory/time.

Screenshots from real Chromium are in `evidence/` (clearly browser proxies, not photographed handhelds).

### Vendor STEP: a path to integration, NOT a viable 18mm module stack

Measured using OpenCascade from **Waveshare 5inch DSI LCD (D)** manufacturer's 2024-10-25 actual STEP:

| Physically modelled geometry | Measured depth |
| --- | ---: |
| One complete retailer display assembly including rear mounting hardware | **13.608mm** |
| Two complete assemblies **alone** | **27.216mm** |
| Two displays after hypothetically OMITTING only deepest back mounting solids | **21.600mm** |
| Largest continuous face solid (geometric identification, not qualified detachable SKU) | **5.800mm each** |
| Two face solids + 1.6mm per-half FDM shell + 0.8mm closing gap | **15.600mm** |
| Remaining inside 18mm stretch goal **before processor, battery, connectors, drivers, shielding, fastening or tolerance** | **2.400mm** |

**Critical:** The 5.8mm face solid is only a geometry classification. It has NOT been detached, electrically characterized or reassembled. The vendor's supported board/backlight controller and 3D integrated driver PCB cannot be omitted without engineering a new electrical pathway. Merely removing mounting hardware leaves two screen assemblies too thick for 18mm even before a shell. This decisively argues against merely buying **two complete Waveshare modules** and stuffing them inside the old enclosure.

### Taiwan source-backed *compute + pair of screens only* asking-price arithmetic

Waveshare 5inch DSI LCD (D) **NT$2,319 each**, two total **NT$4,638**, iCShop made-to-order. NOT a checkout price or an assembled hardware quote.

| Exact compute SKU / seller evidence | Compute ask | Compute + 2 displays ONLY | Notes |
| --- | ---: | ---: | --- |
| CM4 Lite WiFi 2GB, old reference | NT$2,238.43 before VAT | NT$6,876.43 mixed tax basis | Not aligned to stronger local-workstation target; seller lead time long |
| **Raspberry Pi CM5 WiFi Lite 4GB `CM5104000`**, DigiKey | **NT$3,801** | **NT$8,439** | Local Linux baseline; 0 eMMC => SD + carrier; seller reports stock |
| **Raspberry Pi CM5 WiFi Lite 8GB `CM5108000`**, DigiKey | **NT$6,155** | **NT$10,793** | Better RAM target; 0 eMMC => SD + carrier; seller reports stock |
| Pi CM5 WiFi 4GB + 32GB eMMC, iCShop | NT$6,300 | NT$10,938 | Listed **sold out** |
| Radxa CM5 RK3588S2 4GB + 32GB eMMC | US$89 | **not comparable in NTD** | Sold out at cited dealer; Wi-Fi not assumed onboard; 4V 3A carrier requirement |
| Radxa CM5 RK3588S2 8GB + 64GB eMMC | US$119 | **not comparable in NTD** | Sold out at cited dealer; 8-core performance potential, not a measured winner |

**ALL subtotals omit:** carrier/assembly, mounting, custom display bridge PCB, microSD for Lite, wireless antenna, charging/protected battery, cooling, hinge, flex, cables, taxes/shipping, fabrication, rework and software bring-up. Availability is a seller snapshot, not real-time reserved stock. No inferred USD/NTD conversion.

Vendor sources:
- Official [Waveshare display wiki](https://www.waveshare.com/wiki/5inch_DSI_LCD_%28D%29), [manufacturer drawing](https://files.waveshare.com/wiki/5inch%20DSI%20LCD%20%28D%29/5inch_DSI_LCD_D.pdf), [vendor 3D archive](https://files.waveshare.com/wiki/5inch%20DSI%20LCD%20%28D%29/5inch-dsi-lcd-d_3D.zip), [iCShop Taiwan display](https://www.icshop.com.tw/en/products/388370100062).
- DigiKey [CM5 WiFi 4GB Lite `SC1592`](https://www.digikey.tw/en/products/detail/raspberry-pi/SC1592/25805568) and [CM5 WiFi 8GB Lite `SC1598`](https://www.digikey.tw/zh/products/detail/raspberry-pi/SC1598/25805587).
- Radxa [CM5 manufacturer documentation](https://docs.radxa.com/en/som/cm/cm5) and [ALLNET dealer options](https://shop.allnetchina.cn/products/radxa-cm5-1).
- [RG DS reference spec](https://anbernic.com/en-gb/products/rgds?variant=46854314721537).
- Other seller sources recorded item-by-item in `parts_sources.json`.

## Recommendation / next HS experiments

1. **Use CM5 4GB wireless Lite as the first local Linux software/control benchmark**, and CM5 8GB as the RAM-upgrade benchmark. Prove a real on-device workload: run Nano/Neovim, Python, Git and one compiled repository; log interactive responsiveness, peak resident RAM, thermals and power. Do not infer any specific 8GB speedup without testing.
2. Keep **Radxa CM5 RK3588S2** as the compute-performance challenger, *not* the automatic win. Obtain actual available 8GB pricing and a power/thermal design. Its documented recommendation is **4V 3A** for the carrier, with typical 2A current; this matters in a battery clamshell.
3. Source a **genuinely thin, driver-supported display subassembly** or vendor-approved relocated electronics package. Do not call a 5.8mm solid a working standalone screen.
4. Test **two independent DSI+I2C capacitive channels concurrently** on real hardware, followed by cable fatigue and full-body mechanical tolerance. For a real product, changing the stretch thickness to 20–24mm is a possible explicit design trade, **not** an already approved new requirement.
5. Do the 30-minute human typing trial *on physical 5-inch glass*: hit rate, characters/minute, shortcut reliability, wrong presses, fatigue. Browser tap simulation does not answer these.

This is **not another simulation declaring a hardware win**. It narrows the actual engineering problems: full display module packaging, stronger local Linux compute, and real physical input ergonomics.

## Reproduce

```bash
PYTHONPATH=src python3 -m hardware_splicer.cyberdeck_workstation_tradeoff \
  --sources examples/cyberdeck/workstation_tradeoff/parts_sources.json \
  --cad examples/cyberdeck/workstation_tradeoff/evidence/waveshare_d_step.json \
  --browser examples/cyberdeck/workstation_tradeoff/evidence/portrait_vs_DS_browser.json \
  --out examples/cyberdeck/workstation_tradeoff/evidence/hs_workstation_decision.json

PYTHONPATH=src:apps/mecha-splicer:apps/mecha-splicer/src \
  python3 -m pytest -q tests/test_cyberdeck_workstation_tradeoff.py \
  tests/test_cyberdeck_workflow_lab.py
```

Optional **real geometry replay**: download the original STEP archive from Waveshare, unzip, install an OpenCascade Python binding such as `cadquery-ocp`, and run:

```bash
python examples/cyberdeck/workstation_tradeoff/inspect_waveshare_step.py \
  --step /path/to/5inch-dsi-lcd-d_20241025.stp \
  --out examples/cyberdeck/workstation_tradeoff/evidence/waveshare_d_step.json
```

Optional **real browser / localhost SSH rerun** requires the same local OpenSSH, bubblewrap, Chrome/Playwright prerequisites as `../workflow_lab/README.md`:

```bash
python examples/cyberdeck/workstation_tradeoff/measure_dual_portrait.py
```

At no point does this report authorize spending, hardware power-on or fabrication.
