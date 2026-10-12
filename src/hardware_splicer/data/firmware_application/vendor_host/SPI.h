#pragma once
#include "Arduino.h"

#define SPI_HAS_TRANSACTION 1
#define SPI_MSBFIRST 1
#define SPI_LSBFIRST 0
#define MSBFIRST SPI_MSBFIRST
#define LSBFIRST SPI_LSBFIRST
#define SPI_MODE0 0x00
#define SPI_MODE1 0x01
#define SPI_MODE2 0x02
#define SPI_MODE3 0x03
#define SPI_INTERFACES_COUNT 1

class SPISettings {
public:
    SPISettings() = default;
    SPISettings(uint32_t clock, uint8_t bitOrder, uint8_t dataMode)
        : clock_(clock), bit_order_(bitOrder), data_mode_(dataMode) {}

private:
    uint32_t clock_ = 1000000;
    uint8_t bit_order_ = SPI_MSBFIRST;
    uint8_t data_mode_ = SPI_MODE0;
};

class SPIClass {
public:
    void begin() {}
    void end() {}
    void beginTransaction(SPISettings) {}
    void endTransaction() {}
    uint8_t transfer(uint8_t v) { return v; }
    void transfer(void *, size_t) {}
    void transferBytes(const uint8_t *, uint8_t *, size_t) {}
    void writeBytes(const uint8_t *, size_t) {}
    uint8_t transferBits(uint8_t v, uint8_t) { return v; }
    void setFrequency(uint32_t) {}
    void setBitOrder(uint8_t) {}
    void setDataMode(uint8_t) {}
};

extern SPIClass SPI;
