# Adding a part to the device planner

> **Parts are data.** A module, a controller board or a sensor is a cited entry in
> [`data/device_modules.json`](../src/hardware_splicer/data/device_modules.json). The planner, the case export and the
> [engineering review](DEVICE_ENGINEERING_REVIEW.md) read that entry and carry no part-specific code. What a part can do
> downstream depends on how much of the entry is filled in, and the gaps are listed rather than assumed.

## What each output needs

| Output | Needs from the library entry | When a figure is missing |
|--------|------------------------------|--------------------------|
| Plan, 3D assembly, wiring checks | `pcb_mm`, `pins` (position, name, roles), `connectors`, `sources`, `dimension_basis` | the entry is refused at load |
| Case files | nothing more: sized from the plan | none |
| Engineering review | an `engineering` block, and `i2c.pullups` for a breakout | the check says `not_assessed` and lists the module under `coverage` |
| Application source and diagnostics | a part descriptor, an adapter and, for a vendor-host lane, a bus model ([part descriptors](DEVICE_PART_DESCRIPTORS.md)) | the generator refuses the board with a clear message |

Today the firmware generators support the ESP32-DevKitC V4 with the BME280 and BH1750. The plan, case and review work for every
entry in the library.

## A sensor, display or breakout

1. Pins with `roles` (`ground`, `power_in`, `power_3v3`, `i2c_sda`, `i2c_scl`, ...) and positions in the module's own frame.
2. `i2c.addresses` with the sentence that supports them, and `i2c.pullups` (ohms, the rail, the quote and its source) where the
   maker states them.
3. `electrical.supply_note` and `pullups_note`. Name the controller with `{controller}`; the planner writes "ESP32" or "Pico"
   by the board in use.
4. `engineering`:
   - `operating_temp_c` (min, max, `recommended` or `absolute_maximum`, the table it came from);
   - `loads`: rows of `sustained` or `peak` current with `rail_v`, the conditions and the locator;
   - `temperature_sensing` when the part measures temperature and its datasheet says the reading depends on its surroundings;
   - `gaps`: for anything you could not read, say what and why. A part with no figures at all is still valid; the review will
     list it as missing.
5. Every `source` must be one of the entry's own `sources` (or its `engineering_sources`, which a plan never shows). The loader
   enforces this, and enforces finite numbers, locators and the `kind` vocabularies.

## A controller board

Everything above, plus the wording and sources the planner quotes, all in `electrical` and checked by the loader:

| Field | Used for |
|-------|----------|
| `short_name`, `datasheet_basis`, `header_types_basis` | the controller's name and the sources behind wiring findings |
| `input_high_note`, `input_high_basis` | the warning when a module is run from 5 V on a 3.3 V board |
| `i2c_default_owner`, `i2c_defaults_basis`, `i2c_remap_note` | the default I2C pins and what changing them means |
| `i2c_pin_mux` | `any`: the controller can route I2C to most pins (the ESP32). `fixed`: only pins marked for each controller can (the Pico). With `fixed`, mark pins `i2c_sda_capable` or `i2c_scl_capable` with an `i2c_controller` index, and the planner refuses SDA on a pin with no SDA function and a bus that mixes controllers |
| `supply_options_note`, `supply_options_basis`, `supply_check_step`, `supply_power_step` | how the board may be powered, as findings and steps |
| `supply_current_note`, `supply_current_source`, `supply_current_basis`, `supply_current_practice` | what the supply must deliver |
| `pin_numbering_from` (top level) | where pin 1 is counted from, in wire labels |

Antenna boards add `overhang_mm.antenna_end`, a `keep_clear` entry and an `engineering.antenna` clearance with its quote. A board whose
regulator type is documented adds `engineering.power_stage`.

## What this does not do

- It does not extract anything from a datasheet. Reading the figure and writing its locator is a person's job; the loader only
  refuses an uncited or nonsensical one.
- A figure that is cited is not thereby right. Entries stay unreviewed extracts until someone checks them against the source.
- Adding a controller does not give it firmware. That needs a descriptor, an adapter and tests of its own.

## Checking a new entry

`tests/test_device_controllers.py` runs every example through the plan, the review and the case export, so adding an example spec
exercises a new part end to end. The Raspberry Pi Pico was added this way: one library entry, two example specs, and no change to
the planner's logic beyond moving ESP32 wording into the ESP32 entry, with the ESP32 plans byte-identical before and after.
