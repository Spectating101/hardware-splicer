# HS next engineering gate — exact Winstar display driver and genuinely protected battery

2026-11-08. Product objective: a **useful, economical personal dual-touchscreen portable programming terminal** that showcases Hardware Splicer's engineering judgment, **not** a cyberdeck company. This is an HS-native reproducible *decision gate* requiring vendor and live test evidence, not an independently powered or completed device.

**Decision: NO-GO on component purchasing or full PCB fabrication for this candidate yet.** Previous PR #310 passed native inset-hinge shell-only and nominal-screen CGAL poses, but failed real display-tolerance and screen-retention constraints. This study reuses its source-hashed `hinge_qualification.json` rather than claiming those safety blockers disappeared.

## Important new firmware evidence

1. The **CM4** exposes two hardware DSI ports: DISP0 2 lanes, DISP1 4 lanes, maximum 1 Gbit/s/lane. Its published datasheet says only displays supported by the official Raspberry Pi firmware are supported without further integration work. CM4 DSI requires 100-ohm differential impedance and intra-pair matching better than 0.15mm. [Raspberry Pi CM4 datasheet, §2.8](https://datasheets.raspberrypi.com/cm4/cm4-datasheet.pdf).
2. Our **exact Winstar WF50DTYA3MNG10-000** is a separate 2-lane MIPI panel, ILI9881C display + GT928 touchscreen, with **separate 40-pin display and 6-pin touch FPCs**. Its revised 2025-09-01 datasheet and revision history explicitly mention **MIPI2 driver changes to the FPC jumper**. This is not the superficially identical 4-lane `WF50DTYA3MNG10`. [Exact vendor PDF](https://www.winstar.com.tw/d/676/WF50DTYA3MNG10-000.pdf).
3. The **official Raspberry Pi Touch Display 2 5-inch** uses the same family of display controller and exposes `raspberrypi,dsi-5inch` in its [overlay](https://github.com/raspberrypi/linux/blob/rpi-6.12.y/arch/arm/boot/dts/overlays/vc4-kms-dsi-ili9881-5inch-overlay.dts), but its specific firmware timing and init are NOT demonstrated to work on the exact Winstar unit. Examined [Raspberry Pi 6.12.y ILI9881C driver](https://github.com/raspberrypi/linux/blob/rpi-6.12.y/drivers/gpu/drm/panel/panel-ilitek-ili9881c.c) blob `416ff6fe6d8995fc42a37ea3565a9faabdbde427`; the exact Winstar part is not named. Absence of a part name is not a proof a custom driver cannot be written, but it prevents calling the existing driver plug-and-play.
4. The official Touch Display 2 5-inch is **91.5 × 143.5 × 16 mm as a module**, so it cannot replace Winstar within an **80 mm-wide and 18 mm closed** case. It is a useful *software control/reference* only. [Raspberry Pi Touch Display 2 product documentation](https://www.raspberrypi.com/documentation/accessories/touch-display-2.html).

The **720×1280×24bpp×60Hz / 2-lane** raw **ACTIVE-PIXEL-only** rate is **0.663552 Gbit/s per lane**, lower than the CM4's stated 1 Gbit/s/lane. That establishes only an optimistic physics bound. MIPI blanking/packet overhead, actual panel clock/porch/init, both DSI channels, two GT928 I2C/INT/reset paths and the desktop's touchscreen mapping remain **unverified**. Do not use a copy of the official overlay to infer success.

## Actual protected battery vs. 18 mm

A vendor lists **LiPol LP525178**, 3.7 V / 2,500 mAh, **9.25 Wh**, overall **78.6 × 50.3 × 5.2 mm**, with protection PCB, but **no NTC thermistor**; complete Taiwan landing price is absent and its listing mentions an MOQ of 5 samples. [Supplier product listing](https://www.lipobattery.us/lp525178-3-7v-2500mah-9-25wh-li-poly-battery/). This is **not an approved integrated battery/charger**: fit, protection-system interaction, peak current, charge thermal and bend/swelling allowances are untested.

| Lower internal stack scenario | HS lower-bound envelope | Shortfall vs. 18mm |
|---|---:|---:|
| Old hypothetical, **unprotected 6mm cell** | **19.050 mm** | 1.050 mm |
| Source-listed **protected LP525178 5.2mm pack** | **18.928 mm** | **0.928 mm** |

Why is the improvement only **0.122 mm** rather than 0.8 mm? The **CM4 module/connector and 0.8mm carrier** reach **5.878 mm** above the shell floor. Once the pack is thinner than that, CM4 becomes the limiting item. Both estimates assume the vendor worst-case panel thickness **3.45 + 0.5 mm**, **0.15mm provisional bondline**, 1mm component-separation allowance, two 1.6mm FDM floors and 0.8mm closed gap. This is a lower bound, *excluding* pack swelling/retention, FPC and connectors and extra backing—NOT proof of 18.928mm manufacturability.

## Correct order of work

1. **Before buying anything:** obtain the exact Winstar `-000` 2-lane Linux/DSI initialization commands, pixel timings and backlight/power-sequencing guidance; ask about direct CM4 Linux compatibility. No driver available = reselect a documented and actually fit-compatible panel, or consider a different compute/display topology.
2. **First bench:** on a known-safe development carrier, prove **ONE exact screen** starts and reports touch; log DSI modes, source commit, I2C address, reset, backlight waveform and thermal. Buying a single panel remains an explicitly separate decision.
3. **Second bench:** show **BOTH screens concurrently** on CM4 DSI0+DSI1 with independent touch coordinate maps, keyboard events, SSH/tmux interaction, reconnect and display power cycling.
4. **Only then** design the carrier and flex path and re-run mechanical tolerances with an actual specified protected pack and retaining mechanism; get complete Taiwan delivered quotations before fabrication.

**Backlight reminder:** each exact Winstar has a nominal 40 mA LED load at 19.6–23.8 V; two require **1.568–1.904 W** of LED drive before regulator losses. This is a **current-regulated boost** design problem. Do not connect directly to a battery or nominal 5V rail. Power-on/off sequencing, analog/logic/touch voltage supplies, protected charging and NTC/thermal remain electrical safety blockers.

## Reproduce / test

```sh
PYTHONPATH=src python3 -m hardware_splicer.cyberdeck_electrical_feasibility \
  --input examples/cyberdeck/electrical_feasibility/inputs.json \
  --out examples/cyberdeck/electrical_feasibility/report.json

PYTHONPATH=src:apps/mecha-splicer:apps/mecha-splicer/src \
  python3 -m pytest -q tests/test_cyberdeck_electrical_feasibility.py \
  tests/test_cyberdeck_inset_hinge.py tests/test_cyberdeck_cm4_stack.py
```

Outputs are human-readable `report.json` and an input SHA256 + prior HS gate SHA256 receipt. This is a **source-version-pinned research replay**, not a live firmware tester, supplier purchase, or fully automatic driver port.
