# Part descriptors: adding a sensor to the generated application

> **A tested engineering-software system with modeled execution — not physically validated hardware.**
> A descriptor is a cited extract of a datasheet. It is not evidence about any physical part and it never
> authorizes flashing, powering or fabrication.

The generated ESP32 application has one fault-handling engine (`app_core.h`) and one set of fifteen host fault
scenarios (`host_harness.cpp`). Everything specific to one I2C part lives in a descriptor under
`src/hardware_splicer/data/parts/<part>.json`. `device_parts.py` validates it and renders two headers into every
generated package: `src/part_traits.h` (the reading, its plausible ranges and the serial and display formats) and
`test/host/part_fixtures.h` (addresses, identity, fixture readings and the range-edge test cases).
The descriptor itself ships as `PART_DESCRIPTOR.json`, and its SHA-256 is in `FIRMWARE_PROPOSAL.json`.

Supported today: the BME280 (`adafruit-bme280-stemma-qt`) and the BH1750 (`adafruit-bh1750-stemma-qt`),
each with an optional SSD1306 display.

## What a descriptor states

| Field | Meaning |
|-------|---------|
| `addresses` | Exactly two declared 7-bit addresses, first is the default. Must equal the catalogue entry or export is refused |
| `identity` | Register, expected value and citation, or `null` plus an `identity_note` when the datasheet defines no ID register |
| `channels` | One to three readings: key, formats, plausible range, fixture value, an out-of-range probe, display marker |
| `bounds_citation` | Where the ranges come from |
| `adapter` | The Arduino adapter template, the PlatformIO dependencies, whether a vendor-host lane exists and, if so, its `vendor_profile` |
| `review_status` | Always `UNREVIEWED_EXTRACT` until a person reviews it |

Every string that reaches generated C++ is checked against a strict pattern (no quotes, backslashes or newlines in
formats, keys or constants), and unsafe descriptors are refused (`tests/test_device_parts.py`).

## Adding a part

1. Read the datasheet and write the descriptor, with a page citation for each fact. Wrong ranges here are wrong
   everywhere, because the range-edge tests are generated from the same numbers.
2. Write the adapter template (`main_<part>.cpp.tmpl`): a `Hal` with `sensor_begin`, `sensor_read`, the display
   and `bus_recover`. Prefer a direct `Wire` driver when the vendor library prints to `Serial`, because the
   documented serial grammar allows no extra lines.
3. To give the adapter a vendor-host lane, write a bus model from the datasheet (`vendor_host/models_<part>.*`) and a harness
   (`vendor_harness_<part>.cpp`, built on `vendor_common.h`), then register both under a profile in
   `device_vendor_profiles.py`. The descriptor only names the profile; it cannot add a source file or a compiler argument.
4. Add the catalogue entry if it is missing, then run `scripts/verify_device_application.py --spec <spec> --platformio <pio>`
   and `scripts/benchmark_device_fault_matrix.py --part <part>`.

## What it cost, measured

| | BH1750 (core lane) |
|--|--|
| New files | descriptor 41 lines, adapter template 112 lines (about 60 are shared display code) |
| BH1750-specific edits to the fault scenarios | none; one leftover BME280 literal in the generic harness was found and fixed |
| Seeded bugs caught by the full battery | 45 / 45 (smoke 7, healthy bus 10), untuned |
| Adapter lane: a 127-line bus model and a 602-line harness, on 313 lines of shared helpers and the SSD1306 model | 28 / 32 before two harness gaps were closed, 30 / 32 after; see the benchmark note |

The one-off generalisation cost a 251-line generator, and left the engine and harness 36 lines shorter. The BME280
stack, by contrast, is 1,310 hand-written lines for the adapter lane alone.

## What this does not give you

- **The tests prove the code matches the descriptor, not that the descriptor matches the datasheet.** The range-edge
  cases are generated from the same numbers the code uses. Review is the control, and nothing automates it.
- **The BH1750's bus model is written from the datasheet, not from silicon or a vendor library.** It implements the
  power states, the instruction set, the conversion times and the data register, and uses the datasheet's own worked
  examples (p.7) as the oracle. It does not model the resolution modes, so a driver started in L-resolution or H-resolution
  mode 2 is not distinguished from one in H-resolution mode 1: two reviewed blind spots, counted against the score.
- **A part with no ID register cannot be told from another chip that acknowledges its address.**
- The 1.2 divisor is the datasheet's typical value; the datasheet gives 0.96 to 1.44, so a real chip may differ by up to 20 %.

See [the benchmark note](status/DEVICE_FAULT_MATRIX_BENCHMARK_2026-10-12.md) for how the tests are scored.
