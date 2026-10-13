# Vendor-host harness

Compiles the package's real `src/main.cpp` (Arduino adapter) and `src/app_core.h`
together with the pinned Adafruit library sources it uses, against a host Arduino
shim and a modelled I2C bus.

A pass shows that this adapter and this vendor code behave as modelled. It is
not silicon, not the ESP32 Wire driver's real timing, and not electrical
behaviour. It does not authorize flashing or power-on.

Needs the PlatformIO `libdeps/application` directory. If it is missing the
verifier reports `not run: libraries not available` and does not pass.

Clock: `millis` / `micros` are simulated. `delay(ms)` advances the clock; nothing
sleeps. The Wire model follows arduino-esp32 2.0.17: a bus that was never begun,
or was ended, has no buffers, so `endTransmission()` returns 4 and `requestFrom()`
returns 0.

Shared by every part: `Arduino.h`, `Wire.*`, `ssd1306_model.*` (the display) and
`vendor_common.h` (loop driver, process isolation, live-allocation counting).
Each part adds its own bus model and harness. The part's descriptor names its
profile in `PART_DESCRIPTOR.json` (`adapter.vendor_profile`).

## BME280 (`bme280`)

Needs BME280 2.3.0, SSD1306 2.5.17, GFX 1.12.6, BusIO 1.17.4, Unified Sensor 1.1.15.
Files: `models.*`, `vendor_harness.cpp`. All 11 scenarios must pass.

```sh
# From an extracted package, with LIBDEPS pointing at .pio/libdeps/application:
g++ -std=c++17 -Wall -Wextra -Wno-macro-redefined -DARDUINO=10812 -DESP32 -DARDUINO_ARCH_ESP32 \
  -I test/vendor_host -I src \
  -I "$LIBDEPS/Adafruit BME280 Library" \
  -I "$LIBDEPS/Adafruit SSD1306" \
  -I "$LIBDEPS/Adafruit GFX Library" \
  -I "$LIBDEPS/Adafruit BusIO" \
  -I "$LIBDEPS/Adafruit Unified Sensor" \
  src/main.cpp \
  test/vendor_host/arduino_core.cpp \
  test/vendor_host/Wire.cpp \
  test/vendor_host/ssd1306_model.cpp \
  test/vendor_host/models.cpp \
  test/vendor_host/vendor_harness.cpp \
  "$LIBDEPS/Adafruit BME280 Library/Adafruit_BME280.cpp" \
  "$LIBDEPS/Adafruit SSD1306/Adafruit_SSD1306.cpp" \
  "$LIBDEPS/Adafruit GFX Library/Adafruit_GFX.cpp" \
  "$LIBDEPS/Adafruit BusIO/Adafruit_I2CDevice.cpp" \
  "$LIBDEPS/Adafruit BusIO/Adafruit_SPIDevice.cpp" \
  "$LIBDEPS/Adafruit Unified Sensor/Adafruit_Sensor.cpp" \
  -o vendor_harness && ./vendor_harness
```

Prints one JSON object per scenario.
`im_update_never_clears` tests the adapter's bounded initializer: report a
fault without readings, remain bounded on retry, and recover after the model
clears calibration status. The upstream unbounded `init()` is not called;
vendor coefficient and compensation code is unchanged. This is still a model,
not a physical timing guarantee.

## BH1750 (`bh1750`)

The sensor is driven by the adapter's own `Wire` code, so only the display stack is
vendor code: SSD1306 2.5.17, GFX 1.12.6, BusIO 1.17.4.
Files: `models_bh1750.*`, `vendor_harness_bh1750.cpp`. All 11 scenarios must pass.

The bus model is written from the Rohm datasheet (2009.04 Rev.B), not from a vendor
library. The datasheet's own worked examples are the oracle (raw `0x8390` reads
28067 lx, raw `0x0110` reads 227 lx, p.7), so the divide-by-1.2 is not checked
against itself. The model has a power-down initial state, a data register that
resets to 0, conversion times of 180 ms (H) and 24 ms (L), one-time modes that
power down after measuring, and rejects opcodes the instruction set does not
define. It does not model L-resolution or H-resolution mode 2 quantisation, or
the measurement-time register.

```sh
g++ -std=c++17 -Wall -Wextra -Wno-macro-redefined -DARDUINO=10812 -DESP32 -DARDUINO_ARCH_ESP32 \
  -I test/vendor_host -I src \
  -I "$LIBDEPS/Adafruit SSD1306" \
  -I "$LIBDEPS/Adafruit GFX Library" \
  -I "$LIBDEPS/Adafruit BusIO" \
  src/main.cpp \
  test/vendor_host/arduino_core.cpp \
  test/vendor_host/Wire.cpp \
  test/vendor_host/ssd1306_model.cpp \
  test/vendor_host/models_bh1750.cpp \
  test/vendor_host/vendor_harness_bh1750.cpp \
  "$LIBDEPS/Adafruit SSD1306/Adafruit_SSD1306.cpp" \
  "$LIBDEPS/Adafruit GFX Library/Adafruit_GFX.cpp" \
  "$LIBDEPS/Adafruit BusIO/Adafruit_I2CDevice.cpp" \
  "$LIBDEPS/Adafruit BusIO/Adafruit_SPIDevice.cpp" \
  -o vendor_harness && ./vendor_harness
```
