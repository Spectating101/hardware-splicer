# Mecha-Splicer Bundle: HS-POCKET-SSH-DUAL-TOUCH-S2

## Outputs
- `base_shell.scad`
- `lid_shell.scad`
- `clamshell_open_preview.scad`
- `dual_touch_visual_preview.scad`

## BOM
- 2× Waveshare ESP32-S3-Touch-LCD-4.3 (ESP32-S3 N16R8, 800x480 touch 106.1x67.8mm)
- 1× RS485 differential pair + verified common reference (2-wire A/B HY2.0 2P plus safe shared power ground)
- 1× Hinge flexible wire and protection (RS485 + potential 5V/GND power cable; test flex radius)
- 1× steel hinge pin (2.0mm diameter, ~120.0mm long)
- 1× dual-touch keyboard-half base tray (PETG base_shell.stl)
- 1× dual-touch upper display lid tray (PETG lid_shell.stl)
- 1× USB-powered dual-prototype supply (5V 2A or higher verified, two USB-C power leads)
- 0× optional protected Li-ion cells (3.7V single cell PER board, PH2.0 polarity to verify)

## DFM Notes
- [warn] NOT FIT-VERIFIED: board Z, screw mounts, USB access, lid retention, hinge life/cable bend, battery
- [warn] NOT ELECTRICALLY VERIFIED: two SP3485 RS485 A/B ports, termination, half-duplex communication and common-ground/power reference
- [warn] NOT PHYSICALLY VERIFIED: second Waveshare LCD module mounting Z/USB and touchscreen closure clearance
- [warn] NOT FUNCTIONALLY VERIFIED: LVGL virtual keyboard, Ctrl/Esc/Alt/Tab, framed RS485 key events, SSH pinned host key and reconnect
