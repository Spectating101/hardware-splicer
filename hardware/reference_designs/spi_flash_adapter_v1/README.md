# SPI Flash Adapter v1

This directory is the first complete Hardware Splicer reference design for the frozen
3.3 V-host to 1.8 V W25Q128JW case. It contains an editable KiCad 9 schematic, a routed
two-layer PCB, an exact BOM, a machine-readable evidence/authority manifest, and scripts
that regenerate, verify, and package the work without an external design contractor.

The current artifact is a **bounded pre-fabrication result**. It is internally consistent
and reviewable, but it is not fabrication-authorized, power-on-authorized, or physically
validated.

## What is implemented

- `J1`: 3.3 V host interface ordered as 3V3, GND, CLK, MOSI, CS#, MISO.
- `U1`: TXU0304PWR with three fixed A-to-B paths and one B-to-A path.
- `U2`: W25Q128JWSIQ in the SOIC-8 208-mil package.
- `U3`: TLV75518PDBVR fixed 1.8 V regulator.
- `R1`: removable host-power/current-measurement link.
- `R4`: removable DUT-domain isolation/current-measurement link.
- `R2/R3`: 10 kOhm defined-high bias for IO2/WP# and IO3/HOLD#.
- Local regulator, translator, and flash decoupling.
- Fifteen test pads and four M3 mounting holes.
- A 90 mm by 50 mm two-layer probing-oriented PCB.

The initial permitted transaction is read-only command `0x9F` at 5 MHz. Program, erase,
status-write, and reset commands are outside the first-use procedure.

## Evidence basis

The selected topology is tied to frozen manufacturer-document identities in
`design_manifest.json`:

- Winbond W25Q128JW Revision G, including the 1.7-1.95 V operating range, SOIC-8 pinout,
  any-pin absolute maximum of VCC + 0.4 V, timing, and DC-current tables.
- TI TXU0304 SCES935A Revision A, including the PW pinout, 3+1 fixed direction map,
  supply range, output-enable behavior, and propagation-delay table.
- TI TLV755P SBVS320D Revision D, including the DBV pinout, fixed 1.8 V orderable device,
  500 mA rating, and capacitor requirements.

The KiCad symbol library has no dedicated TXU0304 symbol, so `U1` uses the
pin-compatible `TXB0104PW` graphics. The value, BOM, PCB footprint, and prominent
schematic note all bind the fitted part and the exact TXU0304 directional mapping. This
substitution is graphical only; it is not a claim that TXB0104 electrical behavior is used.

## Current machine checks

Run:

```bash
python3 verify_design.py
```

The verifier fails closed unless all of the following are zero:

- schematic ERC errors and warnings;
- PCB DRC violations;
- unconnected PCB pads;
- PCB footprint errors;
- schematic-to-PCB parity issues.

`verification.json` binds those results to hashes of the canonical schematic, routed PCB,
BOM, and design manifest. KiCad 9.0.2 produced the checked-in receipt.

## Regeneration

Schematic generation requires `kicad-sch-api==0.5.6` and KiCad 9 symbol libraries:

```bash
python3 -m venv /tmp/hs-kicad-sch
/tmp/hs-kicad-sch/bin/pip install kicad-sch-api==0.5.6
/tmp/hs-kicad-sch/bin/python generate_schematic.py
```

The PCB generator consumes KiCad's netlist exported from that schematic. This is
deliberate: a geometrically clean board is rejected if its component identity, net names,
or schematic paths do not have parity with the schematic.

Routing is pinned to Freerouting v2.4.1 and then independently accepted by KiCad. The
official `freerouting-2.4.1-linux-x64.zip` used here has SHA-256
`3ad5a956ab474b12f331d24195feadac90e8344b8e013c6a4ab26e203ce51519`.

```bash
python3 route_pcb.py --freerouting /path/to/freerouting-2.4.1-linux-x64/bin/freerouting
python3 verify_design.py
```

The router is an implementation tool, not an authority source. A routing run receives no
credit unless the imported result passes KiCad DRC, connectivity, and schematic parity.

## Review/manufacturing package

```bash
python3 build_package.py --output out/spi_flash_adapter_v1-review-package.zip
```

The package contains the canonical KiCad sources, design/BOM/verification records,
schematic and top-layer SVGs, Gerbers, separated plated/non-plated drill files, placement
CSV, and a per-file SHA-256 list. KiCad wall-clock fields and ZIP timestamps are normalized,
so repeated packaging of the same canonical inputs is byte-identical. These files remain
review inputs only; their
presence does not set `fabrication_ready` to true.

## Controlled physical handoff

When hardware access exists, the next evidence-producing sequence is:

1. Independent EE review of the frozen schematic, PCB, BOM, and manufacturer claims.
2. Fabricator review of minimum 0.15 mm neck-down, 0.20 mm clearance, 0.30 mm minimum
   drill, footprints, stackup, and assembly constraints.
3. Assemble with `R1` and `R4` initially open or removed.
4. Perform cold shorts/resistance/continuity checks against the revision-bound netlist.
5. Apply current-limited 3.3 V through an ammeter at `R1`; verify the unloaded 1V8 rail.
6. Fit/bridge `R4`, retain a conservative current limit, and verify DUT_1V8 at TP15.
7. Capture 3V3, 1V8, DUT_1V8, idle SPI levels, current, and temperature.
8. Issue only read-only `0x9F` at 5 MHz and compare the observed ID with `EF6018`.
9. Persist instruments, calibration, raw captures, board revision/hash, operator, and result
   through the existing Hardware Splicer bench evidence contract.

Until that sequence is reviewed and completed, physical correctness remains `UNPROVEN`.
