# Running the compiled firmware in an emulator — feasibility, 2026-10-12

Goal: run the actual ESP32 binary (not the host model) against scripted I2C faults, and compare it with
the host results. This note records what was checked, what was not, and the protocol for finishing it.
Nothing here is an emulator result: **no emulator was run**.

## What was verified

Public documentation read on 2026-10-12 (not hands-on):

| Route | Stated | Not stated |
|-------|--------|------------|
| [Wokwi custom chips](https://docs.wokwi.com/chips-api/i2c) | C or WASM, beta. `connect` and `write` callbacks return a bool (`false` = NACK). A read cannot be refused | Whether a scenario can change chip behaviour at runtime |
| [Wokwi scenarios](https://docs.wokwi.com/wokwi-ci/automation-scenarios) | Ten steps (`wait-serial`, `set-control`, `expect-pin`, `take-screenshot`, ...), alpha | Any bus-fault or missing-device control |
| Wokwi parts | SSD1306 is I2C-only (the SSD1306 page is deprecated in favour of `board-ssd1306`) | A BME280 part; the supported-hardware list omits it |
| [Velxio](https://developer.espressif.com/blog/2026/07/velxio-browser-based-esp32-simulation/) | AGPLv3 core, QEMU-based, lists ESP32 DevKit C V4, protocol-level I2C for OLED and sensors, BMP280 demo | BME280, SSD1306, headless or CI use |
| [Espressif QEMU](https://docs.espressif.com/projects/esp-idf/en/latest/api-guides/tools/qemu.html) | ESP32 supported | Which peripherals; I2C is not mentioned |
| Renode | An [Xtensa ISA port](https://antmicro.com/blog/2022/01/xtensa-isa-in-renode-for-sof-project) exists | Any official ESP32 peripheral models |

Checked in a sandbox container:

- The ESP32 firmware builds. `scripts/verify_device_application.py --platformio` with PlatformIO Core 6.1.18
  passed all three lanes: 15/15 core, compile, 11/11 vendor-host. Observed once, not claimed reproducible:
  `firmware.bin` 310,784 bytes, SHA-256 `c5e773d8...f0282e`; toolchain `toolchain-xtensa-esp32` 8.4.0,
  `framework-arduinoespressif32` 3.20017.241212 (arduino-esp32 2.0.17).
- GitHub, including release downloads and the API, returned 403 from the container's shell, so Espressif's QEMU
  fork, the Wokwi CLI and Renode releases could not be fetched. No Docker daemon was running. Docker Hub was
  rate-limited. Ubuntu's `qemu-system-misc` is upstream QEMU, which has no ESP32 machine.
- `intel/esp-qemu` on Docker Hub is **not** an ESP32 emulator: its metadata is a generic Alpine VM launcher
  (`bootstrapVm.sh`, `apk add qemu-system...`). Do not use it.

## Protocol for a machine with network access

Take the CI-compiled `firmware.bin` (plus `bootloader.bin` and `partitions.bin`) for `esp32_oled_bme280_usb`.
For each candidate (Wokwi CLI with a custom chip, self-hosted Velxio, Espressif QEMU) answer four yes/no
questions and record the exact versions:

1. Does the firmware boot and print the application's serial lines?
2. Does the SSD1306 acknowledge at 0x3C and accept frames?
3. Does the BME280 return readings that match the datasheet 8.1 oracle for the model's calibration?
4. Can a script make the sensor NACK mid-run, deterministically, from outside the firmware?

Reuse the existing 26 scenarios as fault timelines and treat any host-model versus emulator disagreement as a
finding, not a failure of either side. Whatever runs, the report keeps `physical_correctness: UNPROVEN` and both
authority flags false.

## Decision rule

If no candidate answers question 4 with yes, the emulator adds only a happy-path check over what the host model
already does, and is not worth building into the product. If one does, wire it in as a separate service, never
vendored: Velxio is AGPLv3 and this repository is MIT.
