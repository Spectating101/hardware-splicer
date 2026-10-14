// Pins the RP2040 Wire model to the behaviour of arduino-pico's Wire.cpp at commit fd65f6d4. Each check names the
// real behaviour it holds the model to. Prints one line per failed check and exits non-zero if any failed.
#include <cstdio>
#include <string>

#include "Wire.h"

static int failures = 0;
#define CHECK(cond, what)                                   \
    do {                                                    \
        if (!(cond)) {                                      \
            std::printf("FAIL %s\n", what);                 \
            failures += 1;                                  \
        }                                                   \
    } while (0)

class Probe : public I2cDevice {
public:
    bool here = true;
    uint8_t write_result = 0;
    bool present() const override { return here; }
    uint8_t on_write(const uint8_t *, size_t) override { return here ? write_result : 2; }
    size_t on_read(uint8_t *data, size_t len) override {
        for (size_t i = 0; i < len; ++i) data[i] = static_cast<uint8_t>(0xA0 + i);
        return here ? len : 0;
    }
};

template <typename F>
static bool panics(F f) {
    try {
        f();
    } catch (const HsPanic &) {
        return true;
    }
    return false;
}

int main() {
    Probe dev;
    g_i2c_bus.attach(0x40, &dev);

    // Constructor: variant pins and TWI_CLOCK.
    CHECK(Wire.sda_pin() == 4 && Wire.scl_pin() == 5, "Wire defaults to GP4/GP5");
    CHECK(Wire1.sda_pin() == 26 && Wire1.scl_pin() == 27, "Wire1 defaults to GP26/GP27");
    CHECK(Wire.getClock() == 100000, "TWI_CLOCK is 100 kHz");

    // setSDA/setSCL: the controller's pin table; anything else panics instead of returning false.
    CHECK(Wire1.setSDA(2) && Wire1.setSCL(3), "Wire1 accepts GP2/GP3");
    CHECK(panics([] { Wire1.setSDA(4); }), "Wire1 panics on GP4, an I2C0 pin");
    CHECK(panics([] { Wire.setSCL(4); }), "Wire panics on GP4 as SCL");
    CHECK(Wire.setSDA(4) && Wire.setSCL(5), "Wire accepts GP4/GP5");

    // begin(): starts once; a second begin() on a running bus is a no-op; changing a pin while running panics; the
    // same pin while running is accepted.
    Wire.begin();
    Wire.begin();
    CHECK(Wire.inited(), "begin() starts the bus");
    CHECK(Wire.begin_calls().size() == 2 && Wire.begin_calls()[0].actually_inited && !Wire.begin_calls()[1].actually_inited,
          "begin() on a running bus does not start it again");
    CHECK(Wire.setSDA(4), "the same SDA pin while running is accepted");
    CHECK(panics([] { Wire.setSDA(8); }), "a different SDA pin while running panics");

    // endTransmission: probe 0/2, data 0, any write NACK 4 (never 3), not begun 4.
    Wire.beginTransmission(0x40);
    CHECK(Wire.endTransmission() == 0, "a zero-length probe of a present device is 0");
    Wire.beginTransmission(0x41);
    CHECK(Wire.endTransmission() == 2, "a zero-length probe of an absent address is 2");
    Wire.beginTransmission(0x40);
    Wire.write(0xD0);
    CHECK(Wire.endTransmission() == 0, "an accepted data write is 0");
    Wire.beginTransmission(0x41);
    Wire.write(0xD0);
    CHECK(Wire.endTransmission() == 4, "a data write to an absent address is 4, not 2");
    dev.write_result = 3;
    Wire.beginTransmission(0x40);
    Wire.write(0xD0);
    CHECK(Wire.endTransmission() == 4, "a data NACK is 4 on this core, not 3");
    dev.write_result = 0;
    CHECK(Wire.endTransmission() == 4, "endTransmission without beginTransmission is 4");
    g_i2c_bus.remaining_data_nacks = 1;
    Wire.beginTransmission(0x40);
    Wire.write(0xD0);
    CHECK(Wire.endTransmission() == 4, "an injected data NACK is 4");

    // requestFrom: bytes from a present device; 0 from an absent one, for a zero request, or past the buffer.
    CHECK(Wire.requestFrom(0x40, size_t(3)) == 3 && Wire.read() == 0xA0, "requestFrom reads a present device");
    CHECK(Wire.requestFrom(0x41, size_t(3)) == 0, "requestFrom of an absent address is 0");
    CHECK(Wire.requestFrom(0x40, size_t(0)) == 0, "requestFrom of 0 bytes is 0");
    CHECK(Wire.requestFrom(0x40, size_t(257)) == 0, "requestFrom past the 256-byte buffer is 0");

    // end() then begin() restarts; end() on a stopped bus is a no-op.
    Wire.end();
    CHECK(!Wire.inited(), "end() stops the bus");
    Wire.end();
    Wire.begin();
    CHECK(Wire.inited() && Wire.begin_calls().back().actually_inited, "begin() after end() starts the bus again");

    // The other controller's traffic goes to the other bus, never the planned one.
    const size_t planned_before = g_i2c_bus.log.size();
    Wire1.begin();
    Wire1.beginTransmission(0x40);
    CHECK(Wire1.endTransmission() == 2, "the planned bus's device does not answer on the other controller");
    CHECK(g_i2c_bus.log.size() == planned_before && g_i2c_bus_other.log.size() == 1, "Wire1 traffic is logged on the other bus");

    std::printf("%s\n", failures ? "MODEL CHECKS FAILED" : "MODEL CHECKS PASSED");
    return failures ? 1 : 0;
}
