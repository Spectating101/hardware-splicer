# Mecha-Splicer Bundle: HS-POCKET-SSH-CLAMSHELL-S1

## Outputs
- `base_shell.scad`
- `lid_shell.scad`
- `clamshell_open_preview.scad`

## BOM
- 1× Waveshare ESP32-S3-Touch-LCD-4.3 (4.3 inch 800x480, N16R8, 106.1x67.8mm touch version)
- 1× M5Stack CardKB v1.1 (88x54x5mm 50-key QWERTY I2C @0x5F; 5V)
- 1× I2C bidirectional voltage level shifter (2-channel 3.3V to 5V, SDA/SCL)
- 1× 4-conductor flexible hinged harness (SDA/SCL/5V/GND)
- 1× steel hinge pin (2.0mm diameter approx. 120.0mm long)
- 1× clamshell keyboard tray (PETG base_shell.stl)
- 1× clamshell LCD lid tray (PETG lid_shell.stl)
- 1× USB-C 5V external supply (5V >=1A, vendor input only)
- 0× optional protected single-cell Li-ion pack (3.7V, PH2.0 polarity to verify)

## DFM Notes
- [warn] NOT FIT-VERIFIED: board Z, screw mounts, USB access, lid retention, hinge life/cable bend, battery
- [warn] NOT ELECTRICALLY VERIFIED: CardKB 5V I2C to ESP32 3.3V; level shift, pull-ups and shared I2C bus
- [warn] NOT FUNCTIONALLY VERIFIED: SSH host key, Ctrl/Esc, terminal rendering, reconnect
