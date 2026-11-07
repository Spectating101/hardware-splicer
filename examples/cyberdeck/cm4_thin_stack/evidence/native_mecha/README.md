# Mecha-Splicer Bundle: HS-CM4-LITE-2-THIN-TOUCH

## Outputs
- `base_shell.scad`
- `lid_shell.scad`
- `clamshell_open_preview.scad`
- `dual_touch_visual_preview.scad`

## BOM
- 1× Raspberry Pi CM4102000 wireless Lite 2GB (55x40mm CM4 with 1.5mm option mated stack 5.078mm)
- 2× Winstar WF50DTYA3MNG10-000 (127.6x73.3x3.45mm 2-lane DSI projected capacitive touch)
- 1× custom CM4 dual-DSI carrier (nominal 0.8mm PCB with 2x100-pin 0.4mm-pitch mating)
- 1× protected battery and charger (80x50x6mm naked cell placeholder, NOT approved pack)
- 1× mechanical hinge and two display ribbon cables (hinge FPC bend radius, EMI, connector and fatigue unqualified)
- 1× CM4 dual-touch lower enclosure (HS native Mecha-Splicer shell, FDM 1.6mm floor)
- 1× CM4 dual-touch upper enclosure (HS native Mecha-Splicer shell, FDM 1.6mm floor)

## DFM Notes
- [warn] Closed gap may pinch keys and cable
- [warn] NOT FIT-VERIFIED: board Z, screw mounts, USB access, lid retention, hinge life/cable bend, battery
- [warn] CM4 DSI0/DSI1 and dual GT928 touch software, panel timing and I2C configuration NOT verified
- [warn] CM4 mated stack and dual raw panel clearances are nominal only; 18mm FDM envelope is NOT tolerance or assembly validated
- [warn] No actual backlight boost, cell BMS/swelling, hinge FPC/strain relief or full part BREP collision proof
