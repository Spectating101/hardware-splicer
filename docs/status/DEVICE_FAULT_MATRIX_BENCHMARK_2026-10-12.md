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

The clock check has to run straight after `setup()`: Adafruit_SSD1306 restores the clock to 100 kHz after its
own init, which hides whatever `setup()` asked for. Sub-cases run in forked children because the adapter keeps
function-static state. The scenario sets stay at 15 and 11.

## Reviewed survivors

- **Equivalent.** `setup()` and bus recovery re-applying `Wire.setTimeOut(50)`: in arduino-esp32 2.0.17
  (espressif32@6.10.0) the `TwoWire` constructor sets `_timeOutMillis(50)` (Wire.cpp:48) and `end()` never
  touches it. Valid for that framework version only. `bus_recover()` returning false: `SensorApp` discards its
  result with `(void)` at both call sites. Three further equivalents in the logic lane carry their reasons in the script.
- **Blind spot.** Removing the 10 ms settle delay after a soft reset: the model has no start-up window in which
  the chip does not answer, so it cannot matter to the model. The datasheet specifies a start-up time and silicon may enforce it.

## What this does not show

- It scores the project's own tests against bugs chosen by their author (36 + 12 logic mutants, 23 + 9 adapter
  mutants). It is not a measurement of Wokwi, Flux or any other tool; the smoke and healthy-bus detectors are
  subsets of this project's harnesses, not those tools.
- Everything runs against modelled buses. Silicon, ESP32 timing, the real Wire driver, pull-ups, supply and
  electrical behaviour are untested here, and so is the compiled ESP32 binary.
- Nothing changes any authority flag: `physical_correctness` stays `UNPROVEN`, flashing and power-on stay closed.

Evidence, all under `docs/status/generated/`: `device-fault-matrix-{original,strengthened}-harness-2026-10-12.json`
and `device-adapter-matrix-{original,strengthened}-vendor-host-2026-10-12.json`.
