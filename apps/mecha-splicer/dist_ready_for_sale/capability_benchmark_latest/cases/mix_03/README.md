# Mecha-Splicer Bundle: bench_mix_3

## Outputs
- `motor_mount.scad`
- `idler_mount.scad`
- `carriage.scad`
- `belt_clamp.scad`
- `rod_holder.scad`
- `tensioner_block.scad`
- `endstop_mount.scad`
- `assembly_preview.scad`
- `br_reduction_plate.scad`
- `br_preview.scad`

## BOM
- 2× smooth rod (8.0mm × 220.0mm)
- 4× linear bearing (LM8UU (or printed bushings))
- 1× GT2 belt (6.0mm width, 600mm length)
- 1× GT2 pulley (20T, 5mm bore)
- 1× idler pulley (GT2 idler, 6.0mm)
- 1× stepper motor (NEMA17 (17HS) class)
- 1× M3 screws (assorted)
- 1× endstop switch (micro-switch)
- 2× 2020 extrusion (350.0mm length)
- 8× T-nuts (M5 for 2020)
- 8× M5 screws (M5×10)
- 4× rod holders (printed)
- 8× M3 nuts (hex)
- 8× M3 screws (M3×16)
- 1× GT2 pulley (motor) (20T, 5mm bore)
- 1× GT2 pulley (driven) (60T, 5mm bore)
- 3× bearing (625ZZ (5×16×5))
- 2× shaft (5mm shaft/bolt)
- 1× GT2 belt (6.0mm width (length per center distance))
- 1× stepper motor (NEMA17 (17HS) class)
- 1× M3 screws (assorted)

## DFM Notes
- [info] Estimated rod deflection ~0.06mm (midspan, steel assumption).
- [info] Estimated torque 0.07 N·m (pulley 20T, load-only).
- [info] Accel estimate: a=600 mm/s² → +0.66N, torque≈0.07 N·m (very rough).
- [info] Reduction ratio ≈ 3.00:1 (driven/motor).
- [info] Approx belt pitch length ≈ 201 mm (open belt formula; verify).
