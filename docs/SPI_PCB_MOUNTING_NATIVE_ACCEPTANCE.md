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

## Still required for a physical prototype

Independent confirmation of fastener geometry, screw head/washer and assembly
access; connector J1 and JP1 clearance and wiring; actual PCB and component
STEP models; lid/open-top decision, resin/FDM process, material selection,
and exact 3D interference checking. Only then should a separately authorized
physical test-fit and electrical bring-up be undertaken.

None of the tooling here grants fabrication, power-on or release authority.
