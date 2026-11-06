# HS CM5 Bench Bring-up Harness: first connected electrical schematic

**2026-11-07, KiCad 9.0.2 on the Optiplex. NON-FABRICATION RESEARCH FIXTURE.**

This is the first **connected KiCad schematic** in the HS CM5 architecture work,
building on PR #300 (source-verified 300-pin symbol) and PR #301 (manufacturer
reference-carrier 241-contact routed endpoint map). It is **not** an integrated,
power-qualified, manufacturable motherboard.

## Actual native ECAD files

- `CM5_BENCH_HARNESS_NOT_FOR_FAB.kicad_sch`: complete 3-unit 300-pin Radxa
  CM5 symbol, wired to an external bench power connector J1, USB data-only
  connector J2, UART probe connector J3, and illustrative bulk/high-frequency
  decoupling C1/C2. Maintains intentional manufacturer `NC` markings.
- `CM5_BENCH_HARNESS_NETLIST_EVIDENCE.xml`: **genuine**
  `kicad-cli sch export netlist --format kicadxml` output.
- `CM5_BENCH_HARNESS_ERC_OPEN.txt`: **genuine**
  `kicad-cli sch erc` report, including all its errors/warnings.
- `bench_harness_native_validation.json`: independently verified reference
  net intersections, required CM5 contacts, and unresolved checks.
- `scripts/hs_cm5_connected_bench_schematic.py`: reproducible KiCad-native
  schematic generator using official 300-name manufacturer manifest,
  source-audited CM5 KiCad library, and KiCad standard Device/Connector symbols.
- `src/hardware_splicer/cm5_bench_netlist_gate.py`: fail-closed checker for
  the *actual KiCad export*, not a label-connectivity guess.
- `tests/test_cm5_connected_bench_schematic.py`: adversarial checks that
  detect swapped D+/D-, missing power contact, J1 input/ground cross-wiring,
  accidental connection to pin 290 and attempts to hide incomplete ERC.

## Grounded power / USB design constraints

[Radxa official CM5 hardware specs](https://docs.radxa.com/en/som/cm/cm5)
specify **CM5 MODULE `VCC_SYSIN` range 3.6–5.2 V, 4 V recommended, 2 A
typical, 4 V/3 A recommended carrier regulator**. This is NOT the same as the
**external 12 V input** on Radxa's 160×90 mm CM5 IO reference board, which
has its own [12V→5V→4V conversion circuit](https://dl.radxa.com/cm5/io_board_v2200/radxa_cm5_io_board_v2200_schematic.pdf)
(page 15 of 19). **Never connect a 12 V adapter to the new J1 harness**.

This bench harness accepts a **laboratory-regulated externally current-limited
4 V supply only**. It has **no integrated regulator, battery, charger, PD
controller, DC jack protection or current-rated assembly**. C1=22µF/10V and
C2=100nF/10V are *candidate* decouplers; value/ESR, footprint, additional
capacitors and close placement still require the official circuit's design
review.

[Official CM5 USB reference](https://dl.radxa.com/cm5/io_board_v2200/radxa_cm5_io_board_v2200_schematic.pdf)
(page 13) employs SGM2576 USB 5 V power switching, ESD protection and
common-mode filtering. These are **not installed in the HS schematic**:
J2 carries **D+ / D- / ground only**, and must *not* be misrepresented as a
usable USB port. USB host logic remains untested.

## Real KiCad netlist verification

| Qualified logical segment | KiCad actual net members |
|---|---|
| `/VCC_SYSIN` | J1.1, C1.1, C2.1, CM5 U1 pins **77,79,81,83,85,87** |
| `/GND` | J1.2, J2.3, J3.3, C1.2, C2.2, **all 76 CM5 GND contacts** |
| `/USB20_HOST0_DP` | CM5 **263** to J2.1 |
| `/USB20_HOST0_DM` | CM5 **265** to J2.2 |
| `/UART2_TX_M0` | CM5 **55** to J3.1 |
| `/UART2_RX_M0` | CM5 **51** to J3.2 |

The netlist shows **4 V and ground are separate**; all six `VCC_SYSIN`
contacts are present. **Pin 290 stays unconnected**, because official
CM5 V2.21 says `NC` while older reference carrier v2200 routes it to
`RTC_32K_SOC` (PR #301). This discrepancy remains unresolved.

**On purpose, KiCad ERC is not clean:**

- 172 `pin_not_connected`
- 27 `pin_not_driven`
- 5 `power_pin_not_driven` (including no regulator/power-source marker)
- 8 library-table config warnings and 3 footprint-library-table warnings
- **0 conflicting-net-label findings and 0 off-grid findings** after repair

The genuine ERC failure is a **safety gate**, not a task failure or evidence
that the module is electrically ready. Suppressing all open pins or inserting
fake power flags to obtain a green check would be misleading.

## Reproduction on a computer with KiCad 9 installed

```bash
python3 scripts/hs_cm5_connected_bench_schematic.py \
  --vendor examples/cyberdeck/compute_carrier/cm5_reference/vendor_pin_names.json \
  --symbol examples/cyberdeck/compute_carrier/cm5_reference/HS_CM5_OFFICIAL.kicad_sym \
  --connector-library /usr/share/kicad/symbols/Connector_Generic.kicad_sym \
  --device-library /usr/share/kicad/symbols/Device.kicad_sym \
  --output /tmp/CM5_BENCH_HARNESS_NOT_FOR_FAB.kicad_sch

kicad-cli sch export netlist --format kicadxml \
  /tmp/CM5_BENCH_HARNESS_NOT_FOR_FAB.kicad_sch -o /tmp/cm5_bench_net.xml
kicad-cli sch erc /tmp/CM5_BENCH_HARNESS_NOT_FOR_FAB.kicad_sch \
  -o /tmp/cm5_bench_erc.txt

PYTHONPATH=src python3 -m hardware_splicer.cm5_bench_netlist_gate \
  --netlist /tmp/cm5_bench_net.xml \
  --erc /tmp/cm5_bench_erc.txt \
  --output /tmp/cm5_bench_gate.json
```

The script output's embedded project ID is `CM5_BENCH_HARNESS_NOT_FOR_FAB`,
used by KiCad during netlist export. Do not rename arbitrary electrical
symbols by search/replace without re-exporting a new netlist.

## Next engineering release criteria

1. **Version alignment**: Manufacturer confirmation/waiver for pin 290
   `NC` vs reference carrier RTC routed signal and any other changed
   mapping; check module PCB revision.
2. **Power**: Regulator/soft-start, correct connector current rating,
   input protection, decoupling and 4 V/3 A load/thermal qualification
   derived from the official CM5 IO schematic—not an arbitrary 12 V jack.
3. **USB**: Proper host 5 V switch, VBUS enable logic, ESD protection,
   return path, connector and actual USB peripheral test.
4. **UART**: Verify logic-voltage levels, test exact adapter/interface,
   enforce safe recovery and isolation.
5. **Full schematic**: Resolve *all* required power and boot/reset
   circuits, pin electrical types, missing net connections, ERC, BOM and
   footprint assignments before physical KiCad PCB routing.
6. **Physical verification**: Real selected module SKU, carrier revision,
   controlled-impedance routing, DRC, test board, measured current/heat,
   successful Linux boot and SSH connection.

No purchase order, Gerbers, deployed board, powered electrical validation
or fabrication authorization is implied by these files.
