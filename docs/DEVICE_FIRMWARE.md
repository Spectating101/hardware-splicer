# Device-plan diagnostic source

The device page can download a deterministic, compile-only I2C diagnostic
proposal for the catalog ESP32-DevKitC V4. This extends the existing firmware
scaffolding; it does not replace the verified-interface PlatformIO backend,
change its authorization gate or create another project/evidence store.

## What the user gets

Choose ESP32/OLED/BME280, check the wiring, then select **Download diagnostic
source**. The ZIP contains:

- `src/main.cpp`: a diagnostic sketch with explicitly wired GPIO numbers;
- `platformio.ini`: the pinned software target;
- `DEVICE_SPEC.json` and `DEVICE_PLAN.json`: the input and recomputed plan;
- `FIRMWARE_PROPOSAL.json`: input, plan and source hashes, declared addresses,
  source references, empty observations and closed authority flags;
- `README.md`: compilation instructions and physical-use limits.

The same spec and library bytes produce the same source ZIP bytes. No timestamps,
local paths, compiler output or binaries enter the source ZIP. Binary
reproducibility is not asserted.

The API is `POST /v1/devices/firmware`, taking the same raw spec or `{spec: ...}`
wrapper as `/plan`. It rechecks the spec, never trusts supplied findings, and
returns ZIP bytes. The browser proxy retains authorization forwarding, bounded
64-KiB requests and meaningful error messages. Editing a spec disables the
download until that exact text has been successfully checked. The server still
rechecks it independently.

## What is refused

Any planner error or warning blocks source export. Missing signals have no
fallback to GPIO21/22. Bus tracing works in either wire direction, through a
shared peripheral bus and with renamed module IDs. Export requires exactly one
data GPIO and one distinct clock GPIO shared by all I2C peripherals. Separate
buses are explicitly unsupported, not silently combined.

The library's BME280, BH1750 and DS3231 declarations are supported. Their address
alternatives remain declarations, with their original source/basis. Unsupported
hardware, flash/input-only/strapping/serial-pin problems, address conflicts and
unresolved wiring checks are refused. No donor analogy inherits this export.

## Compilation, separately

Install PlatformIO Core **6.1.18** in a separate environment; its dependencies
must not replace the product API's dependencies. Then run:

```sh
.venv/bin/python scripts/verify_device_firmware.py \
  --platformio .cache/hardware-splicer/firmware-tools/bin/pio
```

By default this compiles the ESP32/OLED/BME280 example. `--example`, `--spec`,
and `--output-root` select another supported input or output parent. Every run
creates a fresh directory, recomputes the proposal, and builds only that generated
project. No arbitrary uploaded ZIP or user-supplied build script is executed.
The command has no upload target and never opens a serial device.

The target is `espressif32@6.10.0`, Arduino, `esp32dev`. This is a compile profile,
not exact physical-board identification. Its pinned Arduino framework is
2.0.17. See the [official platform release](https://github.com/platformio/platform-espressif32/releases/tag/v6.10.0)
and [board profile](https://docs.platformio.org/en/latest/boards/espressif32/esp32dev.html).
The sketch's explicit-pin initialization and transmission APIs follow
[Espressif's Wire documentation](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/i2c.html).

`COMPILE_RESULT.json` records the exact proposal/source hashes, compiler version,
fixed command, exit status, log hash and ELF/BIN hashes. Success requires a zero
exit and both nonempty artifacts in a fresh build directory. Missing compiler,
wrong version, timeout, failing exit and missing artifacts cannot receive compile
credit. Reports retain `firmware_authorized=false`, `power_on_authorized=false`
and `physical_correctness=UNPROVEN` even when compilation passes. The source ZIP
continues to say `compilation=NOT_RUN`; the separate result, not a rewritten
proposal, records execution.

Successful runs also produce `compiled-diagnostic-proposal.zip`, containing that
unaltered source ZIP, compiler report/log and ELF/BIN artifacts. This is a
downloadable compiler bundle, not an authorized hardware release. It is not
claimed byte-reproducible: compiler outputs, logs and execution paths can vary.

## Physical-use limits

The sketch starts serial reporting but does not start Wire or automatically
scan at boot. A serial `s` requests an address probe; it is not an authorization
transaction. Wire uses the explicitly chosen pins, 100 kHz as a diagnostic
software choice (not validated timing), a timeout and non-reserved address range.
An ACK is reported as an observed ACK, not a chip identity or sensor reading.
Other bus errors are reported, not counted as successes. No sensor register
configuration, OLED graphics, temperature/humidity/time readout or physical
measurement is supplied by this diagnostic.

Probing still drives the bus and is not universally safe. This package does
not approve flashing, powering, voltage compatibility, pull-up values, enclosure
fit or manufacturing. Resolve exact hardware, supply and pull-up questions
through the existing review/bench process before any physical operation.

## Regression gate

`.github/workflows/device-plan-deliverables.yml` adds three independent jobs:
real product API headless browser checks; broader studio-fixture browser checks;
and actual ESP32 compilation. No model allowance, vendor login or physical
hardware is required. Dependency/toolchain downloads still require internet.
The broader browser job installs KiCad 9 symbol/footprint libraries for actual
donor lookup; the device/firmware-only job does not need them. Compiler and
product API dependencies are installed in separate Python environments.
Raw source packages, reports, service logs and compiler artifacts are uploaded
as CI artifacts, not promoted into canonical engineering evidence.

Locally, run:

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_device_firmware.py tests/test_firmware_scaffold.py
bash scripts/verify_device_frontend.sh real
bash scripts/verify_device_frontend.sh mock device-assembly device-firmware donor-lookup donor-device-handoff donor-capture evidence-
```

Run browser checks separately from the full Python suite. The harness builds an
isolated source copy, never reclaims occupied ports and never rebuilds the live
frontend. The dedicated download tests inspect the actual ZIP, check its hashes,
compare repeat responses, change GPIOs, and exercise refused/stale/oversized
inputs and upstream failures.
