#pragma once
// Stand-in for the RP2040 core's api/deprecated-avr-comp/avr/pgmspace.h, which Adafruit_SSD1306.cpp includes on
// ARDUINO_ARCH_RP2040. Flash is RAM on this host, so it forwards to the shared host pgmspace.h.
#include "../../../pgmspace.h"
