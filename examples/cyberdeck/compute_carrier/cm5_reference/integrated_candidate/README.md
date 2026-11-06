# CM5 integrated power/USB carrier schematic — physical contact truth gate

**2026-11-07. Source-proven *schematic study*; NOT a routed, fab-ready
motherboard.** Stacked on PR #304's active SGM2590 USB switch and MP8759
reference regulator.

## What is physically integrated in KiCad

- `CM5_FULL_SYMBOL_POWER_USB_NOT_FOR_FAB.kicad_sch`: native KiCad 9
  schematic with **three actual units** of the 300-contact manufacturer
  Radxa CM5 V2.21 symbol **U3**, plus unchanged MP8759 5V→4V buck,
  in-production SGM2590 switched USB host VBUS, USB-A connector,
  resistor/inductor/capacitor network and bench supply.
- This is the **same electrical schematic** as the power stage, *not* a
  logical six-signal connector alone. Previous J2 remains a convenient
  six-wire **logical harness/test interface**; it is **not a substitute**
  for the real 300-pad physical module or a final production connector.
- U3 manufacturer source electrical contacts tied in the KiCad actual XML:
  **77/79/81/83/85/87** all `VCC_SYSIN`, **76 physical GND contacts**,
  USB host VBUS enable **97**, USB2 Host0 D+ **263**, D- **265**.
  Other nonessential/unqualified signals remain open, rather than being
  given guessed routes or suppressing their ERC errors.
- `CM5 V2.21 pin 290` remains **NC**, despite the older Radxa v2200
  reference carrier routing it as `RTC_32K_SOC`; the revision-specific
  discrepancy remains under investigation.

## Native verified evidence

`INTEGRATED_NATIVE_NETLIST.xml` was exported using
`kicad-cli sch export netlist --format kicadxml` on the connected
Optiplex (KiCad 9.0.2). `INTEGRATED_ERC_OPEN.txt` is a real independent
KiCad `sch erc` output. The SGM2590/MP8759 regulator stage's **all
existing source-backed nets were preserved**, and the only electrical
additions are approved U3 pin identities.

KiCad ERC **not clean**, correctly:

- 172 unconnected contacts (the optional/unqualified module pins)
- 26 inputs with no driver (unqualified power/boot/reset/other IO)
- 4 power inputs not driven by validated supply signals
- 26 symbol library-table registration issues on this runner
- 3 connector footprint library-table issues
- **No mixed-net-label, pin-to-pin conflict, off-grid or unconnected
  wire-end electrical errors**.

This is NOT a full, approved schematic: the power flags of the regulator
stage do not guarantee the CM5's other supply/IO voltage domains or boot
sequence. The 300-pad connector footprint's mechanical board placement,
height, stacked mating connector, high-speed routing and full ERC/DRC
remain missing. The separate logical J2 harness is not a safe 300-pin
adapter. **No fabrication or power-on authority.**

## Reproduce

```bash
python3 scripts/hs_cm5_integrated_power_usb_schematic.py \
  --out examples/cyberdeck/compute_carrier/cm5_reference/integrated_candidate/CM5_FULL_SYMBOL_POWER_USB_NOT_FOR_FAB.kicad_sch \
  --contract examples/cyberdeck/compute_carrier/cm5_reference/integrated_candidate/integrated_sgm2590_source_contract.json \
  --pinout examples/cyberdeck/compute_carrier/cm5_reference/vendor_pin_names.json \
  --symbol examples/cyberdeck/compute_carrier/cm5_reference/HS_CM5_OFFICIAL.kicad_sym \
  --report /tmp/hs_cm5_integrated_manifest.json

kicad-cli sch export netlist --format kicadxml \
  examples/cyberdeck/compute_carrier/cm5_reference/integrated_candidate/CM5_FULL_SYMBOL_POWER_USB_NOT_FOR_FAB.kicad_sch \
  -o /tmp/cm5_integrated.xml

kicad-cli sch erc \
  examples/cyberdeck/compute_carrier/cm5_reference/integrated_candidate/CM5_FULL_SYMBOL_POWER_USB_NOT_FOR_FAB.kicad_sch \
  -o /tmp/cm5_integrated_erc.txt

PYTHONPATH=src python3 -m hardware_splicer.cm5_integrated_reference_gate \
  --integrated /tmp/cm5_integrated.xml \
  --reference examples/cyberdeck/compute_carrier/cm5_reference/sgm2590_candidate/CM5_SGM2590_NATIVE_NETLIST.xml \
  --pinout examples/cyberdeck/compute_carrier/cm5_reference/vendor_pin_names.json \
  --erc /tmp/cm5_integrated_erc.txt \
  --manifest examples/cyberdeck/compute_carrier/cm5_reference/integrated_candidate/integration_manifest.json \
  --output /tmp/cm5_integrated_gate.json
```

The independent validator refuses missing/scrambled GND and 4V module
contacts, D+/D- swapping, accidental powered NC290, changed reference
regulator/switch components, altered manufacturer pin names and false
fab-readiness claims. **96 focused tests pass locally**, including the
full upstream CM5 source/footprint and switch chain.

## Next engineering focus

Complete **boot/reset/flash/EEPROM** configuration and other critical module
IO voltage domains with the latest *matching* Radxa carrier hardware
revision, integrate input reverse-polarity/overcurrent protection, USB
data ESD, qualify available resistor/inductor/capacitor footprints and
mechanical 300-pin mating stack. Then independently run **complete KiCad
ERC/PCB DRC**, power integrity/thermal studies, PCB layout, and physical
load+Linux boot testing. This is the first *single-schematic integration*
milestone, not a finished manufactured PC.
