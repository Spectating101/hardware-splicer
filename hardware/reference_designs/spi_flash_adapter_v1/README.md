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
- `R1`: removable host-power/current-measurement link, initially DNP.
- `R4`: removable DUT-domain isolation/current-measurement link, initially DNP.
- `R2/R3`: 10 kOhm defined-high bias for IO2/WP# and IO3/HOLD#.
- `R5`: 10 kOhm host-CS pull-up to **HOST_3V3 upstream of R1**. A powered host's
  CS signal therefore cannot feed the isolated board supply through this resistor.
- `R6`: 10 kOhm DUT-CS pull-up to DUT_1V8, maintaining deselection while U1 is disabled.
- `R7`: 10 kOhm OE pull-down. `JP1` is a normally open, two-pin enable header;
  no shunt is fitted or supplied in the initial assembly variant.
- Local regulator, translator, and flash decoupling with individual short ground-via
  escapes, two filled ground zones, and twenty ground stitching vias. Signals route on
  the front layer; the back layer is reserved for an uninterrupted ground reference.
- Eighteen test pads, including local ground pads and OE, and four M3 mounting holes.
- A 90 mm by 50 mm two-layer probing-oriented PCB.

The initial proposed transaction is read-only command `0x9F` at 5 MHz, SPI mode 0. Program, erase,
status-write, and reset commands are outside the first-use procedure.

Revision 0.2 corrects the original revision's automatic enable, absent CS bias, long
ground-return tree, incomplete read timing calculation, and unbound design-rule checks.
These are design corrections based on model review; human EE sign-off remains incomplete.

## Evidence basis

The selected topology is tied to frozen manufacturer-document identities in
`design_manifest.json`:

- Winbond W25Q128JW Revision G, including the 1.7-1.95 V operating range, SOIC-8 pinout,
  any-pin absolute maximum of VCC + 0.4 V, timing, and DC-current tables.
- TI TXU0304 SCES935A Revision A, including the PW pinout, 3+1 fixed direction map,
  supply range, output-enable behavior, and propagation-delay table.
- TI TLV755P SBVS320D Revision D, including the DBV pinout, fixed 1.8 V orderable device,
  500 mA rating, and capacitor requirements.

`HardwareSplicer.kicad_sym` contains project-local TXU0304PW and W25Q128JWS symbols.
U1 has the actual input and three-state output types, so ERC sees the fixed directions.
U2 points to the JW manufacturer datasheet and uses its SOIC-8 pinout. The selected IQ
suffix has QE fixed high: IO2/IO3 bias is **not hardware write protection**. The initial
read-only restriction is an operating procedure, not a hardware command filter.

## Current machine checks

Run:

```bash
python3 verify_design.py
```

The verifier fails closed unless all of the following are zero:

- schematic ERC errors and warnings;
- actionable PCB DRC violations;
- unconnected PCB pads;
- PCB footprint errors;
- schematic-to-PCB parity issues.
- independent required-topology, complete BOM identity/quantity/footprint, board MPN,
  initial assembly, and ground-reference contract issues.

`verification.json` binds those results to hashes of the canonical schematic, routed PCB,
BOM, design manifest, project rules, symbol library/table, and verification logic.
KiCad 9.0.2 produced the checked-in receipt. Structured native ERC/DRC JSON must match
the recognized schemas and stdout counts; missing arrays, unknown severities, exclusions,
unrecognized violation types, and mismatched counts fail closed.

KiCad's `lib_footprint_mismatch` is advisory only for a specifically identified footprint
whose installed-library and embedded pad stacks independently match: pin numbers, positions,
sizes, shapes, drill, layers, orientation, corner geometry, and mask/paste overrides.
Every other difference or violation is fatal. Non-pad graphics differences are recorded in
the receipt. This accommodates library-revision graphics drift without a blanket waiver.

The back ground fill must form one connected outline covering over 3000 mm2; both sides
must be filled, and each IC and bypass-capacitor ground pad must have a ground via within
2 mm. Non-ground routing on the back layer is rejected. These geometric checks do not prove impedance, return current distribution, or
signal integrity. The read-return budget now includes the outward clock translator:
`100 - 19 - 6 - 15 = 60 ns`, before interconnect, load, skew, and host setup terms.

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
Freerouting's zone/clearance diagnostics are printed separately. KiCad refills the ground
zones after importing the session and is the acceptance check for the canonical result.

## Review/manufacturing package

