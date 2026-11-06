# HS CM5 5V -> 4V and USB host power stage: native KiCad electrical proof

2026-11-07. **Not a fabrication package, not qualified for power-up.**

This directory contains a real KiCad 9 schematic and native KiCad XML netlist,
source-gated evidence and locally verified manufacturer pin maps for a
**5V bench input → regulated nominal 4V CM5 rail**, plus a 5V USB Type-A
VBUS switch controlled by the CM5.

## Actual source and parts

- [Radxa CM5 IO V2.2 manufacturer schematic](https://dl.radxa.com/cm5/v2200/radxa_cm5_io_v2200_schematic.pdf), **sheet 15**: an MP8759GD-Z down-converter between `VCC5V0_SYS` and `VCC_SYSIN` with 1.5µH output inductor, 47k/8.2k feedback divider, input capacitors, bootstrap and output decoupling. Sheet 13: SGM2576 switched USB host VBUS and ESD/filtering.
- [MP8759 manufacturer datasheet](https://www.monolithicpower.com/en/documentview/productdocument/index/version/2/document_type/Datasheet/lang/en/sku/MP8759GD-Z/document_id/1011/): pins 1 VIN, 2 PGND, 3 PG, 4 NC, 5 VOUT (sense!), 6 MODE, 7 SW, 8 BST, 9 VCC, 10 AGND, 11 FB, 12 EN. VIN range 4.5–26 V. Reference 0.6 V feedback.
- [SGM2576 vendor datasheet](https://www.sg-micro.com/rect/assets/281ce0d1-eaf9-4b8e-97e0-dc17087ed2fe/SGM2576_SGM2576B.pdf): pins 1 VOUT, 2 GND, **3 ILIM**, 4 EN, 5 VIN; its programming equation is `I_LIM = 6800 / R_ILIM (A)`, for resistance in ohms.
- [SGMICRO product listing](https://www.sg-micro.com/product/SGM2576) currently states **SGM2576 obsolete**. The Radxa PDF labels its pin 3 `OCB`, but the vendor identifies it as `ILIM`. **Do not copy the older label into a replacement part.**

## Native artifacts

- `CM5_5V4V_USB_REFERENCE_NOT_FOR_FAB.kicad_sch`: KiCad 9 editable schematic; **21 actual schematic components**, 14 source-verified connected net groups. **No PCB tracks, Gerbers, or power-up**.
- `HS_Power.kicad_sym`: local source-pin-derived, editable MP8759 + SGM2576 symbols; `sym-lib-table` retains local and KiCad 9 stock library registry paths.
- `CM5_5V4V_USB_REFERENCE_NETLIST.xml`: native `kicad-cli sch export netlist --format kicadxml` output.
- `CM5_5V4V_USB_REFERENCE_ERC.txt`: native KiCad ERC, **no electrical short/off-grid/pin-to-pin violations**, but 23 unresolved **symbol registration warnings** on this host, so do not call ERC completely clean.
- `5v4v_usb_reference_contract.json` / `5v4v_usb_reference_validation.json` contain expected performance, source metadata, limits and disqualifying flags.
- `src/hardware_splicer/cm5_power_usb_reference_gate.py`: compares all required native netlist pin pairs and symbol pin identities exactly; rejects shorts, wrong rails, swapped USB D+/D−, missing load switch, misreported obsolescence, altered feedback ratios or bogus safety claims.
- `tests/test_cm5_power_usb_reference_gate.py`: adversarial tests; **70 focused tests pass locally** across the full CM5 source and design chain.

## Verified net connectivity

| Source net | Connected components/contacts |
| --- | --- |
| `VCC5V0_SYS` | 5 V bench J1.1, U1 VIN.1, U2 VIN.5, C1/C2/C8, EN upper resistor R3 |
| `SW_MPS` | U1 SW.7, L1.1, bootstrap C6.2 |
| `VCC_SYSIN` | L1.2, U1 VOUT sense.5, J2.1 CM5 **logical harness output**, C3/C4/C5 and feedback top R1 |
| `FB_MPS` | U1 FB.11, 47k R1.2, 8.2k R2.1 |
| `BST_MPS` | U1 BST.8, R5.1; R5.2 → C6.1 `BST_SERIES` |
| `EN_MPS` | U1 EN.12, top 510k R3.2, bottom 510k R4.1 |
| `VCC_MPS` | U1 VCC.9 and 1µF bypass C7.1 |
| `ILIM_USB` | SGM U2 ILIM.3, R6.1, 4.7k to ground |
| `USB_HOST_PWREN_H` | CM5 logical J2.5 → SGM U2 EN.4; **maps to manufacturer CM5 pin 97** |
| `USB_VBUS_SW` | SGM U2 VOUT.1 → Type A J3 VBUS.1 plus C9.1 |
| USB2 HOST0 | J2.3 → USB-A D+ J3.3 (**CM5 physical pin 263**), J2.4 → USB-A D− J3.2 (**CM5 physical pin 265**) |
| GND | shared return of J1.2, J2.2/6, USB-A J3.4, switching regulator, switch, capacitor and divider grounds |

All component pin numbers and logical nets are verified in the **actual KiCad XML export**, not merely hardcoded in the design generator. The **CM5 socket itself is not present on this schematic**: J2 is a logical harness boundary, *not a physical 300-contact adapter pinout*. The source-derived module pin mapping comes from earlier PRs #300–301.

The MP8759 feedback setting gives **0.6 × (1 + 47k/8.2k) = 4.039 V nominal**. This excludes tolerances, operating ripple, startup transient, droop and thermal conditions. The SGM2576 nominal ILIM setting using 4.7k is **6800 / 4700 = 1.447 A**, *not* a verified overload threshold. Manufacturer warns its programmable threshold has material variability.

## Safety and manufacturing blockers

1. **No actual input protection or measured regulator behavior.** Input uses externally regulated 5 V; its undervoltage headroom at 4.5 V, startup, DC/DC loop stability, ceramic capacitance derating, inductor saturation/thermal behavior and PCB copper/vias need calculations and physical characterization.
2. **Obsolete SGM2576:** qualify a supported, pin-verified switch with actual current-limit law, package and EN logic before fab. Do not silently substitute parts.
3. **No USB data ESD protection or common-mode choke on this version**, unlike Radxa's full reference. USB-A shield connection intentionally unqualified. This is a functional reference net-map, not a finished USB-compliant design.
4. **Power-tree detail:** 5V in to MP8759 is *distinct* from the 4V CM5 input. Do **not** connect 5V or 12V directly to an assumed 4V-only rail or interpret J2 as a ready-to-build connector. Battery BMS, 5V sourcing/current budget, connector selection, PD and reverse-polarity protection are not designed.
5. **No PCB/DFM:** MPS package/footprint, SGM obsolete switch footprint, trace width, 1.5µH inductor exact MPN/Isat, USB ESD/EMI, 300-pin CM5 mechanical mating and thermal control unqualified.
6. **V2.200/v2.21 mismatch:** The older reference board uses pin 290 as RTC_32K_SOC but the CM5 V2.21 pinout marks it NC. This remains blocked until revision resolution.

The generic external **5 V bench** symbolic power flags tell KiCad where an external power source is expected; they do **not** create a physical safe power system. The design's `fabrication_authorized` field remains **false**.

## Repeat electrical checks

```bash
python3 scripts/hs_cm5_5v4v_usb_power_reference.py \
  --out examples/cyberdeck/compute_carrier/cm5_reference/CM5_5V4V_USB_REFERENCE_NOT_FOR_FAB.kicad_sch \
  --manifest examples/cyberdeck/compute_carrier/cm5_reference/5v4v_usb_reference_contract.json

kicad-cli sch export netlist --format kicadxml \
  examples/cyberdeck/compute_carrier/cm5_reference/CM5_5V4V_USB_REFERENCE_NOT_FOR_FAB.kicad_sch \
  -o /tmp/cm5_5v4v_usb.xml
kicad-cli sch erc \
  examples/cyberdeck/compute_carrier/cm5_reference/CM5_5V4V_USB_REFERENCE_NOT_FOR_FAB.kicad_sch \
  -o /tmp/cm5_5v4v_erc.txt

PYTHONPATH=src python3 -m hardware_splicer.cm5_power_usb_reference_gate \
  --netlist /tmp/cm5_5v4v_usb.xml --erc /tmp/cm5_5v4v_erc.txt \
  --contract examples/cyberdeck/compute_carrier/cm5_reference/5v4v_usb_reference_contract.json \
  --output /tmp/cm5_5v4v_review.json
```

**Next engineering job:** qualify an in-production USB switch with independent datasheet and actual SOT pad assignment; add ESD/protected input and the manufacturer's exact regulator compensation/decoupling, then build a fully integrated CM5 carrier schematic with real physical connector and run complete ERC and PCB DRC.
