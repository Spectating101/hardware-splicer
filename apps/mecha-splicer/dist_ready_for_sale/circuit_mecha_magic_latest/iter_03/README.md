# Mecha-Splicer Bundle: smart_sensor_node_mecha

## Outputs
- `enclosure.scad`
- `pt_base.scad`
- `pt_bracket.scad`
- `pt_platform.scad`
- `pt_preview.scad`

## BOM
- 4× M3 screws (M3×12)
- 4× M3 heat-set inserts (M3 heat-set)
- 4× rubber feet (self-adhesive)
- 1× servo (pan) (SG90)
- 1× servo (tilt) (SG90)
- 1× M3 screws (assorted)
- 8× M3 nuts (hex)

## DFM Notes
- [info] Tilt torque sanity: moment≈0.18 N·m vs servo stall≈0.18 N·m (SG90).
- [warn] Tilt payload moment is high relative to servo; reduce payload/offset or use stronger servo.
- [info] Professional mode: consider thicker base/bracket plates (>=8mm) for stiffness.
