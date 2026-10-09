# Device assembly (whole gadget)

The **Build a device** page (`/engineering/device`) shows a whole gadget going together: parts hover apart, the board drops
into the case, each wire grows from the pin it starts on to the pin it ends on, the display and lid come down, and USB plugs
in. It goes past the board: modules, wires and a case.

It is a **proposal and a checklist**. It carries no engineering authority, stores nothing, and approves nothing. A wire that
passes the checks is not a wire that works, the case has not been printed, and every "check" is something to try, not a result.

## Endpoints (stateless)

| Route | Returns |
|-------|---------|
| `GET /v1/devices/modules` | the module library, with each module's sources and dimension basis |
| `GET /v1/devices/examples` | example device specs |
| `GET /v1/devices/examples/{id}/plan` | an example's plan |
| `POST /v1/devices/plan` | a plan for a spec (at most 64 KB); 422 with a reason when the spec cannot make one |

## The spec

```json
{
  "name": "ESP32 with an OLED display, powered over USB",
  "power": {"source": "usb"},
  "modules": [{"id": "mcu", "module": "esp32-devkitc-v4"}, {"id": "display", "module": "ssd1306-096-i2c"}],
  "connections": [{"from": "display.VCC", "to": "mcu.3V3"}, {"from": "display.SDA", "to": "mcu.IO21"}],
  "case": {"wall_mm": 2.0, "clearance_mm": 1.0}
}
```

A pin is `module.NAME` (the name printed on the module) or `module.ID` (for example `mcu.J3-6`). A name that several pins share,
such as `GND`, takes the pin nearest the other end of the wire, and the plan says which it chose. Measured sizes can replace the
library's typical ones with `"overrides": {"pcb_mm": {"x": 28.1}}`.

## The module library (`data/device_modules.json`)

Every figure names where it came from, or says it is typical and tells you to measure.

| Module | Taken from | Typical, so measure |
|--------|-----------|---------------------|
| ESP32-DevKitC V4 | Espressif's dimensions drawing (27.94 × 48.26 mm, rows 25.40 apart, 2.54 pitch, 6.04 antenna overhang), the user guide pin tables (J2, J3), the WROOM-32E datasheet (module 18.0 × 25.5 × 3.1 mm, 3.0 to 3.6 V supply, GPIO6 to 11 on the flash, strapping pins, VIH max VDD + 0.3 V), the arduino-esp32 pin file (SDA 21, SCL 22) | PCB thickness, header length below the board, USB socket height |
| 0.96 inch SSD1306 I2C OLED | the SSD1306 datasheet (I2C address 0x3C or 0x3D), seller listings (active area 21.74 × 10.86 mm) | board size, glass position, pin order (follow the printed labels) |

The library does not claim a supply range for the OLED module: the chip's own limit is not what a module accepts, and sellers
do not standardise the module's regulator.

## What the plan checks

Shorts (ground to power or signal), power onto a signal pin, SDA joined to SCL, a pin wired to two things, a missing wire on
a required pin, the module's flash pins (error), input-only pins and the reset pin (error), strapping pins and the USB serial
pins (warning), SDA and SCL swapped against Arduino's defaults (warning), a custom I2C pin (note), 5 V on a module whose
pull-ups would put 5 V on 3.3 V pins (warning), and a battery wired straight to the board (error: it exceeds the 3.6 V maximum).
Each finding carries the basis it rests on.

## The case

A two-part box sized from the modules, a typical jumper-wire housing height (14 mm), room for the wires to bend (10 mm), the
board resting on its header pins, a USB cut-out wide enough for the plug's moulded body, and a window around the display's
active area. It is **a proposal, not printed and not test-fitted**; the page says so and lists what to measure first.

## Not yet

A battery (needs a charger and regulator modules), more module types, a case export you can print, and a wire-by-wire
animation for boards other than the ones in the library.
