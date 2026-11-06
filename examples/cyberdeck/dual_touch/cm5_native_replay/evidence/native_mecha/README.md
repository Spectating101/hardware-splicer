# Mecha-Splicer Bundle: HS-CM5-POCKET-DUAL-DSI-S2

## Outputs
- `base_shell.scad`
- `lid_shell.scad`
- `clamshell_open_preview.scad`
- `dual_touch_visual_preview.scad`

## BOM
- 1× Radxa CM5 V2.21 (56x41mm SoM; board-to-board mating stack not qualified)
- 2× Winstar WF50DTYA3MNG10-000 (127.6x73.3x3.45mm 2-lane MIPI DSI capacitive touch)
- 1× custom CM5 carrier (nominal 0.8mm PCB; NO routed copper or footprint approval)
- 1× protected pouch cell and charging path (80x50x6mm nominal naked placeholder)
- 1× CM5 heat spreader (0.5mm unverified thermal pad/plate)
- 1× hinge + rated display FPC (2.0mm hinge pin, bend radius unqualified)
- 1× CM5 dual-touch lower enclosure (Native Mecha-Splicer shell, not fit qualified)
- 1× CM5 dual-touch upper enclosure (Native Mecha-Splicer shell, not fit qualified)

## DFM Notes
- [warn] Closed gap may pinch keys and cable
- [warn] NOT FIT-VERIFIED: board Z, screw mounts, USB access, lid retention, hinge life/cable bend, battery
- [warn] CM5 two independent DSI hosts: panel drivers, touch controller bus, backlight boost and FPC routing not verified
- [warn] 3.45mm real panel plus CM5 mating, heat and protection need independent Z-constraint check; native shell alone is NOT fit proof
- [warn] Ultra-thin FDM shell, hinge clearance and battery protection are NOT qualified for physical fabrication
