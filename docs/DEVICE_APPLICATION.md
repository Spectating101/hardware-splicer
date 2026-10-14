# Device-plan application source

The device page can already download a compile-only I2C diagnostic sketch.
That sketch reads no sensor and drives no display. This package is the next
deliverable: a generated application for the catalog ESP32-DevKitC V4 that
reads a BME280 breakout and, when one is wired, shows values on an SSD1306
OLED. A display is optional. The application logic is exercised off-hardware
against a modelled bus, with fault injection.

It reports and proposes. It does not approve flashing, powering or physical
use. A function never inherits an electrical contract.

The API is `build_device_application(spec) -> (metadata, zip_bytes)`. The
builder recomputes the plan from the spec and ignores caller-supplied findings
or authority flags. The same spec and library bytes produce the same ZIP
bytes. No local paths or timestamps enter the archive.

## What the user gets

A deterministic ZIP with:

- `src/app_core.h`: platform-independent C++17. All behaviour lives here. It
  includes no Arduino or ESP headers.
- `src/main.cpp`: a thin Arduino adapter. It calls
  `Wire.begin(SDA, SCL, 100000)` with the explicitly wired GPIOs, implements
  `Hal` with Adafruit BME280 and Adafruit SSD1306, and calls into
  `app_core.h`. It does not contain scheduling, fault, or range logic.
- `platformio.ini`: `espressif32@6.10.0`, `board = esp32dev`, Arduino,
  `monitor_speed = 115200`, and pinned Adafruit libraries.
- `test/host/harness.cpp` and `test/host/README.md`: the host behaviour tests.
- `test/vendor_host/`: Arduino shim, modelled I2C bus, BME280/SSD1306 register models, and a harness that compiles the real `src/main.cpp` with the pinned Adafruit sources.
- `DEVICE_SPEC.json`, `DEVICE_PLAN.json`, `FIRMWARE_PROPOSAL.json`, `README.md`.

`FIRMWARE_PROPOSAL.json` uses schema
`hardware_splicer.device_application_proposal.v1`. Status is
`HOST_TESTABLE_PROPOSAL`. `compilation` and `behaviour_tests` are `NOT_RUN`.
`firmware_authorized` and `power_on_authorized` are false.
`physical_correctness` is `UNPROVEN`. Declared devices keep their possible
addresses and the library basis; no address is chosen in the proposal.

## On the Raspberry Pi Pico

The same package is generated for the Pico. `src/app_core.h`, which holds everything the application does, is the same
file on both boards, so the host scenarios are the same scenarios. What differs is the adapter's I2C start and the compile
target:

- The RP2040 can put each of its two I2C controllers only on certain pins. The library marks each Pico pin with its
  controller (`i2c_controller`), the planner refuses SDA and SCL on different controllers, and the adapter uses `Wire` for
  I2C0 and `Wire1` for I2C1. It sets the pins with `setSDA`/`setSCL` before `begin()`, as the arduino-pico core requires;
  if the core refuses a pin, the sketch stops and says so on serial instead of running on other pins.
