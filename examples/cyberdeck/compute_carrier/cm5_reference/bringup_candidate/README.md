# CM5 V2.21 power/boot electrical bring-up — NOT FOR FAB

**2026-11-07. Source-backed KiCad 9 schematic, not a routed PCB or permission to power hardware.** This revision builds on PR #305 without altering the already validated MP8759 5V→~4.04V and SGM2590 USB host switch circuits.

## What is physically connected in the same native KiCad schematic

| Physical CM5 pin | V2.21 function | Connected path |
| --- | --- | --- |
| 106 | 5V_HDMI | Original 5V input rail through R7 0 Ω to a separate 5V_HDMI net |
| 99 | PWRON_L | R8 100 Ω to SW1 normally-open button to GND |
| 92 | RESET_L | R9 100 Ω to SW2 normally-open button to GND |
| 93 | SARADC_VIN0_BOOT | R10 100 Ω to SW3 Maskrom button to GND |
| 226 | SARADC_VIN1_KEY/RECOVERY | R11 100 Ω to SW4 recovery button to GND |

Radxa's carrier board design note v1.0 §3.1 says that if VCC_SYSIN is below 5 V, the module needs an independent 5 V feed at physical contact 106. Its V2.21 pinout labels 106 **5V_HDMI**. It must NOT be wired to the ~4 V VCC_SYSIN rail. The four controls follow the momentary-to-ground / 100 Ω schematic topology in Radxa CM5 IO V2.2 sheet 19; no key/ESD footprint has been qualified.

## Independent KiCad evidence

- The exported native KiCad XML netlist records the 5 V connection through R7 and four button circuits.
- 143 original connected contacts retained, 23 additional contacts newly connected.
- Actual KiCad 9.0.2 ERC: **167 open pins, 24 undriven signal inputs, 3 undriven power inputs, 35 library-symbol warnings, 3 footprint-library warnings**. ERC is intentionally **not clean**; these are release blockers.
- All 300 symbol contact names remain from the corrected V2.21 manufacturer map. Pin 290 remains NC.
- The new independent Python gate rejects an altered regulator/USB switch, wrong 5 V contact, shorting the 5 V and 4 V rails, omitted key series networks and fabrication claims.
- KiCad schematic, original KiCad XML export, actual ERC report, and machine-readable receipt are checked in. The dedicated GitHub CI validates the committed evidence and regenerates the schematic deterministically; actual KiCad export was performed on the authorized Optiplex.

## Remaining hard blockers

**Power integrity.** Radxa recommends a 4 V, 3 A supply to the CM5. The MP8759's published minimum input is 4.5 V, so a nominal 5 V jack is insufficient evidence that VIN remains above the operating limit during CPU/USB transients. At a purely illustrative 90% buck efficiency, a 12 W CM5 load plus USB at 1.5 A (~7.5 W) implies about 4.2 A from a nominal 5 V source *before* other load and losses. Measure supply, input connector, wires, transient droop, ripple, inductor saturation and thermal behavior. This is not a completed current budget.

**Domain sequencing and ESD.** GPIO_VREF, VCCIO_FLASH, boot state and output-domain loading are not yet qualified; neither input overcurrent/reverse-polarity protection nor USB data ESD is populated. The four button footprints, debounce behavior, external controls and ESD remain unqualified.

**Physical mating.** The older Radxa CM5 IO reference includes a 200-contact Hirose connector grouping plus a 100-contact grouping, not necessarily three individually routable 100-pin footprints. The three-unit 300-pin *schematic symbol* is not the mechanical mating design. Verify the exact V2.21 component drawing, plugs/receptacles, contact-to-pad numbering, mating height, location, mounting holes, plating and accessible stock before placing a PCB.

**Fab path.** Select actual vendor MPNs with validated KiCad symbols/footprints and STEP models, create a real PCB, run complete ERC/DRC, power/thermal/SI checks, then use staged current-limited physical tests. No PCB has been fabricated or powered.

## Manufacturer evidence

- Radxa V2.21 module documents: https://docs.radxa.com/en/som/cm/cm5/download
- Radxa carrier design note §3.1: https://dl.radxa.com/cm5/radxa_cm5_carrier_board_design_note.pdf
- Official Radxa IO V2.2 schematic, sheet 19: https://dl.radxa.com/cm5/v2200/radxa_cm5_io_v2200_schematic.pdf
- Radxa 4 V 3 A recommendation: https://docs.radxa.com/en/som/cm/cm5
- MP8759 datasheet: https://www.monolithicpower.com/en/documentview/productdocument/index/version/2/document_type/Datasheet/lang/en/sku/MP8759GD-Z/document_id/1011/
- Active SGM2590: https://www.sg-micro.com/product/SGM2590
- Hirose 100-position receptacle (candidate, not qualified): https://www.hirose.com/en/product/p/CL0684-4033-4-51

## Reproduction

Run the generator from the repository root with Python 3 and then use KiCad 9 to export the new schematic netlist and ERC; validate with the independent gate. KiCad ERC currently exits nonzero by design and must not be suppressed as a green pre-fab result. See the CI workflow for explicit gate arguments.

**No power-on, procurement, footprint compatibility, PCB routing, DRC or fabrication authorization.**
