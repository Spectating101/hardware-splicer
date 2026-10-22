# SPI flash adapter — KiCad-driven CAD mounting revision

**Status:** candidate mechanical design; native CI must pass before claiming
verified CAD. No physical part has been built, test-fitted or powered.

## Why this revision exists

The preceding shell has a real, open cavity but no alignment or retaining
features. This revision reads the **real KiCad PCB** to place four bosses and
corresponding pilot holes in SolidCraft. The native design remains editable.
The complete output is then inspected by FreeCAD and cross-checked by HS.

Reference PCB: 90 × 50 × 1.6 mm, nominal M3 holes, with hole centers:
H1 (104,64), H2 (186,64), H3 (104,106), H4 (186,106), in source KiCad mm.
Relative to the centered board: X±41, Y±21 mm.

The source-defined shell exterior is 110 × 70 × 25 mm; cavity width/depth
are 104 × 64 mm, and nominal floor is 2 mm.

| Feature | Proposed CAD |
| --- | --- |
| Boss centers relative to shell | (14,14), (96,14), (14,56), (96,56) mm |
| Boss OD | 6.6 mm |
| Clearance bore | 3.3 mm |
| Boss top (Z from shell exterior) | 5.2 mm |
| Nominal board underside at mounting position | Z = 5.2 mm |
| Resultant wall around bore | 1.65 mm nominal radial material |
| Shell floor | 2.0 mm nominal |
| Screw/washer length and torque | Not verified |
| Connector access and lid | Not verified |

These dimensions are **design assumptions**, not verified 3D-printing
tolerances, fastener specification or electrical insulation guarantees.
A clearance bore is not a tapped/self-threading boss specification.

## Pipeline

```bash
python scripts/generate_spi_mounting_cad.py \
  --out examples/external_engines/cad/spi_adapter_with_mounts.json \
  --manifest /tmp/hs-spi-mount-requirements.json

python scripts/run_external_engine_plan.py \
  examples/external_engines/spi_adapter_mounted_shell.json \
  --workspace examples/external_engines \
  --out /tmp/hs-spi-mounted-native --execute --timeout 180

export HS_MOUNTED_SHELL_STEP=/tmp/hs-spi-mounted-native/mounted_shell/model.step
export HS_MOUNTING_REQUIREMENTS=/tmp/hs-spi-mount-requirements.json
export HS_MOUNTED_SHELL_TOPOLOGY=/tmp/hs-spi-mounted-native/MOUNTED_SHELL_TOPOLOGY.json
FreeCADCmd scripts/probe_spi_mounted_shell_native.py

python scripts/assess_spi_mounted_device.py \
  --engines /tmp/hs-spi-mounted-native \
  --manifest /tmp/hs-spi-mount-requirements.json \
  --cad-recipe examples/external_engines/cad/spi_adapter_with_mounts.json \
  --out /tmp/hs-spi-mounted-review
```

A failed native SolidCraft boolean or FreeCAD solid validation must **block**
the build; neither is replaced by a synthetic geometry model.

## Native verification demanded

1. KiCad source and generated SolidCraft script SHA-256 agree; the generator
   is independently replayed to reject altered mounting geometry.
2. SolidCraft exports an actual STEP; FreeCAD validates one solid and agrees
   on the 110 × 70 × 25 mm bounding envelope.
3. Native material volume agrees with the analytic boss/floor and cut-hole
   calculation (approximately 39,672.011 mm³, tolerance 0.1 mm³).
4. FreeCAD confirms 14 test points: 2 base-shell floor/cavity samples, and
   for each of the four anchors a solid boss annulus, an empty screw bore,
   and an empty corresponding floor through-hole.
5. The original PCB component envelope still screens clear in the proposed
   cavity. This is not a complete CAD collision or PCB-body interference
   check.

A single pass cannot imply reliable fabrication: physical sizing, connector
clearance, printer/tool process tolerances, strength and insulation remain
separate requirements. Missing or stale outputs, changed source KiCad holes,
invalid material samples or unbound FreeCAD inputs block the review.

## Source-driven connector access

The shell is currently OPEN TOP. Both fitted PCB connectors are vertical
through-hole headers: J1 (six host SPI pins) and JP1 (two enable pins).
No side-wall slots are required for this un-lidded model.

The new connector-access checker reads actual KiCad pad identities/nets,
source courtyard corners, and the KiCad-derived mounting-boss manifest.
It inflates connector courtyards by a nominal 2 mm review-only margin
and screens them against the 104 × 64 mm cavity and proposed bosses.

