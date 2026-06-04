# Build Recipe

## Outputs
- `motor_mount.scad`
- `idler_mount.scad`
- `carriage.scad`
- `belt_clamp.scad`
- `rod_holder.scad`
- `tensioner_block.scad`
- `endstop_mount.scad`
- `assembly_preview.scad`

## Procurement
- (not generated) Run with `--include-pricing` to emit buy lists.

## Evidence Bundle
- `DESIGN_DECISIONS.md`
- `SIM_RESULTS.json`
- `RISK_REGISTER.md`
- `REVISION_NOTES.md`

## Assembly (prototype-grade)
- Print base + lid; test-fit PCB/module with clearance.
- Install heat-set inserts (optional) and fasteners.
- Verify connector cutouts and cable strain relief.

## Linear axis (prototype-grade)
- Print `motor_mount.scad`, `idler_mount.scad`, `carriage.scad` (and optional tensioner/endstop parts).
- Install rods, bearings/bushings, belt, pulley, idler; tension belt.
- Check carriage moves smoothly across full travel.
- Tune accel/speed to avoid skipped steps (start conservative).
