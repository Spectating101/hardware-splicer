# Host behaviour harness

This tests `src/app_core.h` against a scripted I2C model. It does not test
Adafruit libraries, the Wire driver, timing, electrical behaviour, or any
real device.

```sh
g++ -std=c++17 -Wall -Wextra -Werror -I src test/host/harness.cpp -o harness && ./harness
```

The harness prints one JSON object per scenario and exits non-zero if any
fails. It uses a fake clock; it does not read the wall clock or inject
randomness.

Display presence is not modelled here. Adafruit_SSD1306 2.5.17 `begin()`
returns true without detecting the display (`Adafruit_SSD1306.cpp`:
`return true; // Success`). The adapter's `Wire.beginTransmission` check
is verified by reading that pinned source and by the compile, not by this
harness.
