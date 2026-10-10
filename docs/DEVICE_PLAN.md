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
| `POST /v1/devices/plan` | a plan for a spec; 422 with a reason when the spec cannot make one, 413 over 64 KB (the body is read a piece at a time and refused as soon as it is too big, in the page's proxy and in the backend) |
| `POST /v1/devices/reclaim-matches` | advisory exact/variant name matches for a reclaim list; 422 for invalid text or shape, 413 over 64 KB in both proxy and backend |

From **Salvage a board**, matching reclaim rows link here to a small **Parts you may have on hand** list. It compares the markings
and kinds reported in that plan with whole `name` or explicit `mpn` fields in the existing device library, using the exact/variant
rules from marking lookup; family matches are never offered. It does not extract chip names from module descriptions.
The current library has two modules with descriptive names and no separate MPN fields, so a chip marking such as `SSD1306`
does not match the complete OLED module.

The request is `{"parts": [{"ref": "U1", "kind": "ic", "marking": "what you read"}]}` with at most 300 rows and 40 characters
per text field. Each returned row preserves those fields and has `matched` and `matches` (module id, library name, tier and
which name field matched). An empty marking is allowed. Hidden/control characters and non-text values are refused;
dimensions and readings are not consumed. The response names its library source and carries the advisory limit.

The handoff keeps only these input fields in this tab's session storage; the device page validates them through the backend
and checks the library again. The list is advisory: you may already have this part on the board you took apart, but its marking
is what you read, not proof. The planner's data is the library's, not your chip's. It makes no compatibility claim, changes no
device spec or wiring, and approves no building, powering or release. A recorded reading is not a pass.

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
The reset pin and the flash pins are wrong whatever they are wired to, from either end, and a wire the checks reject does not
count toward a module's required pins. Wires are also checked as nets: a module's ground pins are one net, so are its 3V3 pins
and its 5V pins, and wires that are each fine but together join 3V3 to 5V, or a supply to ground, are an error. Each finding
carries the basis it rests on.

## The case

A two-part box sized from every module (so a larger measured display makes a larger case, and a display too small for its own screen is refused), a typical jumper-wire housing height (14 mm), room for the wires to bend (10 mm), the
board resting on its header pins, a USB cut-out wide enough for the plug's moulded body, and a window around the display's
active area. It is **a proposal, not printed and not test-fitted**; the page says so and lists what to measure first.

## Not yet

A battery (needs a charger and regulator modules), more module types, a case export you can print, and a wire-by-wire
animation for boards other than the ones in the library.
