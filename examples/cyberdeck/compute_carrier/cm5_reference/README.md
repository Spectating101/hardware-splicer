# HS Compute Carrier — CM5 manufacturer-verified KiCad contact staging

**2026-11-07 | Engineering experiment, not a manufacturable board.**

This is the first native ECAD output from the HS donor/compute-carrier
research series: a Radxa CM5 V2.21, **300-contact** KiCad symbol with every
contact label reconstructed from **Radxa's own XLSX pinout**, accompanied by
the 300-pad/4-NPTH community footprint and a native KiCad inspection PCB.

## Concrete result on connected Optiplex, KiCad 9.0.2

- **Official pinout**: three sheets U13-A (1–100), U13-B (101–200), and
  J1 (1–100, translated to global 201–300). All **300/300 contacts** loaded.
- **Community symbol**: 300 numbered pins. **192/300 contact names differ**
  from official manufacturer labels; **22 changed contacts are actually
  designated NC by the manufacturer**. Another 18 NC contacts agreed, for
  40 total manufacturer NC entries. This is not merely harmless renaming.
- **Community footprint**: 300 distinct numbered SMD pads **plus four
  unnumbered NPTH mounting holes**. Native KiCad `pcbnew.FootprintLoad`
  successfully parsed it.
- **Corrected symbol**: 300/300 names equal the manufacturer's V2.21
  table after rewriting; original community symbol footprint typo
  `Radax:Radxa_CM5` corrected to
  `HS_CM5_OFFICIAL:Radxa_CM5`. Two unsubstantiated "600mA Max" annotations
  explicitly relabeled as "MAX CURRENT NOT VERIFIED".
- Native **KiCad CLI successfully exported all three symbol-unit SVGs**.
- **Native KiCad PCB staging file**:
  `FOOTPRINT_ONLY_NOT_CONNECTED.kicad_pcb`. One imported footprint,
  300 numbered electrical pads, 4 mounting holes, *no netlist, no tracks*.
  `kicad-cli pcb drc` reported **0 violations/0 unconnected items** on this
  intentionally **unconnected** board. This says KiCad can parse the
  footprint geometry; it does **not** mean we have a powered/routed design.
- Local offline source-integrity suite: **12 tests passed** on the source
  branch before PR CI. Actual manufacturer spreadsheet and upstream library
  files also passed the pinned-SHA source generation run.

## Verified source provenance

| Artifact | Origin | SHA256 |
|---|---|---|
| Manufacturer **V2.21 pinout** | [Radxa XLSX](https://dl.radxa.com/cm5/v2210/radxa_cm5_v2210_pinout.xlsx) | `191052d98a057384b6659bab2626aae81cfc6b565f3216f20433c26046029b9c` |
| Community original symbol | [swdee/radxa-cm5-kicad](https://github.com/swdee/radxa-cm5-kicad/tree/33add7f768b313ddef58c81eca8f2d1c8004ac66) | `389141960fdc4f4023b631edec4e0002edf962d79d4be56dca786b81c606954c` |
| Community 300-pad footprint | Same MIT-licensed repository | `92d2f4aca9df8f6723458639537c99e17396198f986d7e7258f4a7b567bb2439` |

The upstream MIT license is retained in `UPSTREAM_LICENSE_MIT.txt`.
The authoritative contact mapping is a derived manufacturer signal table
`vendor_pin_names.json`. **The manufacturer's XLSX is NOT vendored** into
the repository; the audit downloads the spreadsheet from Radxa and requires
its pinned SHA256. It will **fail closed** on changed revisions, broken
numbering or lost pads, rather than silently guessing a pin function.

## Reproduce

From the root of HS, with working internet:

```bash
mkdir -p /tmp/hs-cm5-source /tmp/hs-cm5-generated
curl -fL --retry 2 https://dl.radxa.com/cm5/v2210/radxa_cm5_v2210_pinout.xlsx -o /tmp/hs-cm5-source/official.xlsx
curl -fL --retry 2 https://raw.githubusercontent.com/swdee/radxa-cm5-kicad/33add7f768b313ddef58c81eca8f2d1c8004ac66/symbols/Radxa_CM5.kicad_sym -o /tmp/hs-cm5-source/original.kicad_sym
curl -fL --retry 2 https://raw.githubusercontent.com/swdee/radxa-cm5-kicad/33add7f768b313ddef58c81eca8f2d1c8004ac66/footprints/Radxa_CM5.kicad_mod -o /tmp/hs-cm5-source/original.kicad_mod

PYTHONPATH=src python3 -m hardware_splicer.cm5_pinout_audit \
  --official /tmp/hs-cm5-source/official.xlsx \
  --symbol /tmp/hs-cm5-source/original.kicad_sym \
  --footprint /tmp/hs-cm5-source/original.kicad_mod \
  --output-dir /tmp/hs-cm5-generated
PYTHONPATH=src python3 -m pytest -q tests/test_cm5_pinout_audit.py
kicad-cli sym export svg examples/cyberdeck/compute_carrier/cm5_reference/HS_CM5_OFFICIAL.kicad_sym -o /tmp/hs-cm5-symbols
python3 scripts/hs_cm5_footprint_fixture.py \
  --library examples/cyberdeck/compute_carrier/cm5_reference/HS_CM5_OFFICIAL.pretty \
  --out /tmp/hs-cm5-generated/FOOTPRINT_ONLY_NOT_CONNECTED.kicad_pcb
kicad-cli pcb drc /tmp/hs-cm5-generated/FOOTPRINT_ONLY_NOT_CONNECTED.kicad_pcb
```

Use KiCad `sym-lib-table`/ `fp-lib-table` to register these libraries when
adding to a **new, separately reviewed schematic**. The symbol's pin
**electrical types** were inherited from the community source and have
**not** been audited against V2.21; only numbers and names have been
verified. Treat the symbol as a traceable contact-identity fixture until
types and physical connector stack-up are independently validated.

## Device interface candidate

`candidate_interfaces.json` groups exact manufacturer contact numbers
for **USB2 HOST** (four DP/DM contacts), **debug UART2** (two signals),
**HDMI** (15 labeled contacts) and candidate **system power/grounds**.
Those are pin-name matches only. **Do not connect** `VCC_SYSIN`,
`5V_HDMI`, `VCC_3V3_S3` or other supply pins on the basis of that table:
the needed regulator limits, 5V HDMI direction, surge protection, rail
sequencing, and current constraints must come from the official CM5
reference carrier schematic, not substring classification.

## Hard stop and next real engineering step

**No fabrication, board powering, firmware operation, serial testing or
high-speed layout is authorized.** The staging PCB has no electrical nets
by design, so its clean DRC is **not a completed-board DRC success**.

The next concrete phase is to derive a minimal carrier **from Radxa's
official CM5 IO V2.2 power/USB/HDMI schematic**, keeping its verified
regulators, connectors, and high-speed routing rules, then run full
schematic ERC, PCB DRC, independent signal-integrity review, physical
connector fit, safe power-up and verified boot on a real board. Do not
blindly generate high-speed routing using HS's generic 2-layer PCB path.

