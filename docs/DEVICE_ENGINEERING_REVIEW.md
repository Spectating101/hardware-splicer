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
| Electrical | I2C bus loading | Wire lengths come from the drawn jumpers. Capacitance is estimated from the wire (assumed 30 to 100 pF/m); the high estimate adds 10 pF per pin, which UM10204 Table 10 gives only as a maximum, so the low estimate is the wire alone. Pull-ups are counted only where the library states a value. The bus must satisfy Rp(max) = tr / (0.8473 x Cb) with tr = 1000 ns and Rp(min) = (VDD - 0.4 V) / 3 mA (UM10204 section 7.1, Table 10). When any module on the bus does not state its pull-ups the result is `advisory`: unstated pull-ups sit in parallel, which helps the rise time and can break Rp(min), so neither verdict follows from the stated values |
| Power | USB supply current | Each module's sourced currents (for the ESP32 module, its Wi-Fi transmit peak, 379 mA, WROOM-32E datasheet Table 16), counted 1:1 at the port, as a linear regulator would draw them. These are sums of published figures; a typical figure is not a maximum and peaks need not coincide, so neither sum is a bound. A module whose source gives only peak figures is named and counted in the peak sum only. A controller whose datasheet asks for more than the port is assumed to give is `exceeds_limit`; one that asks for exactly the port's budget is said to leave no margin |
| Thermal | Sealed-case temperature | Natural convection from the five exposed faces (assumed 5 to 10 W/m2K). Heat is each current at the rail it was measured on, plus a known linear regulator's drop, with converter losses unmodelled; a peak (a radio transmitting) run without pause overstates it. The surface temperature is given as a range from the convection assumption at a warm ambient, never as a floor. It is `exceeds_limit` only when even the sustained load with the better convection reaches the lowest sourced limit, and otherwise `advisory`. It never shows that the parts inside are cool |
| Thermal | Temperature-sensor bias | The BME280's reading sits above ambient by an amount that depends on PCB temperature and self-heating (Bosch datasheet note). The check reports how close the sensor is to the controller board |
| Radio | Antenna clearance | For a board whose entry lists an antenna: the gaps from the antenna end to the end wall, the side walls (to the board's edge, a lower bound for the antenna itself), the floor and the lid, against the clearance its source recommends (Espressif: at least 15 mm in all directions around the antenna inside a housing). Short at the end wall is `exceeds_limit` (the case can be lengthened there); short in another direction is `advisory`. The distance to other modules is reported from the antenna end's footprint, not judged. Boards with no antenna say `not_assessed` |
| Mechanical | Gaps to the walls | Every module outline against the inside walls and a 0.3 mm printer tolerance |
| Mechanical | What holds the board when a cable is plugged in | How far the board can travel before the antenna end meets the wall |
| Printing | Wall thickness, the USB bridge, the lid orientation | Against a 0.4 mm nozzle and a 20 mm bridge limit, both assumed |

## What it found in the generated case, and what the case now does about it

The review's first run on the shipped ESP32 examples found the antenna end of the board **1 mm** from the inside wall, against a recommended
15 mm, and a board that could slide only 1 mm before that end met the wall, so a plug's push went through the antenna end. The case now
answers both, as spec options that are on by default:

- `case.antenna_clearance`: the case is lengthened at the antenna end until the gap meets the clearance the board's library entry sources
  (15 mm for the ESP32 module, about 14 mm longer). Set it to `false` to get the old case, and the review reports `exceeds_limit` again.
- `case.board_stops`: for any board with header pins below it, a low stop block sits 0.5 mm past the last pin of each row, so a plug pushed in is
  taken by the pins. A board with no antenna, like the Pico, grows slightly to make room for them. The review reports the travel (0.5 mm)
  and says plainly that the stops' strength and the insertion force are not assessed.

The stops are small printed blocks at typical sizes and nothing else holds the board. With both options off the ESP32 plans are byte-identical
to what they were before these options existed.

## What it does not assess

EMC and radio regulation, ESD and surge, vibration and shock, ingress, mechanical strength, long-term reliability, and the supply
current of the display and sensors (no sourced figure in the module library). The result lists these.

## Limits

- Wire capacitance, convection, ambient temperature, printer tolerance and the bridge limit are general practice, not measurements.
- The DevKitC user guide does not say what its 3.3 V regulator is, so the supply check shows the linear case as a conditional figure.
- Sourced figures are those of the ESP32-WROOM-32E, the BME280 and the I2C specification as read on 2026-10-13; a different board or
  revision needs its own.
- Nothing here has been measured on hardware. `physical_correctness` stays `UNPROVEN`.
