# Hardware Splicer — Integrated Dual-Portrait First-Prototype Gate

**Date:** 2026-11-09. **Owner's objective:** two physically independent 720 × 1280 portrait touchscreens with genuinely useful LOCAL Linux programming performance, plus SSH to Optiplex. No physical keyboard and **no plan to launch a handset company**. DS-style folding handhelds remain mechanical reference designs, not substitutes for our user-specified two-screen concept.

**This iteration actually implements and exercises an integrated *software* first prototype. It has NOT fabricated or powered a physical CM5 workstation.** The separate, manual physical bench described below is a hard prerequisite for using the words *physical working prototype*.

## What we built and ran

Unlike #312 and #313's *single combined 720×2560 browser viewport*, this app now presents **TWO independent pages**, each 720×1280, intended for different real display outputs:

- **Upper** `/terminal`: upstream [xterm.js](https://github.com/xtermjs/xterm.js) 6.0.0, actual SSH output from isolated OpenSSH, terminal resizing, no input/typing API.
- **Lower** `/keyboard`: independently rendered large-key touch keyboard with alphabet/symbol layers and Escape, Tab, Ctrl, Shift, arrows, Enter, Ctrl+B, Ctrl+C/D. Sends input through a **separate, input-only WebSocket**. Has no access to terminal bytes or DOM.
- The localhost-only Python bridge owns a single real SSH PTY, so a tap on the lower independent surface changes the real terminal on the upper. Authentication uses per-run random bearer token, same-origin WS, a fresh pinned Ed25519 SSH host/client pair, and an isolated Bubblewrap filesystem/network with no user home or GitHub keys.
- **Real Chromium + Playwright** actually opened both independent 720×1280 pages, tapped the lower surface, ran `pwd`, edited a real file with Nano and Ctrl+O/Ctrl+X, and detached a real tmux session using Ctrl+B/D. Screenshots and the machine-readable result are in `evidence/`; this is *not* prerecorded terminal content. Neither screenshot is a photo of a physical screen.
- A read-only Linux hardware probe ran on the connected Optiplex and identified **NO Raspberry Pi CM5 and NO TWO connected 720×1280 DSI screens or touch event streams**. We refuse to quietly substitute x86 Chrome for ARM/DSI hardware.
- Canonical HS MachineProject integrates the browser, SSH, source-linked bench hardware and real hardware probe into one `BUILD_READY` assessment. **Five measured software functions pass; a physical build is blocked.**

## Reproduce NOW on the authorized Optiplex

Prerequisites: local OpenSSH server executable and client, bubblewrap, tmux, Nano, Chrome, Python 3 aiohttp and Playwright, npm with pinned xterm dependency. Host must have legacy TIOCSTI tty injection **disabled**. This is a development-only server with intentionally isolated temporary SSH. Never publish it to a LAN or use personal SSH credentials in this app.

```bash
# From repository root:
npm ci --prefix examples/cyberdeck/workflow_lab/web --ignore-scripts --no-audit

# Run REAL Chrome in 2 independent pages, real localhost SSH, Nano, tmux:
python3 examples/cyberdeck/integrated_bench/run_integration.py

# Run read-only hardware presence probe (BLOCKS on this Optiplex):
python3 examples/cyberdeck/integrated_bench/first_boot_probe.py \
  --out examples/cyberdeck/integrated_bench/evidence/optiplex_first_boot_probe.json

# Recompute canonical HS release decision from actual measured evidence:
PYTHONPATH=src python3 -m hardware_splicer.cyberdeck_integrated_prototype_gate \
  --root examples/cyberdeck/integrated_bench \
  --out examples/cyberdeck/integrated_bench/evidence/hs_integrated_gate.json
```

To manually interact on the authorized local computer, launch `python3 examples/cyberdeck/integrated_bench/dual_panel_server.py`, open **upper terminal URL first** then the **separate lower keyboard URL** printed locally. If the terminal browser page disconnects, close/reopen the keyboard too. The server uses fresh temporary SSH keys, no passwords or forwarding, and stops when interrupted. No physical touch or screen is inferred.

## Physical bench *next* (not yet carried out)

Avoid the mistakes of designing an unknown custom carrier and battery before verifying the display protocol. **Only off-the-shelf manufacturer development hardware** for this separate, unconstrained **desktop** prototype:

| Functional block | Bench part / method | What is still unknown |
| --- | --- | --- |
| Local compute | Raspberry Pi **CM5 wireless Lite 4GB** as a *baseline*, optionally 8GB for RAM workload comparison | Real compile time, RAM use, thermal behavior, storage performance |
| Reference carrier | Official **CM5 IO Board**, **160 × 90mm**, with two 22-pin 0.5mm MIPI DSI/CSI connectors | Board is FAR TOO LARGE for finished handheld. No custom PCB qualified |
| Displays | **Two** Waveshare **5inch DSI LCD (D)**, each native 720×1280 portrait, capacitive touch | Vendor documents each model/port separately, **not this exact simultaneous two-panel pairing** |
| Storage | Quality microSD for **CM5 Lite** (no on-module eMMC) with verified Raspberry Pi OS installation | Actual boot and IO reliability |
| Power | **Manufacturer-appropriate regulated USB-C 5V, 5A supply** for CM5IO; no Li-ion or improvised boost | Real current, heat and performance under two LCDs |
| Wiring | Two vendor-supported 22-pin-to-screen DSI cables, proper pin orientation and bend radius | No hinge/FPC fatigue, no final enclosure |
| Cooling | Official-compatible CM5 fan/heat sink for desk test | Actual sustained clock/power not tested |

Primary vendor references:
- [Raspberry Pi CM5 IO board and two MIPI connectors](https://www.raspberrypi.com/documentation/computers/compute-module.html)
- [CM5 IO Board datasheet, J6 touch I2C jumper consideration, 5V power](https://datasheets.raspberrypi.com/cm5/cm5io-datasheet.pdf)
- [Waveshare exact 5inch DSI LCD (D) wiring/overlay](https://www.waveshare.com/wiki/5inch_DSI_LCD_%28D%29)
- [Previous HS vendor OpenCascade STEP and Taiwan price evidence](../workstation_tradeoff/README.md)

### Manual physical commissioning sequence — gate each stage

**1. CM5 alone:** Verify correct qualified 5 V supply, heatsink, SD card, boot, exact board revision, OS version, Ethernet/Wi-Fi, and thermals. No battery.

**2. One display on CAM/DISP 1:** With power OFF, attach correct flat cable. Waveshare documents the `dtoverlay=vc4-kms-dsi-waveshare-panel,5_0_inch` overlay for DSI1 (plus vc4 KMS overlay). Confirm BOTH image and touch; log DRM connector mode, input event ID, pixel orientation, and backlight behavior. Do NOT blindly change J6 or 1.8/3.3V jumpers—review exact CM5IO board schematic and manufacturer revision.

**3. Move the same display to CAM/DISP 0:** With power OFF and manufacturer pin orientation verified, Waveshare separately documents the `...,5_0_inch,dsi0` overlay. Boot and verify again. This isolates port and cable issues before buying or connecting the second display.

**4. Two simultaneously:** Only after one-screen/each-port success, experiment with BOTH overlays on a recoverable boot configuration. Check both 720×1280 DRM connectors and independent physical touch controllers; do NOT assume two copies of the overlay can initialize or coordinate separate I2C and touch mapping. Use an external HDMI rescue display/SSH during experiment. If either fails, the gate stays BLOCKED; do not produce a carrier PCB.

**5. Run HS app on actual two displays:** Assign **upper terminal URL to panel 1** and **lower keyboard URL to panel 2**, not a fake combined window. Validate touch mapping/position in the actual compositor (Wayland or X11), then run real on-device Python/Git/compiler workload and 30-minute human typing task. The current local sandbox fixture is **not a production Optiplex connection**: a real hardened SSH client and host-key/identity scheme must be integrated separately.

**6. Measure:** thermal throttling, sustained RAM use, current/power (with an external power meter), CPU load, refresh/touch input delays, comfort, small-screen typing errors, FPC orientation and sleep/reconnect behavior. Only then consider an integrated carrier, battery pack, folding hinge and manufacturability.

The official CM5 IO board already exceeds the *previous assistant's* 155×80×18mm exploratory handheld target. That is intentional: this is a **functional desk bench**. Neither the historical 18mm thickness nor NT$8,000 assistant-proposed budget was separately authorized as a hard requirement. A physical prototype should **work before being miniaturized**, but a large desk fixture cannot be presented as finished pocketable hardware.

## Evidence/decision policy

- **Passed, actually measured:** two separate Chrome pages, separate input/output WebSockets, loopback sandboxed OpenSSH, Nano/tmux editing via lower touch events, auth/role checks.
- **Source-backed but untested hardware:** CM5IO two MIPI connectors and qualified PSU requirements; Waveshare model-specific *single panel per-port* setup.
- **Not done:** power on real CM5, two real DSI displays, independent capacitive touch mapping, on-device native compilation, safe battery, case/hinge, cost at delivered checkout and physical manufacturing.

The HS-native `cyberdeck_integrated_prototype_gate` keeps software success and physical hardware authority separate. **The next milestone is unambiguously a powered, measured, two-screen CM5 bench.** No more CAD-only acceptance should count as completion.
