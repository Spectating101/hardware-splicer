# Engineering review of a device plan

> **An estimate from catalogued figures and stated assumptions.** It reports limits that are exceeded and things that need
> checking. It does not show that a design works, and it approves no building, powering or release.

`POST /v1/devices/engineering` (and **Review the engineering** on the device page) recomputes the plan from the spec and asks what
the layout implies. A caller's own plan or findings are never used. Every figure it uses is either **sourced** (a datasheet table or
a standard, named in the result with a link) or an **assumption** with its range, shown beside the check that used it. Figures about parts
live in each module's library entry ([adding a part](DEVICE_ADDING_PARTS.md)), so a new board or sensor adds data and no code here; a part with
no figures is listed under `coverage` and the checks that need them say `not_assessed`. A check
returns one of four statuses and never "pass":

| Status | Meaning |
|--------|---------|
| `exceeds_limit` | a sourced limit or recommendation is not met by this layout |
| `advisory` | something to check; the result depends on a value this review cannot know |
| `within_limit_under_assumptions` | under the limit if the listed assumptions hold; not a result |
| `not_assessed` | the inputs needed are not in the library; the review says which |

## What it checks

| Domain | Check | How |
|--------|-------|-----|
| Electrical | I2C bus loading | Wire lengths come from the drawn jumpers. Capacitance is wire (assumed 30 to 100 pF/m) plus 10 pF per pin (UM10204 Table 10). Pull-ups are counted only where the library states a value. The bus must satisfy Rp(max) = tr / (0.8473 x Cb) with tr = 1000 ns and Rp(min) = (VDD - 0.4 V) / 3 mA (UM10204 section 7.1, Table 10) |
| Power | USB supply current | Each module's sourced currents (for the ESP32 module, its Wi-Fi transmit peak, 379 mA, WROOM-32E datasheet Table 16), counted as a linear regulator would draw them: an upper bound on what a port supplies. Headroom against a 500 mA port is what every unsourced load must fit in. A controller that needs more than the port is assumed to give is `exceeds_limit` |
| Thermal | Sealed-case temperature | Natural convection from the five exposed faces (assumed 5 to 10 W/m2K). The heat is a floor: each current at the rail it was measured on, plus a known linear regulator's drop, with converter losses unmodelled. It can show a limit is exceeded, never that the parts inside are cool |
| Thermal | Temperature-sensor bias | The BME280's reading sits above ambient by an amount that depends on PCB temperature and self-heating (Bosch datasheet note). The check reports how close the sensor is to the controller board |
| Radio | Antenna clearance | For a board whose entry lists an antenna: the gap from the antenna end to the inside wall, against the clearance its source recommends (Espressif: at least 15 mm in all directions around the antenna inside a housing). Boards with no antenna say `not_assessed` |
| Mechanical | Gaps to the walls | Every module outline against the inside walls and a 0.3 mm printer tolerance |
| Mechanical | What holds the board when a cable is plugged in | How far the board can travel before the antenna end meets the wall |
| Printing | Wall thickness, the USB bridge, the lid orientation | Against a 0.4 mm nozzle and a 20 mm bridge limit, both assumed |

## What it found in the generated case

For the shipped ESP32 examples the antenna end of the board is **1 mm** from the inside wall, against a recommended 15 mm, so the
case is about 14 mm too short at that end. The case itself is not changed by the review: lengthening it is a layout decision that
moves every other dimension, and it is left for a person to make. The same layout lets the board travel only 1 mm before its antenna end
meets the wall, so the USB plug's push goes through the antenna end; the exported case has no board stops.

## What it does not assess

EMC and radio regulation, ESD and surge, vibration and shock, ingress, mechanical strength, long-term reliability, and the supply
current of the display and sensors (no sourced figure in the module library). The result lists these.

## Limits

- Wire capacitance, convection, ambient temperature, printer tolerance and the bridge limit are general practice, not measurements.
- The DevKitC user guide does not say what its 3.3 V regulator is, so the supply check shows the linear case as a conditional figure.
- Sourced figures are those of the ESP32-WROOM-32E, the BME280 and the I2C specification as read on 2026-10-13; a different board or
  revision needs its own.
- Nothing here has been measured on hardware. `physical_correctness` stays `UNPROVEN`.
