# HS-ROVER-VAC-A: a mapping camera rover from a faulty robot vacuum and a cracked phone

**Status: design record only. No donor has been bought, opened, measured, wired or driven.**

The objective: a rover that maps a room with a laser scanner, drives on its own, and streams live video on the local
network, for less than the cheapest wheeled camera robot sold (the "Blinky Bot", US$30-50, about NT$1,500 on Shopee;
see `projects/hs-rover-a`). Worked through HS's toolbelt on one project record (`project/ledger.jsonl`; rerun with
`run_through_toolbelt.py OUT_DIR`).

## Where it comes from

A first-generation Xiaomi Mi Robot Vacuum (SDJQR01RR/02RR) carries an LDS02RR laser scanner, two encoded drive wheel
modules, a 14.4 V 5.2 Ah Li-ion pack with its own protection board, a bumper and cliff sensors, all already mounted at
the right height in a working body. Faulty ones sell for NT$1,000-2,625 on Ruten (27 Nov). `hs_junk_lookup` for a
scanner, encoded drive, pack, bump sensors, camera and compute returns exactly two donors: that vacuum and a cracked
Android phone.

The open robot vacuum OOMWOO (Apache-2.0) builds from these same modules bought one by one as spares (about US$200 plus
a Raspberry Pi) and is not yet buildable. This rover keeps the donor's body instead, so no chassis has to be designed.

## Two routes, chosen by the donor's main board

| | Route A: main board works | Route B: main board dead |
|---|---|---|
| Control | Valetudo (Apache-2.0) replaces the cloud firmware: local driving and the vacuum's own map | ESP32-S3 drives both wheels (two DRV8871) and the scanner motor (a MOSFET switch), reads the encoders and the scanner (kaiaai/LDS, Apache-2.0) |
| Camera | the phone, clamped on the top cover, streaming over Wi-Fi | same |
| Charging | the vacuum's own dock | a 4S Li-ion charger at 16.8 V, through the pack's own protection board |
| Parts (`bom.json`, `hs_bom_check`) | **US$37.10** (NT$1,221), US$0.66 of it new | **US$46.83** (NT$1,541), US$10.39 of it new |

Both are under the Blinky Bot's US$50 top price; route B is about its NT$1,500 street price. What the rover has that
the toy does not: a laser map, 7 h of runtime and local-only video.

## Checks (HS tools, in the ledger)

| Check | Result |
|---|---|
| Drive (`hs_size_rover_drive`, 4.0 kg, 71.5 mm wheels, 0.25 m/s, 5 deg) | the salvaged wheel module passes: 0.43 m/s at cruise, 0.20 A per motor cruising, 0.31 A on the slope, 8% of its stall torque |
| Energy (`hs_energy_budget`, 2 h session) | 0 errors; about 7.1 h at an 8.9 W average (scanner 2.0 W, ESP32 0.6 W, phone 3.0 W declared; motors from the drive check) |
| Parts (`hs_bom_check`, US$50) | both routes pass; every price has its listing URL; donors are marked salvaged |

The wheel module's figures come from one aftermarket Roborock S5 Max-family module measured by OOMWOO contributor
@IKsares (winding resistance 5.08 ohm, brush drop 1.91 V, no-load 0.13 A and 6,150-6,180 rpm at 12 V, 65.36:1 by tooth
count, 4 encoder cycles per motor turn, 0.859 mm per edge). Its 14.4 V speed and torque are derived from those, with a
60% gearbox efficiency assumed (`data/drive/salvage_gearmotors_20261127.json`).

## Wiring for route B (wheel modules: verified on the measured module; check yours)

Wheel module, 7-way JST ZH 1.5 mm connector, pins numbered from the wire side with the latches up:

| Pin | Function | Goes to |
|---|---|---|
| 1, 2 | wheel-drop switch, normally closed (open = treat as wheel dropped and stop) | ESP32 input with pull-up, other pin to ground |
| 3 | Hall sensor VCC (orange) | 3.3 V |
| 4 | Hall sensor output (blue), open collector | ESP32 input, **10 kOhm pull-up to 3.3 V mandatory** |
| 5 | Hall sensor GND (brown) | ground, tied to the driver ground at one point |
| 6, 7 | motor (black, red) | DRV8871 OUT1/OUT2; VM from the pack (14.4-16.8 V; the driver takes 6.5-45 V and 3.6 A peak against the motor's 2.93 A stall at 16.8 V) |

The encoder is single-channel: speed and distance, not direction; firmware takes direction from the polarity it
applies. Do not power the Hall sensor from the motor rail. The scanner follows kaiaai/LDS's LDS02RR wiring: its motor
on the MOSFET module from 5 V, its data line into an ESP32 UART.

## Open before anything is built

1. Whether a 1st-gen Xiaomi's wheel modules match the measured S5-family module. Measure on the donor with
   @IKsares's method: locked-rotor voltage at three currents, then the encoder frequency at 12 V.
2. The scanner's power draw (2.0 W declared) and the phone's while streaming.
3. Route A on this donor is weak: Valetudo's page says the 1st-gen Xiaomi ("Xiaomi V1") never got persistent maps, so
   it maps afresh every run, and units made after 2020-03 need full disassembly to root. A Vacuum-Mop P (STYJ02YM,
   3irobotix CRL-200S inside; NT$1,400 faulty on Ruten) roots over micro USB and already has an open driver and a ROS2
   bridge, and it mops: the junk catalogue now lists it (`robot-vacuum-mop-crl200s`).
4. The phone clamp: a printed part not yet drawn; the top cover's dimensions need measuring on the donor.
5. Every donor is untested until opened: check the pack for swelling before charging it.
