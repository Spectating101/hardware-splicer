# Vendor-host harness

Compiles the package's real `src/main.cpp` (Arduino adapter) and `src/app_core.h`
together with the pinned Adafruit library sources against a host Arduino shim
and a modelled I2C bus.

A pass shows that this adapter and this vendor code behave as modelled. It is
not silicon, not the ESP32 Wire driver's real timing, and not electrical
behaviour. It does not authorize flashing or power-on.

Needs the PlatformIO `libdeps/application` directory (BME280 2.3.0, SSD1306
2.5.17, GFX 1.12.6, BusIO 1.17.4, Unified Sensor 1.1.15). If that directory is
missing the verifier reports `not run: libraries not available` and does not
pass.

Clock: `millis` / `micros` are simulated. `delay(ms)` advances the clock; nothing
sleeps.

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

Prints one JSON object per scenario. `im_update_never_clears` is a FINDING
about Adafruit_BME280 2.3.0, not a pass.