```bash
python3 build_package.py --output out/spi_flash_adapter_v1-review-package.zip
```

The package contains the canonical KiCad sources, design/BOM/verification records,
schematic and top-layer SVGs, copper/mask/paste Gerbers, separated plated/non-plated drill files, placement
CSV, and a per-file SHA-256 list. KiCad wall-clock fields and ZIP timestamps are normalized,
so repeated packaging of the same canonical inputs is byte-identical. These files remain
review inputs only; their
presence does not set `fabrication_ready` to true. The assembly BOM marks R1/R4 DNP and
the surface-mount placement export excludes them. J1/JP1 are through-hole parts, fitted
separately; JP1's header is fitted but its enable shunt is absent.

## Controlled physical handoff

The following is a proposed bench procedure for independent review, not a power-on
authorization. Record the exact host, instrument setup, current limits, and acceptance
values before execution. Use a common ground first; keep the host supply and bench supply
from being connected together through R1.

1. Independent EE review of the frozen schematic, PCB, BOM, and manufacturer claims.
2. Fabricator review of minimum 0.15 mm neck-down, 0.20 mm clearance, 0.30 mm minimum
   drill, footprints, stackup, and assembly constraints.
3. Assemble with `R1` and `R4` DNP, `JP1` open, and J1 disconnected. Verify the actual
   flash marking/package and all component orientations.
4. Perform cold shorts/resistance/continuity checks against the revision-bound netlist,
   including OE-to-ground pull-down and each CS-to-own-domain pull-up.
5. With R1 open, connect bench ground and apply 3.3 V **to R1 pad 2 / TP2 (3V3)** through
   an ammeter. R1 pad 1 / J1 pin 1 (HOST_3V3) stays isolated. A proposed initial limit is
   10 mA. Check 3V3 = 3.20–3.40 V, unloaded 1V8 = 1.75–1.85 V, and no limit activation.
6. Turn power off and confirm discharge before fitting R4. Leave R1 and JP1 open.
   Restart at a proposed 50 mA limit. Check 1V8 and DUT_1V8 = 1.75–1.85 V and no limit
   activation. Capture rail ramp/overshoot as well as DC voltage; the flash operating
   range is 1.7–1.95 V, and the DC checks alone do not demonstrate a clean ramp.
7. With JP1 still open, connect the **powered** 3.3 V host to J1, common ground first.
   Keep R1 open so the host rail supplies R5 but does not parallel the bench supply.
   Configure mode 0, SCLK low, MOSI low, and CS high; verify host CS and DUT CS at
   TP9/TP10 and OE low at TP16. Do not attach an unpowered host to a driven interface.
8. Only after DUT VCC has stayed above 1.7 V for **at least 20 us**, rail checks have
   passed, and host CS is high, deliberately bridge JP1. The manual rail-check interval
   is much longer than 20 us, but the timing requirement still applies to any future
   automated enable. A fitted jumper at startup defeats this control and is forbidden
   by this procedure. Verify OE high and DUT CS still high before clocking.
9. Capture current, temperature, supply and SPI waveforms using nearby ground pads.
   Issue only read-only `0x9F` at 5 MHz and compare the observed ID with `EF6018`.
10. With CS high, open JP1 before power-down. Change R1/R4 only with power off. Before
   restarting, confirm DUT VCC below 0.8 V for at least 100 us. Do not inject external
   voltage into DUT_1V8 while U3 is unpowered; its reverse-current behavior is not protected
   or validated here. Record rail decay, including VOUT versus VIN, for EE review.
11. Persist instruments, calibration, raw captures, board revision/hash, operator, and result
   through the existing Hardware Splicer bench evidence contract.

Until that sequence is reviewed and completed, physical correctness remains `UNPROVEN`.

## Remote FCT and Gauntlet campaign

For execution by a PCBA functional-test service or remote laboratory, build the deterministic
campaign projection:

```bash
python3 build_remote_fct_campaign.py \
  --output out/spi-flash-adapter-v1-remote-fct.zip
```

The outer archive contains the actual byte-bound fabrication, assembly, BOM, placement,
schematic and bounded host-test artifacts—not only metadata references—plus native KiCad
reports, the historical Astra source packet, an implementation-specific physical packet,
provider return template and `PACKAGED_NOT_PHYSICAL` Gauntlet state. Contact data and vendor
credentials are excluded. A successful build does not authorize fabrication or power.