- The target is `board = pico` with the earlephilhower arduino-pico core, through
  [maxgerhardt/platform-raspberrypi](https://github.com/maxgerhardt/platform-raspberrypi) pinned to one commit. That
  platform is not in the PlatformIO registry; it is the usual way to build arduino-pico with PlatformIO. The registry's own
  `raspberrypi` platform uses the Mbed core, which does not set I2C pins this way.
- There is no vendor-host lane for the Pico. The host shim models the ESP32 Arduino core's `Wire`, so running it against a
  Pico adapter would test the wrong driver. The package says so in its claim boundary and ships no `test/vendor_host/`.
- The diagnostic address-probe sketch is still ESP32-only.

Checked on 2026-10-14 with `scripts/verify_device_application.py --platformio` (PlatformIO Core 6.1.18, the pinned platform
commit): the BME280 package on I2C0 (GP4/GP5) and on I2C1 (GP2/GP3, so `Wire1`), and the BH1750 package, each compiled
with exit 0 and produced an ELF and a BIN, and each passed its host scenarios. The first run downloads the RP2040 core and
toolchain (several minutes). A compile shows the adapter is valid C++ against that core; it is not a run on a Pico, and
nothing here was flashed.

## What is refused

Any planner error or warning blocks export, as with the diagnostic. Export
also refuses when:

- the MCU is neither the catalog ESP32-DevKitC V4 nor the Raspberry Pi Pico;
- there is no BME280 breakout (`adafruit-bme280-stemma-qt`);
- there is more than one BME280;
- any I2C peripheral other than the BME280 and the SSD1306 is present;
- the wiring is not exactly one shared SDA GPIO and one distinct SCL GPIO.

The application supports ESP32 + BME280 + optionally SSD1306. The diagnostic
export remains available for other catalog parts.

## Addresses are not assumed

The plan only knows possible addresses (BME280 `0x77`/`0x76`, SSD1306
`0x3C`/`0x3D`). The application tries the declared alternatives in order at
boot. For the BME280 it uses the address whose chip identity matches:
register `0xD0` equals `0x60`.

Bosch BME280 datasheet BST-BME280-DS001-24, register description:

> The “id” register contains the chip identification number chip_id[7:0],
> which is 0x60.

The chosen address is printed on serial (`BOOT sensor=0x76 display=0x3C`, or
`display=NONE`). If the BME280 answers at both declared addresses, that is
`FAULT_AMBIGUOUS_ADDRESS`. The application does not pick. After probing, if
exactly one address matched, `sensor_begin` is called again on that address so
the driver is bound there; a failed rebind rejects the probe. The bounded
adapter follows the binding behavior of Adafruit_BME280 2.3.0 `begin(addr, wire)`, which always
replaces its I2C device with one bound to `addr`, then returns false if the
chip id is not 0x60 — a failed begin leaves the driver bound to the address it
just tried.

## Host scenarios

The harness is a fake `Hal` with a scripted bus: per-address presence, chip
id, a queue of read results, injected faults, and a controllable clock. It
records every log and display call. It prints one JSON object per scenario
and exits non-zero if any fails. It is deterministic.

| Scenario | What it asserts | What it does not establish |
|---|---|---|
| `boot_ok` | Both devices found; serial reports the matched addresses; the first cycle shows a reading. The modelled chip is at `0x76` (the last declared address) | A real chip acknowledged, or that Adafruit `begin` works |
| `default_address_binding` | Chip at the first declared address `0x77`; after probing, the last `sensor_begin` is `0x77` and the first cycle shows a reading | That Adafruit `begin(addr, wire)` rebinds; that is library behaviour read from 2.3.0, modelled here |
| `sensor_missing_at_boot` | Neither sensor address matches → `FAULT_SENSOR_MISSING`, display `SENSOR MISSING`, the fault is logged once per state change, retries at 1 s, 2 s, 4 s … capped at 30 s, never blocks; when the sensor appears: `RECOVERED` and normal operation | Pull-ups, power, or that a missing ACK is the only failure mode |
| `display_missing` | `display_begin` fails at both addresses → readings stay on serial, `DISPLAY MISSING` once, `display_show` never called | That a particular OLED is absent on a real bus. Adafruit_SSD1306 2.5.17 `begin()` returns true without detecting the display; the adapter's presence check (`Wire.beginTransmission` / `endTransmission`) is verified by reading that pinned source and by the compile, not by this harness |
| `display_at_second_address` | Display answers at `0x3D` only: `BOOT` reports `display=0x3D` and the first reading reaches the display | That a particular OLED ACK'd at `0x3D` |
| `transient_read_failure` | 1–2 failed reads keep the last good value marked `STALE` and raise no fault; the 3rd consecutive failure → `FAULT_SENSOR_READ`, one `bus_recover()`, then re-begin; a good read logs `RECOVERED` | Electrical recovery, clock stretching, or library retry policy |
| `read_fault_persistent_recovery` | After `FAULT_SENSOR_READ`, retries use the missing-sensor backoff (1 s, 2 s, 4 s … capped at 30 s): each expiry `bus_recover()`, re-probes declared addresses (rebind if exactly one match; two matches → `FAULT_AMBIGUOUS_ADDRESS`), then reads; when the chip re-appears at the same address: `RECOVERED` and normal readings | That a real unplug/replug resets calibration, or that Adafruit `begin` restores it |
| `ambiguous_during_read_fault` | Enter `FAULT_SENSOR_READ`, then both declared sensor addresses match: `FAULT_AMBIGUOUS_ADDRESS`, no new reading, no address picked | Two physical chips appearing after a read fault |
| `second_read_fault_starts_at_one_second` | After a read-fault episode whose backoff has grown to at least 8 s and a recovery, the first retry of a second episode is 1000 ms after entering it | That a real chip's recovery timing matches this software backoff |
| `implausible_values` | Isolated NaN in humidity or pressure is rejected. Each of the six Bosch bounds is accepted at the edge (−40.0 °C, 85.0 °C, 0.0 %, 100.0 %, 300.0 hPa, 1100.0 hPa) and rejected just beyond. Far out-of-range values and all-NaN remain failed reads and are never shown | That a real BME280 cannot produce those numbers, or that Adafruit will return NaN |
| `clock_wrap` | `now_ms()` crossing `0xFFFFFFFF` → `0` neither stalls the 2000 ms schedule nor causes a burst of reads | Real `millis()` behaviour on a particular core |
| `read_period` | With the chip healthy: a reading at t=0, none at t=1999, one at t=2000, none at t=3999, one at t=4000 (1 ms steps around the edges, and 500 ms steps). `sensor_read` is called 6 times in a 10 s window | That 2000 ms is a validated sampling rate |
| `two_devices_answer` | Identity matches at both declared BME280 addresses → `FAULT_AMBIGUOUS_ADDRESS` once; over 60 s, zero `sensor_read` calls, zero reading lines, zero display readings | Two physical chips, address pin state, or a bus conflict |
| `first_read_fails` | The very first read fails: serial `STALE`, display `NO DATA` on the first line with the other lines empty, no fault | A blank OLED on hardware, or that Adafruit leaves the buffer uncleared |
| `serial_grammar` | Every serial line is one of the closed shapes below | Anything about UART wiring or baud |

Read period is 2000 ms. That is a software choice, not a validated rate.

Operating-range constants are the Bosch line:

> Operating range                  -40…+85 °C, 0…100 % rel. humidity, 300…1100 hPa

from BST-BME280-DS001-24 (the text capture at the datasheet extract used
while writing this package).

### Closed serial shapes

```
BOOT sensor=0xNN display=0xNN
BOOT sensor=0xNN display=NONE
T=<ms> STATE=OK TEMP_C=<%.2f> HUM_PCT=<%.1f> PRES_HPA=<%.1f>
T=<ms> STATE=STALE
T=<ms> STATE=FAULT_SENSOR_MISSING
T=<ms> STATE=FAULT_SENSOR_READ
T=<ms> STATE=FAULT_AMBIGUOUS_ADDRESS
DISPLAY MISSING
RECOVERED
```

A stale or fault line carries no temperature, humidity or pressure figures.
Those numbers would be ones the application cannot stand behind.

## Vendor-host scenarios

A second harness compiles the package's real `src/main.cpp` and `src/app_core.h` together
with the pinned Adafruit sources (BME280 2.3.0, SSD1306 2.5.17, GFX 1.12.6, BusIO 1.17.4,
Unified Sensor 1.1.15) on the host, against a shim of Arduino and of arduino-esp32 2.0.17
`TwoWire`, and a modelled I2C bus with fault injection. It drives `setup()` / `loop()`.

A pass shows that this adapter and this vendor code behave as modelled. It is **not**
silicon, **not** the ESP32 Wire driver's real timing, and **not** electrical behaviour.

The shim clock is simulated: `delay(ms)` advances it; nothing sleeps. `Wire.begin()` with
no arguments follows 2.0.17 `Wire.cpp`: it calls `begin(-1, -1, 0)`. If the bus is already
inited, that returns true without changing pins. Otherwise `initPins` reuses the prior
`sda`/`scl` if they were set, else the esp32dev defaults `SDA=21` `SCL=22`
(`variants/esp32/pins_arduino.h`).

BME280 registers follow BST-BME280-DS001-24 §5. Compensation compared to the library is
the datasheet §8.1 double-precision formulas, implemented independently. ADC and
calibration bytes used in the scenarios are **synthetic** and labelled so. Tolerance:
0.05 °C (Adafruit reports 0.01 °C steps from the integer formula), 0.2 hPa, 0.3 %RH
(integer / 64-bit Adafruit vs datasheet double; table 15 of the datasheet treats those as
different implementations).

SSD1306 command/data bytes are split on control byte `0x00` / `0x40` as Adafruit 2.5.17
writes them. After `display()`, pixels are compared with `GFXcanvas1` drawing the same
four text lines (the framebuffer encodings differ; the pixels must match).

| Scenario | What it asserts | What it does not establish |
|---|---|---|
| `sensor_default_address_0x77_with_display_0x3C` | `BOOT sensor=0x77 display=0x3C`; every `STATE=OK` line matches the §8.1 oracle; driver I2C reads go to `0x77`; OLED pixels match the four text lines | A real chip ACK'd, or ESP32 Wire timing |
| `sensor_0x76_only` | Second declared address; reads go to `0x76`; oracle match on a second synthetic calib/ADC set | Address-pin state of a particular module |
| `display_at_0x3D_only` | `BOOT` reports `display=0x3D`; framebuffer pixels match `GFXcanvas1` | A particular OLED geometry |
| `display_absent` | `DISPLAY MISSING` exactly once; after the 0x3C/0x3D presence probes, no further transaction to those addresses that is not a bare address probe; no framebuffer data | That Adafruit `begin()` would have detected the absence (2.5.17 returns true without probing; `Adafruit_SSD1306.cpp`: `return true; // Success`) |
| `sensor_absent_then_appears` | `FAULT_SENSOR_MISSING`; probes at backoff 1, 2, 4, 8 s of simulated time (including library `delay`s); then `RECOVERED` | Pull-ups or a missing ACK as the only failure mode |
| `unplug_replug_mid_run` | Unplug resets the model's registers (calibration lost until `begin()` reloads it); readings fail or are implausible; fault; retry re-begins; oracle values resume | That a real unplug power-cycles NVM the same way |
| `both_addresses_answer` | `FAULT_AMBIGUOUS_ADDRESS`; no readings | Two physical chips |
| `transient_data_nack` | 1–2 `requestFrom` / data-NACK failures → `STALE` then recovery, no fault | Library retry policy on hardware |
| `wire_pins_stay_explicit` | Pins in effect after boot and after fault/recovery are the planned GPIOs (example 21/22, and a spec on IO25/IO26). Default-arg `Wire.begin()` that actually inits the bus after `end()` fails the scenario | GPIO electrical behaviour |
| `blocking_budget` | Simulated time inside any one `loop()` stays within 250 ms: `2*(delay(10)+delay(100))` plus one calibration poll per successful `begin` (Adafruit_BME280.cpp:117–127) | That Adafruit `begin` is non-blocking on silicon |
| `im_update_never_clears` | Bounded initializer reports a fault without readings, stays bounded during retries, then recovers when the modeled calibration condition clears | Physical timing or correctness of a real device |

### Bounded calibration initialization

The earlier `im_update_never_clears` experiment found that Adafruit_BME280 2.3.0
`init()` waits without a timeout. The vendor files remain untouched. The generated
adapter now uses a `BoundedBme280` subclass that binds the device, checks the chip
ID and reset/status I2C results, waits at most 50 ms for calibration status to clear,
then reuses the vendor coefficient, sampling and compensation code. A failed
rebind is also a failed probe, never a successful boot.

`im_update_never_clears` is now a required passing regression: stuck calibration
must return a fault within the modeled software budget, produce no readings, stay
bounded during retries, and recover after the model clears that condition. A
mutation removing the timeout must fail this scenario. The 50 ms status deadline
and Wire transaction timeout are software choices, not validated physical timing.
Library calibration and compensation code is still tested; the unbounded vendor
`begin()`/`init()` path is deliberately not used by this application.

Both verifier lanes require every named scenario exactly once, literal boolean
passes, no findings, and a zero process exit status. Missing/duplicate results,
crashes, malformed output and a 60-second execution timeout are failures, not
partial successes.

The verifier takes `--vendor-libs DIR` pointing at a PlatformIO
`.pio/libdeps/application` tree. After `--platformio` it uses
`<project>/.pio/libdeps/application` automatically. If the libraries are not there it
writes `VENDOR_HOST_RESULT.json` with `pass: false` and
`reason: "not run: libraries not available"` — never a pass.

## What the host tests do not prove

They do not test the Adafruit libraries, the Wire driver, I2C timing, pull-up
values, supply rails, GPIO electrical behaviour, OLED geometry of a
particular module, or any real device. A passing scenario is not a sensor
reading and not permission to flash or power the board. Compilation, when
run separately, is still only a compiler result.

Display presence is checked by reading the pinned Adafruit_SSD1306 2.5.17
source (`Adafruit_SSD1306.cpp`, `return true; // Success`) and by the
compile of `main.cpp` (`Wire.beginTransmission` / `endTransmission` before
`begin(..., true, false)`). The host harness does not prove that.

The adapter's bounded initialization still calls `delay(10)` and `delay(100)`;
a successful initialization blocks for roughly 110 ms plus bounded status polling.
`loop_once()` is non-blocking only in application logic.

## What this does not prove

The same boundary. Host scenarios, a clean host compile, and a PlatformIO
compile of the adapter are not a sensor reading, not a display, not proof
that Adafruit `begin` is non-blocking, and not permission to flash or power
the board.

## How to run

Host tests from an extracted package:

```sh
g++ -std=c++17 -Wall -Wextra -Werror -I src test/host/harness.cpp -o harness && ./harness
```

From the repo, rebuild the proposal and run the same harness:

```sh
PYTHONPATH=src .venv/bin/python scripts/verify_device_application.py
```

That always writes `BEHAVIOUR_RESULT.json` (`schema_version`
`hardware_splicer.device_application_behaviour.v1`) with `pass`, the
scenario list, `core_sha256`, `harness_sha256`, the compiler version string,
the claim boundary above, and the closed authority flags.

Optional PlatformIO compile with Core **6.1.18** (same pin as the diagnostic
verifier). Use a separate environment; do not replace the product API
dependencies:

```sh
PYTHONPATH=src .venv/bin/python scripts/verify_device_application.py \
  --platformio .cache/hardware-splicer/firmware-tools/bin/pio
```

`PLATFORMIO_CORE_DIR` defaults to the diagnostic cache:

`.cache/hardware-splicer/device-firmware/platformio-core` under the repository root

`--example` and `--spec` select the input the same way as
`scripts/verify_device_firmware.py`. A compile run writes `COMPILE_RESULT.json`.
`--vendor-libs DIR` runs the vendor-host harness and writes `VENDOR_HOST_RESULT.json`.
The source ZIP continues to say `compilation=NOT_RUN` and
`behaviour_tests=NOT_RUN`; the separate result files record execution. Do not
upload from this package.

If the sandbox has no network, PlatformIO cannot download the pinned
libraries. That is a missing compile, not a pass.

## Pinned libraries

These versions were taken from the PlatformIO registry listings:

- [adafruit/Adafruit BME280 Library 2.3.0](https://registry.platformio.org/libraries/adafruit/Adafruit%20BME280%20Library)
- [adafruit/Adafruit SSD1306 2.5.17](https://registry.platformio.org/libraries/adafruit/Adafruit%20SSD1306)
- [adafruit/Adafruit GFX Library 1.12.6](https://registry.platformio.org/libraries/adafruit/Adafruit%20GFX%20Library)
- [adafruit/Adafruit BusIO 1.17.4](https://registry.platformio.org/libraries/adafruit/Adafruit%20BusIO)
- [adafruit/Adafruit Unified Sensor 1.1.15](https://registry.platformio.org/libraries/adafruit/Adafruit%20Unified%20Sensor)

The platform is [espressif32 v6.10.0](https://github.com/platformio/platform-espressif32/releases/tag/v6.10.0).
Board profile `esp32dev` is a compile target, not exact physical-board
identification.

## Bosch sources

- Chip id: BST-BME280-DS001-24 §5.4.1 Register 0xD0 “id” — chip_id[7:0] is 0x60.
- Operating range: key-features line “Operating range -40…+85 °C, 0…100 % rel. humidity, 300…1100 hPa”.
