# Open reference designs

[`open_reference_designs_20261125.json`](open_reference_designs_20261125.json) records 14 published KiCad boards in four product classes: which parts each functional block uses, how the supply rails connect, and what three checkers report on each. Every board is pinned to a commit (or, for Raspberry Pi's CM4 IO board, to the SHA-256 of its download). Only facts read from the schematics are stored here. No design files are copied, so each board's own licence (CERN-OHL, GPL, MIT or none stated) stays with its source. None of these boards was built or measured for this record.

## How a FieldDeck-class handheld is powered

All four battery boards use the same chain:

1. **USB-C input.** The board needs either 5.1 kΩ Rd on both CC pins (Argo's power port) or something that handles CC itself: the CM5 module (CM5 MINIMA), or a role controller such as the HD3SS3220 (Argo's USB 3.0 port).
2. **Charger with a power path.** The BQ25895 (Argo, PiUPS) feeds the system rail from USB and charges the cell at the same time. Beepy uses a linear TP4054 instead, plus a P-MOS load-sharing switch whose gate sits on VBUS, so the cell takes over only when USB is unplugged.
3. **Boost to 5 V.** The system rail is boosted to 5 V for the compute module: TPS61022 on Argo, TPS61088 on PiUPS, TPS61090 on Beepy.
4. **Current-limited port switches.** Downstream USB ports are fed through switches with a current limit: AP22653, RT9742, STMPS2151.
5. **Support parts.** An RTC with a backup supply (DS3231M, PCF85063, or the CM5's own RTC on VBAT), ESD arrays on USB (TPD4EUSB30), and a fan controller (EMC2301 on the CM4 IO board).

HS's cyberdeck plan ([`../arbitrage_lab/build_vs_buy/cyberdeck_pi5.json`](../arbitrage_lab/build_vs_buy/cyberdeck_pi5.json)) buys steps 2 and 3 as one "UPS HAT" line. PiUPS is the open version of that part.

## How a small drone's electronics are laid out

- **Flight controller.** An MCU (STM32F722 or RP2354A), an IMU (ICM-42688-P or BMI270), a barometer (BMP388 or BMP580), blackbox flash, and on the F7 board an AT7456E analog OSD.
  - The VENDETTAFC feeds its IMU and barometer from a separate LDO through ferrite beads, on a rail of their own (+3.3VA).
  - OpenAIO gives its gyro its own 1.8 V LDO.
- **Power from the pack.** Buck converters run straight from the LiPo: MP9943 for +9 V and +5 V, LMR51430 or LMR54406 for the +10 V gate-drive rail. An LDO then makes 3.3 V. Battery voltage reaches an ADC through a divider.
- **ESC.**
  - On AM32 boards, one small MCU per motor (AT32F421) drives a three-phase driver (NSG2065Q) from the +10 V rail.
  - The 1S whoop uses EFM8BB51 MCUs instead and boosts the cell to 5 V (TPS61022).
  - An INA186 senses battery current.
- **Radio.** ExpressLRS on an SX1281 is on the board itself in the all-in-ones (with an SE5004L amplifier on the whoop), next to an ESP32 for configuration. The whoop also carries an RTC6705 analog video transmitter.

HS-3G ([`../drone_proving_ground/inputs/parts.json`](../drone_proving_ground/inputs/parts.json)) treats the flight controller and ESC as one bought "stack". These boards show what sits inside that stack.

## What the checkers say on boards that were published as working

| Checker | Errors on these 14 boards | Notes |
|---|---|---|
| KiCad ERC | 0 to 62 per board (190 in all), plus 67 to 873 warnings | 150 of the 190 errors are "pin not driven" or "power pin not driven": an input or power pin whose net has no pin typed as a driver |
| kicad-happy (deterministic) | 0 to 29 per board (85 in all) | |
| HS `kicad_design_review` | 0 errors, 0 warnings; notes only | **Not a false-positive rate**: HS's rules were adjusted on these same boards. The held-out measurement is recorded separately. |

Read the totals with care. A board being published is not proof that it works, and these counts were not judged one by one.

Reproduce with `PYTHONPATH=src python -m hardware_splicer.kicad_design_review <schematic or netlist>`. Boards saved by KiCad 10 need a KiCad 10 `kicad-cli`; point `HARDWARE_SPLICER_KICAD_CLI` at one.
