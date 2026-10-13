# Device fault-matrix mutation benchmark — 2026-10-12

Question: do the generated application's host fault scenarios catch bugs that a boot-only or healthy-bus
test cannot? Method: seed realistic bugs into the generated source, compile with the production flags,
and record which detector notices. Two lanes, because two different pieces of code run on the ESP32.

```sh
# application logic (src/app_core.h) through the 15-scenario host harness
PYTHONPATH=src .venv/bin/python scripts/benchmark_device_fault_matrix.py --set all --out core.json
# Arduino adapter (src/main.cpp) through the vendor-host lane; needs the pinned PlatformIO libdeps
PYTHONPATH=src .venv/bin/python scripts/benchmark_device_fault_matrix.py --lane adapter --set all \
    --libdeps <project>/.pio/libdeps/application --out adapter.json
# score an earlier revision:  --harness host_harness.cpp   |   --vendor-host <dir>
```

`serial_grammar` re-runs nine other scenarios, so it is never counted as a healthy-bus detector.
A survivor is excused only after a written reason; a reviewed "blind spot" (a real hardware bug the host
model cannot observe) is listed but still counts against the score.

## Lane 1 — application logic

48 mutants, 45 scored (3 reviewed equivalents). Smoke is `boot_ok`; healthy bus is `boot_ok`,
`default_address_binding`, `read_period`.

| Detector | Caught |
|----------|--------|
| smoke | 5 / 45 (11 %) |
| healthy bus | 8 / 45 (18 %) |
| fault matrix, as it stood | 41 / 45 (91 %) |
| fault matrix, after this change | 45 / 45 |

37 of 45 are caught only by fault-injecting scenarios.

## Lane 2 — the Arduino adapter

The adapter is what runs on the ESP32, and the core harness never compiles it: measured, the core lane
catches 0 of 29 adapter bugs. Only the vendor-host lane (the real adapter plus the pinned Adafruit sources
against a modelled I2C bus) can see them. 32 mutants, 29 scored (3 reviewed equivalents). Smoke is the
default-address scenario; healthy bus adds `sensor_0x76_only` and `display_at_0x3D_only`.

| Detector | Caught |
|----------|--------|
| core host harness | 0 / 29 |
| vendor smoke | 12 / 29 (41 %) |
| vendor healthy bus | 14 / 29 (48 %) |
| vendor matrix, as it stood | 21 / 29 (72 %) |
| vendor matrix, after this change | 28 / 29 (97 %) |

The one survivor is a known blind spot, below. The adapter was the weaker half: 72 % against 91 % for the
logic it hosts.

**Read the "as it stood" figures as the generalisation numbers, not the "after" ones.** Each lane has a
primary set used to tune the harness and a second set written afterwards and not used for tuning. They agree
(logic 91 % / 91 %; adapter 67 % / 88 % before tuning). The "after" figures include the mutants that exposed
the gaps below.

## Lane 3 — a second part, generated from its descriptor

The application logic is generic and the part-specific text is generated from a cited descriptor
([DEVICE_PART_DESCRIPTORS.md](../DEVICE_PART_DESCRIPTORS.md)). The BME280 package, regenerated from its descriptor,
produced output byte-identical to the committed baseline (all 15 scenarios, all 158 serial lines), and the
refactor left every number above unchanged. The BH1750, a part with no ID register, was then generated and
scored with the same detectors and no BH1750-specific scenario edits (one leftover BME280 literal in the generic
harness was found and fixed).

| BH1750, 48 mutants (45 scored) | Caught |
|--|--|
| smoke | 7 / 45 (16 %) |
| healthy bus | 10 / 45 (22 %) |
| fault matrix | 45 / 45 |

