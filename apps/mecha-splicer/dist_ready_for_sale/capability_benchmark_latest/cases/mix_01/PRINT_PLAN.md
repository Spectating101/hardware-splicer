# Print Plan

This is a heuristic print plan. Validate critical fits and iterate.

- `motor_mount.scad`: flat_on_plate (mount)
  - Increase perimeters for stiffness; consider PETG/ABS for heat.
- `idler_mount.scad`: flat_on_plate (mount)
  - Increase perimeters for stiffness; consider PETG/ABS for heat.
- `carriage.scad`: flat_on_plate (carriage)
  - Ream rod bores if tight; keep clearance >=0.4mm for FDM.
- `belt_clamp.scad`: flat_on_plate (accessory)
  - Prototype-grade accessory; verify hole sizing.
- `rod_holder.scad`: flat_on_plate (clamp)
  - Print with high perimeters; tighten bolts gradually to avoid cracking.
- `tensioner_block.scad`: flat_on_plate (accessory)
  - Prototype-grade accessory; verify hole sizing.
- `endstop_mount.scad`: flat_on_plate (accessory)
  - Prototype-grade accessory; verify hole sizing.
- `assembly_preview.scad`: flat_on_plate (part)
- `br_reduction_plate.scad`: flat_on_plate (reduction)
  - Use rigid mounting; plate thickness matters more than infill.
- `br_preview.scad`: flat_on_plate (reduction)
  - Use rigid mounting; plate thickness matters more than infill.
