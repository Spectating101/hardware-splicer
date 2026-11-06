# HS CM5 USB host power successor: active SGM2590

**2026-11-07 · Native KiCad 9 schematic, not a fab/assembly authorization.**

SGMICRO's [SGM2576 product page](https://www.sg-micro.com/product/SGM2576)
marks that IC **obsolete** and explicitly names [SGM2590](https://www.sg-micro.com/product/SGM2590) as its recommended replacement.
This candidate carries the complete 5V → MP8759 nominal 4V CM5 power stage
from PR #303 and replaces only the switched USB VBUS stage U2 and its
current-limit resistor R6. No other electrical net changes were accepted.

## Manufacturer pinout and sourcing

[SGM2590/SGM2590D official April 2025 datasheet](https://www.sg-micro.com/rect/assets/28859410-24d5-43f6-8723-76d4c3a5d0e7/SGM2590_SGM2590D.pdf):

| SOT-23-5 pin | SGM2576 old | SGM2590 new | HS net |
|---|---|---|---|
| 1 | VOUT | VOUT | `USB_VBUS_SW` |
| 2 | GND | GND | `GND` |
| 3 | ILIM | ILIM | `ILIM_USB` |
| 4 | EN | EN | `USB_HOST_PWREN_H` |
| 5 | VIN | VIN | `VCC5V0_SYS` |

The old Radxa carrier drawing labels old pin 3 `OCB`—not the
SGMICRO datasheet name `ILIM`. Do not use that label to infer an
overcurrent-reporting signal or try to connect it to a GPIO.

- **Exact new manufacturer MPN:** `SGM2590XN5G/TR`, listed *active* by
  SGMICRO (not a verified supplier order).
- **Package:** SOT-23-5. The physical package class matches, but exact
  copper pad land pattern, available placement space and heat flow remain
  **unverified**.
- **Supply range:** 2.5–6 V, including regulated 5 V branch.
- **EN:** active high, internal pull-down **1.2 MΩ**, differing from
  SGM2576's 500 kΩ. CM5 logical host power enable is module pin 97.
- **Programmable limit equation:** `ILIM(mA) = 6612 / (R_ILIM(kΩ)^0.982)`.
  Selecting 4.53 kΩ yields **1.4998 A nominal**, not a guaranteed limit.
  Datasheet specifies at that resistor **1.31–1.675 A** across
  -40 °C to +125 °C, before tolerances of the actual resistor.
- **Relative to old source design:** SGM2576 used 4.7 kΩ and a different
  current-limit formula, around **1.4468 A nominal**.
- **Reference manufacturer price:** the SGMICRO page displays
  **USD 0.525** at 1–24 pieces (not an actual delivered cost or proof of
  immediate supply). Actual lead time, MSL, material and distributor quote
  must be checked before buying.

## Native KiCad validation

- `CM5_SGM2590_USB_POWER_NOT_FOR_FAB.kicad_sch`: editable **21-part**
  new switch revision.
- `HS_Power.kicad_sym`: local symbols for MP8759 and SGM2590, with
  vendor-specified pin identities.
- `CM5_SGM2590_NATIVE_NETLIST.xml`: authentic KiCad 9 export.
- `CM5_SGM2590_ERC.txt`: actual KiCad ERC, **0 observed electrical
  findings**, **23 symbol registration warnings**. Not a blanket
  completed-board ERC pass.
- `sgm2590_source_contract.json` and `sgm2590_validation.json` are
  inspectable verification records.

`src/hardware_splicer/cm5_sgm2590_successor_gate.py` compares **all
14 named KiCad electrical nets** against the original source-vetted
SGM2576 schematic. It rejects any altered switching regulator, power
supply, USB D+/D− assignment, or host enable net. It also confirms
**all five SOT-23-5 electrical pin functions** from source, the updated
programming resistor, new current-limit equation, and the continuing
fabrication blockers.

**Focused tests: 83 passed locally** across the whole CM5 development chain.

## Remaining STOP gates

1. Manufacturer technical substitution is **not proof of a physically
   validated drop-in replacement**: compare vendor SOT-23-5 land
   patterns, tolerances, assembly class, thermal paths and operating
   behavior (EN, auto discharge, current-limit temperature).
2. The core MP8759 5V-to-4V buck still has unqualified inductor
   Isat/DCR, PCB trace widths, regulator stability, input protection,
   current measurements and heat transfer.
3. USB-A D+/D− **ESD/EMI protection and connector shielding** are
   not designed. Actual output-voltage droop and host enumeration
   are untested.
4. The CM5 is represented by a *logical six-wire harness*, not a
   fully implemented physical 300-contact connector board. The
   manufacturer source **pin 290 NC vs v2200 RTC** discrepancy remains.
5. **No purchase, board routing, fabrication, powered prototype or
   formal electrical safety approval**. Never interpret a
   source-backed pin map as a functional USB module.

This revision makes the **USB switching part commercially supportable**
at the manufacturer specification level; the physical prototype remains
blocked. The next engineering priority is ESD/protection and full CM5
connector integration, not further speculative substitute lists.