40 mutants are generic engine bugs, and 39 of them behave identically on both parts (the same scenarios catch
them, or none for the three reviewed equivalents).
8 are specific to the BH1750's generated traits, written before the battery was run against it, and all 8 were
caught, five of them only by `implausible_values`. Read this as "the battery transfers", not "the part is verified":
those cases are generated from the same numbers the code uses, so they show the code matches the descriptor and
cannot show the descriptor matches the datasheet. The BH1750's Arduino adapter is scored in lane 4.

## Lane 4 — the BH1750's Arduino adapter

The BH1750 adapter drives the chip with its own `Wire` code, so the only vendor code in this lane is the SSD1306
display stack. Its bus model is written from the Rohm datasheet (2009.04 Rev.B): power states, the instruction set,
conversion times, a data register that resets to 0. The datasheet's own worked examples (p.7: raw 0x8390 is 28067 lx,
raw 0x0110 is 227 lx) are the oracle, so the divide-by-1.2 is not checked against itself.

```sh
PYTHONPATH=src .venv/bin/python scripts/benchmark_device_fault_matrix.py --lane adapter --part bh1750 --set all \
    --libdeps <project>/.pio/libdeps/application --out bh1750-adapter.json
```

39 mutants (28 primary, 11 held-out; 17 + 5 are specific to the BH1750 driver, the rest are template text shared with
the BME280 adapter), 32 scored (7 reviewed equivalents, 2 blind spots that stay in the denominator).
The 17 + 5 were written from the adapter template before the BH1750 harness was scored against any of them.

| Detector | Caught, as it stood | Caught, after this change |
|----------|--------------------|---------------------------|
| core host harness | 0 / 32 | 0 / 32 |
| vendor smoke | 19 / 32 (59 %) | 20 / 32 (63 %) |
| vendor healthy bus | 21 / 32 (66 %) | 22 / 32 (69 %) |
| vendor matrix, primary set | 21 / 24 (88 %) | 23 / 24 (96 %) |
| vendor matrix, held-out set | 7 / 8 (88 %) | 7 / 8 (88 %) |
| vendor matrix, all | 28 / 32 (88 %) | 30 / 32 (94 %) |

The "as it stood" column is the first scoring of the harness, run against the earlier revision with `--vendor-host`
(`device-adapter-matrix-bh1750-original-vendor-host-2026-10-13.json`). The held-out set is not used for tuning and
both gaps below came from the primary set. Ten mutants are caught by exactly one scenario.

What the datasheet model adds: `bh_conversion_wait_removed` (the first read returns the reset value 0, which is a valid dark
reading and passes the plausibility range) fails eight scenarios on a bright scene. `bh_conversion_start_not_recorded` (a chip
that was unplugged and replugged is read without waiting) fails only the three scenarios that restart the chip.
`bh_mode_one_time` and `heldout_bh_power_down_after_read` (the chip stops converting, so a later change in light is not seen)
are caught only by the light-change check in the default-address scenario; a bus model that returns a fixed reading
cannot see them.

## Gaps found and closed

| Gap | Now asserted in |
|-----|-----------------|
| A stale reading drawn under an OK headline passed | host `transient_read_failure` |
| Fault text drawn on a display that never answered passed | host `display_missing` |
| The failed-rebind guard was untestable | host `sensor_missing_at_boot` (`fail_begin_call`) |
| A period measured from zero, not from boot, passed | host `clock_wrap` |
| A NACK on the chip-id, soft-reset or status write during init was ignored | vendor `transient_data_nack`, three isolated sub-cases (`data_nack_skip`) |
| A chip answering with another identity (a BMP280 answers 0x58) was accepted or counted as a second sensor | vendor `both_addresses_answer`, decoy sub-case (`set_chip_id`) |
| A heap block leaked per failed retry (the app retries a missing sensor forever) | vendor `sensor_absent_then_appears`, live-allocation count across retries |
| `setup()` requesting a bus clock other than 100 kHz | vendor `wire_pins_stay_explicit`, read before any loop |
| Bus recovery that never ended the bus, so the peripheral was never reset | vendor `wire_pins_stay_explicit`, at least two initialising explicit `begin()` calls |

