# Device application, bench-scan check and CI repair — local verification, 2026-10-12

Branch `agent/hs-competitive-integration`, local HEAD `8693c91f`, on top of the pushed
`99de14a1`. Nothing here has been pushed or run on GitHub. The pushed `99de14a1` was red;
this record says why, what was fixed with proof, and what is still unknown.

This is a **proposal and test record**, not a release. No hardware was touched. The
application and its host tests are not a sensor reading and not permission to flash or
power anything; `firmware_authorized`, `power_on_authorized` stay false and
`physical_correctness` stays `UNPROVEN`.

## Why the push was red

| Failure on GitHub | Cause | Proof | Commit |
| --- | --- | --- | --- |
| 9 browser specs (comparison viewer, review packet, evidence viewport) | The proxy route directory is named `artifacts/`, which the root `artifacts/` ignore rule swallowed. It existed only on one machine, so no fresh clone had the route. | On a tracked-only checkout of `99de14a1` the specs gave 8 failed / 22 passed; at the fix 30 / 30. A guard test fails on the old rule. | `62223c88` |
| `test_pipeline_fake_java_writes_empty_ses` | CI installs KiCad 9.0.9; it writes the same nine graphic items in a different order than 9.0.2 and the guard compared them as a list. | Reproduced in the `kicad/kicad:9.0.9` image; 49 routing tests pass there after the fix. | `c497b69b` |
| `donor-capture` "Start again clears it" (about 1 run in 6) | The spec clicked a part with `force: true` in "Click to place" mode; when layout moved after a reload the click placed a second part. | The failure screenshot shows U2 over U1. 25 repeats, then 8 repeats of the whole file (104 runs), pass. | `92216299` |
| `closed_pan_tilt_mechatronics_project` scenario | The 3D-Splicer interpreter on the runner cannot use CadQuery. Reproduced exactly (`compile_ok=True claimable=False exit=1`) by removing CadQuery locally. **Why CI's copy is unusable is not established.** | Harness and setup now print the import error; needs one CI run to read it. | `e83ce8cf` |
| 3D tab, 2 specs | **Not reproduced locally**, including with KiCad 9.0.9's CLI. The mock said "kicad-cli is not installed" for any failure; it now reports the real exit status or timeout. | Needs one CI run. | `d50d8b65` |

## What was added

- **Bench-scan check** (`device_observations.py`, `POST /v1/devices/observations`, device-page
  panel). Compares pasted serial text with the plan's declared addresses per module. Reads the
  diagnostic's scan and the application's own `BOOT` / `STATE` lines. The text is
  operator-supplied and the result says so; an acknowledge is never an identity.
- **Application package** (`device_application.py`, `POST /v1/devices/application`,
  `docs/DEVICE_APPLICATION.md`). ESP32 + BME280 + optional SSD1306. Logic is in a
  platform-independent core with a host harness: 15 scenarios, 22 single-text mutations that
  must each fail it. Addresses are never assumed; the chip-id match decides.
- **Vendor-host harness.** Compiles the package's real `main.cpp` with the pinned Adafruit
  sources against a model of arduino-esp32 2.0.17's `TwoWire` and BME280/SSD1306 register
  models. 10 scenarios pass; one result is a finding, not a pass (below). 5 mutations of the
  generated sources must each fail a scenario that ran.
- **Three sourced breakouts**: INA219, MPU-6050, ADS1115 (45 verbatim quotes, each found in an
  independent fresh download of its cited source). AHT20 and SHT31-D were fetched and dropped:
  neither page publishes a Product Dimensions field for the current board.
- CI: the compile job also runs the application's host tests and compile; the new specs are in
  the device lists.

## Findings about vendor code (read from the pinned sources, then exercised)

- `Adafruit_BME280::begin(addr)` replaces its I2C device with one bound to `addr` before
  checking the chip id, so a failed `begin` leaves the driver bound to the address it tried.
  Probing the declared order 0x77, 0x76 would have left the driver bound to 0x76 after boot
  for a sensor at the default 0x77, so reads failed until the fault path re-began it. The core
  now rebinds after probing.
- `Adafruit_SSD1306::begin` returns true without detecting the display, so "display missing"
  could never fire and a display at 0x3D would never be found. The adapter checks for an
  acknowledge first.
- `Adafruit_BME280::init` waits `while (isReadingCalibration()) delay(10)` with no timeout; a
  chip whose `im_update` bit never clears hangs `begin()`. Recorded as a known limitation, not
  fixed.

## Local results (HEAD `8693c91f` unless stated)

| Check | Result |
| --- | --- |
| Full Python suite at `021ab8f2` (vendor libraries available) | 3592 passed, 13 skipped, 0 failed |
| Device, observation, guard and harness tests at HEAD | 363 passed |
| Real-API browser specs, tracked-only checkout of HEAD | 34 passed |
| Broader mock browser list (CI's), tracked-only checkout of HEAD | 107 passed |
| Application compile, PlatformIO Core 6.1.18 | pass (own run; exit 0, ELF and BIN produced) |
| Application host harness | 15 / 15 scenarios; 22 / 22 mutations caught |
| Vendor-host harness | 10 / 10 scenarios; 1 finding; 5 / 5 mutations caught |

## Still unknown or unproven

- The CadQuery and 3D-tab causes on GitHub's runner, above.
- Everything physical. The host and vendor-host harnesses are models: they do not test ESP32
  silicon, the real Wire driver's timing, supply, pull-ups or any real part.
- The library has eight modules, not a validated contract for every part.
- No browser or CI run of this HEAD on GitHub exists yet.