Reference-board shell coordinates and source-footprint envelopes:

- J1 center (15,30) mm; inflated XY rectangle X=11.23..18.77,
  Y=26.23..46.47 mm; nearest boss center separation 9.53 mm.
- JP1 center (57,48) mm; inflated XY rectangle X=53.23..60.77,
  Y=44.23..54.32 mm; nearest boss center separation 35.27 mm.
- Nominal vertical room above the top of the PCB: 18.2 mm, which
  does NOT validate the height of the actual mating header/harness.

The source footprints indicate upward mating orientation. This does
NOT authenticate connector body geometry, cable bend radius, plug
insertion force, strain relief, or any top cover/lid. Larger connector
keepout margins are intentionally allowed to fail the source review.

Run the separate inspection CLI after generating the mounting manifest:
python scripts/assess_spi_connector_access.py --mount-manifest
/tmp/hs-spi-mount-requirements.json --out /tmp/hs-spi-connector-access.json

## Real header dimensions and provisional 3D mating/service envelope

The exact fitted header identities are in the KiCad reference BOM:

- J1: Samtec TSW-106-07-T-S, vertical, 6 pins at 2.54 mm pitch.
- JP1: Samtec TSW-102-07-T-S, vertical, 2 pins at 2.54 mm pitch.
- For both: 2.54 mm header insulator height and 5.84 mm mating post length
  (source: Samtec's part pages and independent DigiKey part attributes).

The male header tip nominally reaches Z=15.18 mm (PCB underside
Z=5.2, PCB thickness 1.6, header insulator 2.54, mating post 5.84).
That puts the male pin tips **9.82 mm below the shell's 25 mm top rim**.
A suitable female connector therefore needs an accessible vertical
insertion path; the courtyard alone cannot prove this.

Provisional references for envelope investigation ONLY:

- Samtec SSW-106-02-T-S and SSW-102-02-T-S, 2.54 mm pitch single-row
  receptacles with 8.51 mm nominal insulator height. These are
  through-hole PCB-tail sockets, **not a selected cable harness**.
- The service approach corridor uses the actual KiCad connector courtyard
  expanded by an authored 2 mm review allowance, extending from above
  the header insulation to 10 mm above the open shell's rim.
- The provisional socket top would be approximately Z=17.85 mm on
  a simplified seating assumption; this is NOT a verified mated height.

Engineering truth, unlike guessed integration claims:

1. The male header dimensions are backed by named manufacturer parts.
2. The approximate 3D service corridor is an authored design hypothesis,
   not a supplier-certified female socket/cable geometry.
3. HS screens this corridor against actual PCB component-height
   approximations, proposed mounting bosses and cavity boundaries.
4. A native FreeCAD script uses a boolean intersection of the corridor
   with the actual mounted SolidCraft STEP geometry.
5. The result remains BLOCKED for qualified mating, cable routing,
   strain relief, plug orientation, insertion force and real assembly.

Commands after generating the mounted-shell manifest and native STEP:

python scripts/assess_spi_mating_volume.py --mount-manifest
/tmp/hs-spi-mount-requirements.json --out
/tmp/hs-spi-mounted-native/CONNECTOR_MATING_VOLUME.json

Set HS_MOUNTED_SHELL_STEP to the actual native mounted-shell STEP, set
HS_MATING_VOLUME_REPORT to CONNECTOR_MATING_VOLUME.json, and
HS_NATIVE_MATING_COLLISION_REPORT to an output JSON path.
Then run FreeCADCmd scripts/probe_spi_connector_access_native.py.

Documentation/data sources:

- https://www.samtec.com/products/tsw-106-07-t-s
- https://www.samtec.com/products/tsw-102-07-t-s
- https://www.digikey.com/en/products/detail/samtec-inc/TSW-106-07-T-S/1101618
- https://www.digikey.com/en/products/detail/samtec-inc/SSW-106-02-T-S/1112794
- https://www.digikey.com/en/products/detail/samtec-inc/SSW-102-02-T-S/1112798

No model should authorize printing, assembly, power or product release
until an actual mating hardware assembly is specified and checked.

## Still required for a physical prototype

Independent confirmation of fastener geometry, screw head/washer and assembly
access; connector J1 and JP1 clearance and wiring; actual PCB and component
STEP models; lid/open-top decision, resin/FDM process, material selection,
and exact 3D interference checking. Only then should a separately authorized
physical test-fit and electrical bring-up be undertaken.

None of the tooling here grants fabrication, power-on or release authority.