Two more were found by lane 4 and are closed for both parts:

| Gap | Now asserted in |
|-----|-----------------|
| The display library calling `Wire.begin()` again (`periphBegin = true`) passed: the BH1750 harness only checked that no default-argument `begin()` initialised the bus, and on an initialised bus it is a no-op | BH1750 `wire_pins_stay_explicit`: the adapter makes no default-argument `begin()` at all, so any is a failure |
| The driver handed `Wire1`, which `setup()` never starts, passed: the Wire model carried transactions on a bus nobody had begun | The Wire model follows arduino-esp32 2.0.17 (`Wire.cpp` 447-450, 480-483, 525-528): no buffers means `endTransmission()` returns 4, `requestFrom()` returns 0, `write()` returns 0 |

The BME280 vendor harness output stayed byte-identical after both changes (all 11 scenarios, same SHA-256 prefix as before).

The clock check has to run straight after `setup()`: Adafruit_SSD1306 restores the clock to 100 kHz after its
own init, which hides whatever `setup()` asked for. Sub-cases run in forked children because the adapter keeps
function-static state. The scenario sets stay at 15 and 11.

## Reviewed survivors

- **Equivalent.** `setup()` and bus recovery re-applying `Wire.setTimeOut(50)`: in arduino-esp32 2.0.17
  (espressif32@6.10.0) the `TwoWire` constructor sets `_timeOutMillis(50)` (Wire.cpp:48) and `end()` never
  touches it. Valid for that framework version only. `bus_recover()` returning false: `SensorApp` discards its
  result with `(void)` at both call sites. Three further equivalents in the logic lane carry their reasons in the script.
- **Equivalent (BH1750 adapter).** `SensorApp` reads only after a `sensor_begin()` of the same device succeeded, so the
  driver's `configured_` flag and its reset are never observable (`bh_failed_begin_stays_configured`,
  `heldout_bh_read_without_configuration`). Valid for `SensorApp` as written. Dropping the checked result of `requestFrom`
  (`bh_short_read_unchecked`) leaves `read()` returning -1, which yields about 14 million lx and is rejected by the plausibility
  range; valid while that ceiling stays below it. Dropping the empty fourth display line (`heldout_adapter_fourth_line_dropped`)
  is pixel-identical for a one-channel display, though it is a real bug for the BME280's four lines.
- **Blind spot (BH1750 adapter).** Starting the chip in L-resolution or H-resolution mode 2 (`bh_mode_low_resolution`,
  `heldout_bh_mode_two`): the model implements no resolution modes, so it cannot tell them from mode 1. Silicon would return
  a coarser or rescaled value. Both count against the score.
- **Blind spot.** Removing the 10 ms settle delay after a soft reset: the model has no start-up window in which
  the chip does not answer, so it cannot matter to the model. The datasheet specifies a start-up time and silicon may enforce it.

## What this does not show

- It scores the project's own tests against bugs chosen by their author (36 + 12 logic mutants, 23 + 9 BME280 adapter
  mutants, 28 + 11 BH1750 adapter mutants). It is not a measurement of Wokwi, Flux or any other tool; the smoke and healthy-bus detectors are
  subsets of this project's harnesses, not those tools.
- Everything runs against modelled buses. Silicon, ESP32 timing, the real Wire driver, pull-ups, supply and
  electrical behaviour are untested here, and so is the compiled ESP32 binary.
- Nothing changes any authority flag: `physical_correctness` stays `UNPROVEN`, flashing and power-on stay closed.

Evidence, all under `docs/status/generated/`: `device-fault-matrix-{original,strengthened}-harness-2026-10-12.json`,
`device-fault-matrix-bh1750-2026-10-12.json` and `device-adapter-matrix-{original,strengthened}-vendor-host-2026-10-12.json` and
`device-adapter-matrix-bh1750-{original,strengthened}-vendor-host-2026-10-13.json`.
