#pragma once
// Empty stand-in. Adafruit_SSD1306.cpp includes <util/delay.h> unless __ARM_ARCH is defined; the Pico's ARM compiler
// defines it, so the real build skips the include. This host build is x86 and leaves __ARM_ARCH alone, and the library
// uses nothing from this header.
