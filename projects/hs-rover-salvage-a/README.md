# HS-ROVER-SALVAGE-A: a camera rover from a broken phone and a broken toy car

**Status: build package only. Nothing has been bought, opened, wired or driven.** The firmware and the PC self-test are
tested on a computer against a simulated rover (`tests/test_rover_salvage_a.py`); everything physical is unproven.

A phone with a cracked screen supplies the camera, Wi-Fi and video; a broken RC car supplies the motors, wheels and
chassis; cells from dead laptop batteries supply the power. A NT$73 ESP32-C3 board drives the motors and serves a
drive page that shows the phone's video. Compared with what is sold, see `../hs-rover-a/README.md`.

## Parts: NT$574 in all, NT$175 of it new (`bom.json`, checked with `hs_bom_check`)

| Part | Origin | Price (Ruten, 2026-11-26) |
|---|---|---|
| Android phone that powers up, cracked screen (one listing: Galaxy Note 3) | salvaged | NT$100 |
| Broken RC car with two working motors (or a NT$400 mini tracked tank if none works) | salvaged | NT$200 |
| Dead laptop battery packs (a lot), for two 18650 cells | salvaged | NT$99 |
| Two resistors, 100 kOhm and 33 kOhm, from any junk circuit board | salvaged | 0 |
| ESP32-C3 PRO MINI board | new | NT$73 |
| DRV8833 two-motor driver module | new | NT$22 |
| MP1584 step-down module (set to 5.0 V) | new | NT$13 |
| Two-cell 18650 holder, 2S protection board, TP5100 two-cell charger | new | NT$47 |
| 30 g of PLA for a mount (or zip ties and foam tape instead) | new | about NT$20 |

Not included: shipping from each seller, a spare phone in case the first is dead, and tools (screwdriver, soldering
iron, multimeter). Each listing is untested; read the description, and prefer "powers up" (上電有反應) or "boots".

## How to build it

**1. Check each donor before taking anything apart** (the checks come from `hs_junk_lookup`):

* Phone: it charges and boots; the camera app shows a picture; it joins Wi-Fi; a streaming app installs. Stop if the
  back or screen bulges: a swollen battery must not be charged; take it to a battery recycling point.
* Toy car: measure its original battery's voltage (or read the label). Write it down as `motor_v_max`. Each motor
  spins on that voltage; the gears are not stripped.
* Laptop pack: open it slowly, never pushing a blade into a cell. Keep only cells above about 3.0 V at rest, with no
  dents or leaks. Pick two within 0.1 V of each other.

Weigh what you salvage (a kitchen scale) and photograph each donor: those numbers go into the project record.

**2. Wire it** (power off, cells out of the holder):

```text
 2 x 18650 in holder ──► 2S protection board ──┬──► DRV8833 VM          DRV8833 AOUT1/AOUT2 ──► left motor
 (charge with TP5100 at 8.4 V)                 ├──► MP1584 IN ─► 5.0 V ─► ESP32-C3 5V pin
                                               └──► 100 k ─┬─ 33 k ─► GND     DRV8833 BOUT1/BOUT2 ──► right motor
                                                           └──► ESP32-C3 GPIO3 (battery reading)
 ESP32-C3 GPIO4 ─► AIN1   GPIO5 ─► AIN2   GPIO6 ─► BIN1   GPIO7 ─► BIN2   GND ─► DRV8833 GND
 If the DRV8833 module has an EEP or nSLEEP pin, connect it to the ESP32's 3.3 V.
```

**Set the MP1584 to 5.0 V with the multimeter before connecting the ESP32**; it comes set to an unknown voltage.
Pin numbers can be changed in `config.json` if your board is labelled differently.

**3. Load the program.** Flash MicroPython for the ESP32-C3 (https://micropython.org/download/ESP32_GENERIC_C3/) with
`esptool`, copy `firmware/config.example.json` to `config.json`, fill in your Wi-Fi, `motor_v_max` and (after step 4)
the phone's stream address, then copy the files: `mpremote cp firmware/main.py firmware/rover_logic.py config.json :`.
Without Wi-Fi details it makes its own network, `hs-rover`.

**4. Phone.** Install a camera streaming app that gives an MJPEG address (for example IP Webcam: `http://<phone>:8080/video`),
keep the screen awake, and mount the phone facing forward with zip ties or foam tape.

**5. Test with the wheels off the ground**, from a PC on the same Wi-Fi:

```bash
python tools/selftest.py --rover http://<esp32-address> --phone http://<phone>:8080/video --out evidence.json
```

It checks the rover answers, the battery reads 6.0-8.6 V, drive commands are accepted, **the motors stop on their own
when commands stop**, bad commands are refused, and the video delivers at least 5 frames a second. Then drive it on the
floor from the page at `http://<esp32-address>/` and film it: that the wheels turn and the rover moves cannot be checked
from the PC.

## What to send back to HS

`evidence.json`, the video, photos of each donor before and after, the salvaged weights, and how long each step took.
With those, HS records the build: whether it works, real cost and real hours against the US$30-50 product, and grams of
junk reused, which are the numbers the salvage business case and grant applications need.

## Safety

The motors stop by themselves 0.6 s after the last command and when the pack falls below 6.4 V. Lithium cells are the
real hazard: no damaged or swollen cells, charge only with the protection board in circuit, and never leave it
charging unattended.
