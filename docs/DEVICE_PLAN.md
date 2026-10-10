# Device assembly (whole gadget)

The **Build a device** page (`/engineering/device`) shows a whole gadget going together: parts hover apart, the board drops
into the case and the display and lid come down. Wires are animated only where their physical pin positions are known.
The generic OLED's header pads are unnamed, so its wires have label-based instructions without a positioned wire animation.
USB stays disconnected in the animation when any warning or error needs review. The page covers modules, wires and a case.

It is a **proposal and a checklist**. It carries no engineering authority, stores nothing, and approves nothing. A wire that
passes the checks is not a wire that works, the case has not been printed, and every "check" is something to try, not a result.

## Endpoints (stateless)

| Route | Returns |
|-------|---------|
| `GET /v1/devices/modules` | the module library, with each module's sources, dimension basis and optional sourced `chips` roles |
| `GET /v1/devices/examples` | example device specs |
| `GET /v1/devices/examples/{id}/plan` | an example's plan |
| `POST /v1/devices/plan` | a plan for a spec; 422 with a reason when the spec cannot make one, 413 over 64 KB (the body is read a piece at a time and refused as soon as it is too big, in the page's proxy and in the backend) |
| `POST /v1/devices/reclaim-matches` | advisory exact/variant name matches for a reclaim list; 422 for invalid text or shape, 413 over 64 KB in both proxy and backend |

From **Salvage a board**, matching reclaim rows link here to a small **Parts you may have on hand** list. It compares the markings
and kinds reported in that plan with whole `name`, explicit `mpn` fields or explicit `chips[].marking` entries in the device library,
using the exact/variant rules from marking lookup; family matches are never offered. It does not extract chip names from descriptions.
Whole-name matches have `relation: "module"`. Chip-name matches have `relation: "chip_on_module"`, with the listed role, source URL
and an advisory note. `SSD1306` names the display controller listed on the OLED module; `ESP32-WROOM-32E` names the Wi-Fi/Bluetooth
radio module listed on the DevKitC board. The chip or radio module alone is **not that module**, and does not come with its board,
pins, regulator or wiring rules. These are name comparisons against the library, not proof of the reclaimed part.

The request is `{"parts": [{"ref": "U1", "kind": "ic", "marking": "what you read"}]}` with at most 300 rows and 40 characters
per text field. Each returned row preserves those fields and has `matched` and `matches` (module id, library name, tier, relation and
which name field matched; chip matches also carry `role`, `source` and `note`). An empty marking is allowed. Hidden/control characters and non-text values are refused;
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

For the generic OLED, **follow the labels printed on your module**. Its IDs are `GND`, `VCC`, `SCL` and `SDA`, not numbered
positions. The old `display.P1` through `display.P4` aliases are refused because they implied a pin order. Seller orders
include `GND VCC SCL SDA` and `VCC GND SCL SDA`; neither is a default. Logical OLED wire coordinates mark the header centre
only, with a `point_basis` stating that the physical pin position is unknown. Separate library `header_positions` draw
unnamed pads in the plan's `modules[].pins`; `modules[].logical_pins` retains the electrical names and roles for wire
endpoints. The pads do not map signals to positions. Wire lengths remain estimates.

`power.source` is a text label, not a wire or a voltage. Only `usb` is supported by this planner. Other labels report an error
and show a power-review step without asking you to connect USB. There is no external power-source module in this library,
so this spec cannot describe or detect a second supply, or establish a battery wire to 3V3. It does not claim that a supply
exceeds a voltage limit from its name. A display load on 3V3 or 5V is not another supply.

## The module library (`data/device_modules.json`)

Every figure names where it came from, or says it is typical and tells you to measure.
Optional `chips` lists hold at most eight entries, each with printable, nonempty `marking` (at most 40 characters), `role` (80)
and `source` (2048). The source must equal a URL already in that module's `sources`. Only the SSD1306 controller and
ESP32-WROOM-32E radio module are listed, using their already-cited datasheets; no chip pin or electrical contract is added.

| Module | Taken from | Typical, so measure |
|--------|-----------|---------------------|
| ESP32-DevKitC V4 | Espressif's dimensions drawing (27.94 × 48.26 mm, rows 25.40 apart, 2.54 pitch, 6.04 antenna overhang), the user guide pin tables (J2, J3), the WROOM-32E datasheet (module 18.0 × 25.5 × 3.1 mm, 3.0 to 3.6 V supply, GPIO6 to 11 on the flash, strapping pins, VIH max VDD + 0.3 V), the arduino-esp32 pin file (SDA 21, SCL 22) | PCB thickness, header length below the board, USB socket height |
| 0.96 inch SSD1306 I2C OLED | the SSD1306 datasheet (I2C address 0x3C or 0x3D), seller listings (active area 21.74 × 10.86 mm) | board size, glass position, pin order (follow the printed labels) |

The library does not claim a supply range for the OLED module: the chip's own limit is not what a module accepts, and sellers
do not standardise the module's regulator. Every OLED plan copies `electrical.supply_note` and `pullups_note` into the module's
notes and into information findings, including the example. Those notes ask you to check the actual module's supply and
pull-up arrangement. The example's 3V3 wire does not establish how your module will behave.

The WROOM-32E datasheet source and each chip entry citing it use the redirected documentation URL. The supervisor checked
that redirect on 2026-10-10; that is the source's `as_of` date, not a new claim about the hardware.

## What the plan checks

Ground to power or signal (including input-only pins), power onto a signal pin, SDA joined to SCL, a pin wired to two things,
a missing wire on a required pin, the module's flash pins, input-only I2C pins and the reset pin are errors.
Display GND on IO34, IO35, VP or VN is an error and does not count as a ground return. The isolation check names the board's
GND label rather than treating that signal endpoint as ground.

I2C on IO12 (MTDI) is an error: its pull-ups hold the pin high at reset and select the flash's 1.8 V supply. It gets no
custom-pin routing note. Other strapping pins and USB serial pins have warnings; SDA and SCL swapped against Arduino's
defaults have warnings; other output-capable custom I2C pins have a note. GPIO0 also has an auto-program circuit note
from audit B7's ESP-IDF citation, **unverified by supervisor**.

OLED VCC on 5V keeps a warning covering both the chip's logic supply and pull-ups that could put 5 V on ESP32 SDA/SCL.
Check the actual module's regulator and pull-up supply. Any warning or error replaces the USB action with a review step:
"Do not plug in until you have checked the warnings above and resolved the errors."

The reset pin and the flash pins are wrong whatever they are wired to, from either end, and a wire the checks reject does not
count toward a module's required pins. Wires are also checked as nets: a module's ground pins are one net, so are its 3V3 pins
and its 5V pins, and wires that are each fine but together join 3V3 to 5V, or a supply to ground, are an error. Each finding
carries the basis it rests on.

The example has information findings, not an empty findings list. A DevKit one-supply note appears in every plan. No
finding or checklist approves building, powering, reuse or release. Meter checks ask you to record what you observe;
they supply no expected reading. An I2C scan records observations rather than predicting a device or address.

## Source excerpts used for these rules

- [DevKitC V4 user guide](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html):
  "The power supply must be provided using one and only one of the options above"; the options are Micro USB, 5V/GND and
  3V3/GND. It warns: "otherwise the board and/or the power supply source can be damaged."
  Its J2 table lists "IO34 | I | GPIO34, ADC1_CH6, VDET_1" and defines "I: Input".
- [WROOM-32E datasheet](https://documentation.espressif.com/esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.pdf), section 4.2:
  "MTDI = 1, VDD_SDIO pin is powered from internal 1.8 V LDO." Its schematic says:
  "IO12 should be kept low when the module is powered on."
- [SSD1306 datasheet](https://cdn-shop.adafruit.com/datasheets/SSD1306.pdf): "VDD = 1.65V to 3.3V for IC logic";
  I2C data and clock "must be connected to pull-up resistors". The chip's panel-driving VCC is a different supply
  from a module header labelled VCC.
- [AZ-Delivery listing](https://www.az-delivery.de/en/products/0-96zolldisplay): "Pin assignment: VCC, GND, SCL, SDA"
  and "Operating voltage: 3.3V to 5V". These are claims about that seller's module.
- Audit B7 cites [ESP-IDF ADC docs v4.2.5](https://docs.espressif.com/projects/esp-idf/en/v4.2.5/esp32/api-reference/peripherals/adc.html):
  "ESP32 DevKitC: GPIO 0 cannot be used due to external auto program circuits." This excerpt is unverified by supervisor.

## The case

A two-part box sized from every module (so a larger measured display makes a larger case, and a display too small for its own screen is refused), a typical jumper-wire housing height (14 mm), room for the wires to bend (10 mm), the
board resting on its header pins, a USB cut-out wide enough for the plug's moulded body, and a window around the display's
active area. It is **a proposal, not printed and not test-fitted**; the page says so and lists what to measure first.
Seat the display by its circuit-board edges, not by the glass, and avoid straining the header or wires. This is general
handling practice, not a force limit or a fit claim.

## Not yet

A battery (needs a charger and regulator modules), more module types, a case export you can print, and a wire-by-wire
animation for boards other than the ones in the library.
