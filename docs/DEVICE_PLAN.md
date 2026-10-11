# Device assembly (whole gadget)

The **Build a device** page (`/engineering/device`) shows a whole gadget going together: parts hover apart, the board drops
into the case and the display and lid come down. Each wire grows from pin to pin. For the generic OLED, the drawing uses
an explicit pin-order choice, shown beside the viewer: **Which order is printed on your module?** Changing it updates the
spec, makes another plan and redraws the pads and wires. Read the order left to right looking at the screen, header at the top.
USB stays disconnected in the animation when any warning or error needs review. The page covers modules, wires and a case.

The example selector keeps the original ESP32/OLED example as the default and
also offers ESP32/OLED/BME280. I2C breakouts have independent stand-in shapes on
the case floor, placement steps and printed-name labels. Each wire and connector
follows its owning module, including when module IDs are renamed or several
breakouts are present. Sensor pin positions and component shapes are
illustrative, not a published header order or physical fit result.

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
radio module listed on the DevKitC board; `BME280`, `BH1750FVI` and `DS3231` name the chips listed on the three I2C breakouts.
The chip or radio module alone is **not that module**, and does not come with its board,
pins, regulator or wiring rules. These are name comparisons against the library, not proof of the reclaimed part. Family matches
are never offered.

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
  "modules": [{"id": "mcu", "module": "esp32-devkitc-v4"}, {"id": "display", "module": "ssd1306-096-i2c", "pin_order": "vcc-gnd-scl-sda"}],
  "connections": [{"from": "display.VCC", "to": "mcu.3V3"}, {"from": "display.SDA", "to": "mcu.IO21"}],
  "case": {"wall_mm": 2.0, "clearance_mm": 1.0}
}
```

A pin is `module.NAME` (the name printed on the module) or `module.ID` (for example `mcu.J3-6`). A name that several pins share,
such as `GND`, takes the pin nearest the other end of the wire, and the plan says which it chose. Measured sizes can replace the
library's typical ones with `"overrides": {"pcb_mm": {"x": 28.1}}`.

For the generic OLED, **follow the labels printed on your module**. Its IDs are `GND`, `VCC`, `SCL` and `SDA`, not numbered
positions. The old `display.P1` through `display.P4` aliases are refused because they implied a pin order. Seller orders
include `GND VCC SCL SDA` and `VCC GND SCL SDA`. Optional `modules[].pin_order` chooses a library order ID:
`gnd-vcc-scl-sda` or `vcc-gnd-scl-sda`. Non-text values and unknown IDs are refused with the valid IDs;
a module with no orders refuses this field. Omitting it assumes the library's `default_pin_order`.

The default is `vcc-gnd-scl-sda`, confirmed by AZ-Delivery's already-cited listing. The former drawing used GND first;
its order remains a choice linked to the existing DisplayModule citation, with the source detail explicitly marked as
not rechecked. The current DisplayModule page text does not list that order. This source gap is not proof of a pin layout.

The planner assigns names and electrical roles to `header_positions` in the chosen sequence, then uses those pads for
wire endpoints and `step.wire` for animation. `modules[].pins` and `modules[].logical_pins` now share those named pads;
`modules[].pin_order` records the drawn ID. Wire lengths remain estimates. There is no header-centre `point_basis`.
An info finding explains the drawn sequence and source and tells you to connect by the printed labels, not picture position.
Its code is `pin_order_drawn` when selected, or `pin_order_assumed` when omitted; the latter says it was assumed.
Selecting an order describes the drawing; it does not verify your module or its supply and pull-ups.

`power.source` is a text label, not a wire or a voltage. Only `usb` is supported by this planner. Other labels report an error
and show a power-review step without asking you to connect USB. There is no external power-source module in this library,
so this spec cannot describe or detect a second supply, or establish a battery wire to 3V3. It does not claim that a supply
exceeds a voltage limit from its name. A display load on 3V3 or 5V is not another supply.

## The module library (`data/device_modules.json`)

Every figure names where it came from, or says it is typical and tells you to measure.
Each `pin_orders` entry has an `id`, source-name `label`, exact `signals` sequence and `source` URL from that module's
existing `sources`. The loader requires each signal once, unique order IDs, a valid default and a header pad per signal.
Optional `chips` lists hold at most eight entries, each with printable, nonempty `marking` (at most 40 characters), `role` (80)
and `source` (2048). The source must equal a URL already in that module's `sources`. The listed chips are the
ESP32-WROOM-32E radio module, the SSD1306 display controller, and the BME280, BH1750FVI and DS3231 chips on the
three I2C breakouts, each using an already-cited datasheet; no chip pin or electrical contract is added.
Optional `quotes` lists hold sourced fragments: each item has exactly `claim`, `quote` and `source`, the source must
equal a URL already in that module's `sources`, and the quote is a verbatim excerpt.
The loader checks the quote's shape and source membership. The separate
`scripts/verify_device_module_quotes.py --source-dir <capture-directory>` check
compares each fragment with its exact cited capture and reports capture hashes.

| Module | Taken from | Typical or unpublished, so check |
|--------|-----------|---------------------|
| ESP32-DevKitC V4 | Espressif's dimensions drawing (27.94 × 48.26 mm, rows 25.40 apart, 2.54 pitch, 6.04 antenna overhang), the user guide pin tables (J2, J3), the WROOM-32E datasheet (module 18.0 × 25.5 × 3.1 mm, 3.0 to 3.6 V supply, GPIO6 to 11 on the flash, strapping pins, VIH max VDD + 0.3 V), the arduino-esp32 pin file (SDA 21, SCL 22) | PCB thickness, header length below the board, USB socket height |
| 0.96 inch SSD1306 I2C OLED | the SSD1306 datasheet (I2C address 0x3C or 0x3D), seller listings (active area 21.74 × 10.86 mm) | board size, glass position, pin order (follow the printed labels) |
| Adafruit BME280 STEMMA QT | Adafruit pinouts (Vin, 3Vo, GND, SCK, SDI; regulator 3–5 V; default I2C 0x77 / 0x76; level shifting follows Vin), Adafruit product 2652 Product Dimensions 25.2 × 18.0 × 4.6 mm, Bosch BME280 datasheet (chip 1.71–3.6 V; address 111011x; SDI needs a pull-up) | header positions, header length below the board, mounting-hole positions; pin order was not published — connect by the printed names |
| Adafruit BH1750 STEMMA QT | Adafruit pinouts (VIN, 3Vo, GND, SCL, SDA; 10 kΩ pull-ups; addresses 0x23 / 0x5C), Adafruit product 4681 Product Dimensions 25.3 × 17.7 × 4.5 mm, Rohm BH1750FVI datasheet from an Internet Archive copy (chip 2.4–3.6 V; two slave addresses) | header positions, header length below the board, mounting-hole positions, which rail the pull-ups join; pin order was not published |
| Adafruit DS3231 STEMMA QT | Adafruit pinouts (Vin, GND, SCL, SDA, BAT; 10 kΩ pull-ups to Vin; 2.3–5.5 V, no regulator), Arduino usage (address 0x68, not changeable), product 5188 Product Dimensions 25.4 × 17.8 × 7.8 mm and CR1220 backup cell, Maxim DS3231 datasheet from an Internet Archive copy (chip VCC 2.3–5.5 V; address 1101000) | header positions, header length below the board, mounting-hole positions; pin order was not published |

The library does not claim a supply range for the OLED module: the chip's own limit is not what a module accepts, and sellers
do not standardise the module's regulator. Product Dimensions on the three Adafruit breakouts are the seller's overall
product size, not a board outline. Bosch, Rohm and Maxim voltages are chip limits, not header VIN contracts.

Every plan copies each wired module's `electrical.supply_note` and `pullups_note` into that module's notes and into
information findings, including the example. OLED notes keep the `oled_supply_note` rule name; other modules use
`module_supply_note`. Those notes ask you to check the actual module's supply and pull-up arrangement. A 3V3 or 5 V
wire does not establish how your module will behave, and a 5 V Vin finding is not a build permit.

A device still needs exactly one microcontroller board and at most one display. Any number of `i2c_breakout` modules
may sit on the case floor, USB-side of the antenna, up to the existing module limit. They do not get a lid window.
Header order was not published for the three breakouts: connect by the printed names (SCK and SDI on the BME280).

The WROOM-32E datasheet source and each chip entry citing it use the publisher's new documentation URL (the old one answers
HTTP 301). The 2026-10-10 date is when the link was updated, not a new claim about the hardware.

## What the plan checks

Ground to power or signal (including input-only pins), power onto a signal pin, SDA joined to SCL, a pin wired to two things,
a missing wire on a required pin, the module's flash pins, input-only I2C pins and the reset pin are errors.
Display GND on IO34, IO35, VP or VN is an error and does not count as a ground return. The isolation check names the board's
GND label rather than treating that signal endpoint as ground.

I2C on IO12 (MTDI) is an error: its pull-ups hold the pin high at reset and select the flash's 1.8 V supply. It gets no
custom-pin routing note. Other strapping pins and USB serial pins have warnings; SDA and SCL swapped against Arduino's
defaults have warnings; other output-capable custom I2C pins have a note. GPIO0 also has an auto-program circuit note
from the ESP-IDF ADC documentation's list of dev kits.

A breakout VIN on 5V keeps a warning that uses that module's own supply and pull-up notes, plus the WROOM VIH
limit (VDD + 0.3 V). Check the actual module's regulator and pull-up supply. 5 V on DS3231 Vin is especially a
pull-up-to-Vin warning, not a missing-regulator warning. That finding is not a permit to build or power the gadget.
The existing OLED 5 V warning, information findings and single-display scan step keep their established text.
Any warning or error replaces the USB action with a review step:
"Do not plug in until you have checked the warnings above and resolved the errors."

Overlapping I2C address sets are a warning. Two or more modules that state onboard pull-ups get an information note
about stacked resistors. The DS3231 coin cell is backup only and is not a power source; wiring BAT to 3V3 or 5V is
an error.
The BME280 and BH1750 `3Vo` pins are regulator outputs, so supply-to-signal,
ground shorts and parallel supply-output connections are also checked there.
The BAT restriction is the planner's conservative wiring policy with an optional
coin cell, rather than a claim that the datasheet forbids every external backup supply.
Other BAT wiring and optional breakout pins with no supported electrical role are
reported as unsupported connections; listing a pin name supplies no wiring check.

Matching I2C data or clock pins may share a bus, directly at the MCU or through
another module. In a plan with breakouts, the whole connected signal path must
reach one MCU pin; disconnected buses, multiple MCU pins on one signal and
indirect SDA/SCL bridges are errors. These checks supply no scan result.

The reset pin and the flash pins are wrong whatever they are wired to, from either end, and a wire the checks reject does not
count toward a module's required pins. Wires are also checked as nets: a module's ground pins are one net, so are its 3V3 pins
and its 5V pins, and wires that are each fine but together join 3V3 to 5V, or a supply to ground, are an error. Each finding
carries the basis it rests on.

The example has information findings, not an empty findings list. A DevKit one-supply note appears in every plan. No
finding or checklist approves building, powering, reuse or release. Meter checks ask you to record what you observe;
they supply no expected reading. An I2C scan records observations rather than predicting a device or address.
When only notes are present, the findings panel still says "These checks found nothing wrong with the wiring. That does
not prove it will work." It adds that these are the checks this tool makes and a wire that passes them is not a wire that
works, then lists the notes.

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
- The GPIO0 note cites [ESP-IDF ADC docs v4.2.5](https://docs.espressif.com/projects/esp-idf/en/v4.2.5/esp32/api-reference/peripherals/adc.html):
  "ESP32 DevKitC: GPIO 0 cannot be used due to external auto program circuits." (Quoted from that page; it appears in the list of dev kits with ADC2 pin restrictions.)

## The case

A two-part box sized from every module (so a larger measured display makes a larger case, and a display too small for its own screen is refused), a typical jumper-wire housing height (14 mm), room for the wires to bend (10 mm), the
board resting on its header pins, a USB cut-out wide enough for the plug's moulded body, and a window around the display's
active area. It is **a proposal, not printed and not test-fitted**; the page says so and lists what to measure first.
Seat the display by its circuit-board edges, not by the glass, and avoid straining the header or wires. This is general
handling practice, not a force limit or a fit claim.

## Not yet

A battery (needs a charger and regulator modules; the DS3231 coin-cell backup is not that feature), more module types, a case export you can print, and a wire-by-wire
animation for boards other than the ones in the library.

Every plan also reports the WROOM-32E supply requirement (datasheet v2.1, Table 14: IVDD minimum 0.5 A).
Weak chargers, cables or unpowered hubs and resets when Wi-Fi starts are labelled general practice, not datasheet claims.
Wires on pins whose library function names ADC2 get an information note: analog reads fail while Wi-Fi runs
(ESP-IDF v4.2.5 ADC docs); digital I2C still works. This also appears on wires rejected by other checks.
The antenna `keep_clear` entry cites Figure 3 note A: the datasheet marks a keepout zone but gives no case-wall distance.
The information note reports the actual antenna-to-inside-wall gap from the existing layout without judging it.
One kit-fit note names the typical housing, bend, USB overmold, PCB and under-board header sizes and asks you to
check your actual kit; female-to-female jumpers require male pins at both ends. Display seating puts force on board
edges and never the glass, explicitly labelled general practice, not from the datasheet. These notes approve nothing.

## Compatibility check

`PYTHONPATH=src .venv/bin/python scripts/audit_device_plan_compatibility.py --baseline bfeb992b`
compares every MCU/OLED pin pair in both directions (304 cases), including exact
error and warning text. It also reports whether the example spec, authority
sentence and complete default plan match the selected revision. Default-plan
equality is reported separately from wiring-check parity; differences may include
notes, sources or instructions added before this module extension.

## Headless frontend verification

```sh
bash scripts/verify_device_frontend.sh mock device-assembly donor-lookup donor-device-handoff donor-capture evidence-
bash scripts/verify_device_frontend.sh real device-assembly donor-device-handoff
```

The harness needs the repo Python environment, installed frontend dependencies
and pinned Playwright in `/tmp/hs-playwright` (override with
`HS_PLAYWRIGHT_ROOT`). It builds a source copy without `.env` files in a fresh
ignored directory and uses isolated project/output roots. Default test ports
are 3102/8102; `HS_FRONTEND_TEST_PORT` and `HS_BACKEND_TEST_PORT` can change them.
Occupied ports are refused, not reclaimed. Cleanup stops only the two processes
started by the harness and leaves build logs, JSON results and screenshots in
the reported directory. It does not rebuild the live `.next` directory.

`mock` uses the existing studio fixture, which delegates device plans and reclaim
matching to their real implementations. `real` mounts the actual product API;
it does not seed an outsider project. The browser tests cover the original OLED
flow, each of the three breakouts, independent multi-module motion, renamed IDs,
wire attachment, conservative warning behavior, phone layout and advisory chip
handoffs. Passing them supplies no physical evidence or release authority.
