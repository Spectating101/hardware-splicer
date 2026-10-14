// Host model of earlephilhower/arduino-pico TwoWire (libraries/Wire/src/Wire.cpp at commit fd65f6d4).
// Each function names the real one it mirrors. Drafted by Gemini 4 Argon; reviewed and integrated by Hardware-Splicer.
#include "Wire.h"

#include <cstdarg>
#include <cstdio>
#include <cstdlib>

static i2c_inst_t g_i2c0_inst{0};
static i2c_inst_t g_i2c1_inst{1};
i2c_inst_t *const i2c0 = &g_i2c0_inst;
i2c_inst_t *const i2c1 = &g_i2c1_inst;

I2cBus g_i2c_bus;
I2cBus g_i2c_bus_other;
int g_hs_planned_i2c = HS_PLANNED_I2C;

// Mirrors the Wire and Wire1 definitions at the end of Wire.cpp, with the Pico variant's pins.
TwoWire Wire(i2c0, PIN_WIRE0_SDA, PIN_WIRE0_SCL);
TwoWire Wire1(i2c1, PIN_WIRE1_SDA, PIN_WIRE1_SCL);

std::vector<std::string> &wire_panics() {
    static std::vector<std::string> panics;
    return panics;
}

[[noreturn]] static void record_and_throw_panic(const char *fmt, ...) {
    char buf[256];
    va_list args;
    va_start(args, fmt);
    std::vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    wire_panics().push_back(buf);
    throw HsPanic(buf);
}

void I2cBus::attach(uint8_t addr, I2cDevice *dev) { device[addr & 0x7f] = dev; }
void I2cBus::detach(uint8_t addr) { device[addr & 0x7f] = nullptr; }
void I2cBus::clear_log() { log.clear(); }
I2cDevice *I2cBus::at(uint8_t addr) const { return device[addr & 0x7f]; }

// Mirrors TwoWire::TwoWire(i2c_inst_t *i2c, pin_size_t sda, pin_size_t scl). The real constructor leaves the timeout
// members to Stream; the model starts them at setTimeout's declared defaults (25 ms, no reset).
TwoWire::TwoWire(i2c_inst_t *i2c, pin_size_t sda, pin_size_t scl) {
    _sda = sda;
    _scl = scl;
    _default_sda = sda;
    _default_scl = scl;
    _i2c = i2c;
    _clkHz = TWI_CLOCK;
    _running = false;
    _slave = false;
    _addr = 0;
    _txBegun = false;
    _timeout = 25;
    _timeoutFlag = false;
    _reset_with_timeout = false;
    _buffLen = 0;
    _buffOff = 0;
    _buffSize = WIRE_BUFFER_SIZE;
    _buff = static_cast<uint8_t *>(std::malloc(_buffSize));
}

TwoWire::~TwoWire() {
    std::free(_buff);
    _buff = nullptr;
}

I2cBus &TwoWire::bus() const {
    return (static_cast<int>(i2c_hw_index(_i2c)) == g_hs_planned_i2c) ? g_i2c_bus : g_i2c_bus_other;
}

void TwoWire::reset_model() {
    _sda = _default_sda;
    _scl = _default_scl;
    _sda_set = false;
    _scl_set = false;
    _clkHz = TWI_CLOCK;
    _running = false;
    _slave = false;
    _addr = 0;
    _txBegun = false;
    _timeout = 25;
    _timeoutFlag = false;
    _reset_with_timeout = false;
    _buffLen = 0;
    _buffOff = 0;
    begin_calls_.clear();
    wire_panics().clear();
}

// Mirrors TwoWire::setSDA(pin_size_t pin), RP2040 (not RP2350B) pin table.
bool TwoWire::setSDA(pin_size_t pin) {
    constexpr uint64_t valid[2] = {
        (1ULL << 0) | (1ULL << 4) | (1ULL << 8) | (1ULL << 12) | (1ULL << 16) | (1ULL << 20) | (1ULL << 24) | (1ULL << 28),
        (1ULL << 2) | (1ULL << 6) | (1ULL << 10) | (1ULL << 14) | (1ULL << 18) | (1ULL << 22) | (1ULL << 26),
    };
    const uint8_t idx = i2c_hw_index(_i2c) & 1;
    if (!_running && pin < 64 && ((1ULL << pin) & valid[idx])) {
        _sda = pin;
        _sda_set = true;
        return true;
    }
    if (_sda == pin) {
        _sda_set = true;
        return true;
    }
    if (_running) record_and_throw_panic("FATAL: Attempting to set Wire%s.SDA while running", idx ? "1" : "");
    record_and_throw_panic("FATAL: Attempting to set Wire%s.SDA to illegal pin %d", idx ? "1" : "", static_cast<int>(pin));
}

// Mirrors TwoWire::setSCL(pin_size_t pin), RP2040 (not RP2350B) pin table.
bool TwoWire::setSCL(pin_size_t pin) {
    constexpr uint64_t valid[2] = {
        (1ULL << 1) | (1ULL << 5) | (1ULL << 9) | (1ULL << 13) | (1ULL << 17) | (1ULL << 21) | (1ULL << 25) | (1ULL << 29),
        (1ULL << 3) | (1ULL << 7) | (1ULL << 11) | (1ULL << 15) | (1ULL << 19) | (1ULL << 23) | (1ULL << 27),
    };
    const uint8_t idx = i2c_hw_index(_i2c) & 1;
    if (!_running && pin < 64 && ((1ULL << pin) & valid[idx])) {
        _scl = pin;
        _scl_set = true;
        return true;
    }
    if (_scl == pin) {
        _scl_set = true;
        return true;
    }
    if (_running) record_and_throw_panic("FATAL: Attempting to set Wire%s.SCL while running", idx ? "1" : "");
    record_and_throw_panic("FATAL: Attempting to set Wire%s.SCL to illegal pin %d", idx ? "1" : "", static_cast<int>(pin));
}

// Mirrors TwoWire::setClock(uint32_t hz): stores; while running the real one also sets the baud rate.
void TwoWire::setClock(uint32_t hz) { _clkHz = static_cast<int>(hz); }

// Mirrors master-mode TwoWire::begin(): a no-op while running.
void TwoWire::begin() {
    WireBeginCall rec;
    rec.sda_arg = rec.sda_in_effect = static_cast<int>(_sda);
    rec.scl_arg = rec.scl_in_effect = static_cast<int>(_scl);
    rec.freq_arg = static_cast<uint32_t>(_clkHz);
    rec.default_args = !(_sda_set || _scl_set);
    rec.bus_was_inited = _running;
    if (_running) {
        rec.actually_inited = false;
        begin_calls_.push_back(rec);
        return;
    }
    _slave = false;
    _running = true;
    _txBegun = false;
    _buffLen = 0;
    rec.actually_inited = true;
    begin_calls_.push_back(rec);
}

// Mirrors slave-mode TwoWire::begin(uint8_t addr). Not used by the adapter; kept so a library call still compiles.
void TwoWire::begin(uint8_t addr) {
    if (_running) return;
    _slave = true;
    _addr = addr;
    _running = true;
}

// Mirrors TwoWire::end(): a no-op when not running. Pins are not reset to the variant defaults.
void TwoWire::end() {
    if (!_running) return;
    _running = false;
    _txBegun = false;
}

// Mirrors TwoWire::beginTransmission(uint8_t addr).
void TwoWire::beginTransmission(uint8_t addr) {
    if (!_running || _txBegun) return;
    _addr = addr;
    _buffLen = 0;
    _buffOff = 0;
    _txBegun = true;
}

// Mirrors TwoWire::_handleTimeout(bool reset), without the SDA-low bus-clear pulses (no pin-level model here).
void TwoWire::_handleTimeout(bool reset) {
    _timeoutFlag = true;
    if (!reset) return;
    const int prev_clkHz = _clkHz;
    if (_slave) {
        const uint8_t prev_addr = _addr;
        end();
        setClock(static_cast<uint32_t>(prev_clkHz));
        begin(prev_addr);
    } else {
        end();
        setClock(static_cast<uint32_t>(prev_clkHz));
        begin();
    }
}

// Mirrors TwoWire::requestFrom(uint8_t address, size_t quantity, bool stopBit): any failure reads 0 bytes.
size_t TwoWire::requestFrom(uint8_t address, size_t quantity, bool stopBit) {
    if (!_running || _txBegun || !quantity || (quantity > _buffSize)) return 0;
    I2cBus &b = bus();
    I2cTransaction tx;
    tx.address = address;
    tx.direction = I2cDir::Read;
    tx.stop = stopBit;
    I2cDevice *dev = b.at(address);
    if (b.remaining_read_fails > 0) {
        b.remaining_read_fails -= 1;
        _buffLen = 0;
        tx.result = 4;
    } else if (!dev || !dev->present()) {
        _buffLen = 0;
        tx.result = 2;
    } else {
        const size_t got = dev->on_read(_buff, quantity);
        _buffLen = static_cast<int>(got);
        tx.bytes.assign(_buff, _buff + got);
        tx.result = got ? 0 : 4;
    }
    _buffOff = 0;
    b.log.push_back(tx);
    return static_cast<size_t>(_buffLen);
}

size_t TwoWire::requestFrom(uint8_t address, size_t quantity) { return requestFrom(address, quantity, true); }

// Mirrors TwoWire::endTransmission(bool stopBit). A zero-length transmission is the _probe() path (0 or 2). A data
// write returns 4 on any NACK, address or data, because i2c_write_blocking_until's result differs from the length; 5 on a
// timeout. There is no 3 on this core.
uint8_t TwoWire::endTransmission(bool stopBit) {
    if (!_running || !_txBegun) return 4;
    _txBegun = false;
    I2cBus &b = bus();
    I2cTransaction tx;
    tx.address = _addr;
    tx.direction = I2cDir::Write;
    tx.bytes.assign(_buff, _buff + _buffLen);
    tx.stop = stopBit;
    tx.bare_probe = (_buffLen == 0);
    I2cDevice *dev = b.at(_addr);
    uint8_t result = 0;
    const auto injected = [&b]() -> uint8_t {
        const int value = b.next_write_result;
        b.next_write_result = -1;
        return value == 3 ? 4 : static_cast<uint8_t>(value);
    };
    if (!_buffLen) {
        result = b.next_write_result >= 0 ? injected() : ((dev && dev->present()) ? 0 : 2);
        tx.result = result;
        b.log.push_back(tx);
        return result;
    }
    const size_t len = static_cast<size_t>(_buffLen);
    auto device_write = [&]() -> uint8_t {
        if (!dev || !dev->present()) return 4;
        const uint8_t r = dev->on_write(_buff, len);
        return r == 0 ? 0 : (r == 5 ? 5 : 4);
    };
    if (b.next_write_result >= 0) {
        result = injected();
    } else if (b.remaining_data_nacks > 0 && b.data_nack_skip > 0) {
        b.data_nack_skip -= 1;
        result = device_write();
    } else if (b.remaining_data_nacks > 0) {
        b.remaining_data_nacks -= 1;
        result = 4;
    } else {
        result = device_write();
    }
    tx.result = result;
    b.log.push_back(tx);
    if (result == 5) {
        _handleTimeout(_reset_with_timeout);  // the real code returns here without clearing the buffer length
        return 5;
    }
    _buffLen = 0;
    return result;
}

uint8_t TwoWire::endTransmission() { return endTransmission(true); }

// Mirrors TwoWire::write(uint8_t): 0 when not running, not begun, or the buffer is full.
size_t TwoWire::write(uint8_t ucData) {
    if (!_running || _slave) return 0;
    if (!_txBegun || (_buffLen == static_cast<int>(_buffSize))) return 0;
    _buff[_buffLen++] = ucData;
    return 1;
}

// Mirrors TwoWire::write(const uint8_t *data, size_t quantity).
size_t TwoWire::write(const uint8_t *data, size_t quantity) {
    for (size_t i = 0; i < quantity; ++i) {
        if (!write(data[i])) return i;
    }
    return quantity;
}

int TwoWire::available(void) { return _running ? _buffLen - _buffOff : 0; }
int TwoWire::read(void) { return available() ? _buff[_buffOff++] : -1; }
int TwoWire::peek(void) { return available() ? _buff[_buffOff] : -1; }
void TwoWire::flush(void) {}

// Mirrors TwoWire::setTimeout(uint32_t timeout, bool reset_with_timeout).
void TwoWire::setTimeout(uint32_t timeout, bool reset_with_timeout) {
    _timeoutFlag = false;
    _timeout = timeout;
    _reset_with_timeout = reset_with_timeout;
}

bool TwoWire::getTimeoutFlag() { return _timeoutFlag; }
void TwoWire::clearTimeoutFlag() { _timeoutFlag = false; }

// Mirrors TwoWire::setBufferSize(size_t bSize).
size_t TwoWire::setBufferSize(size_t bSize) {
    if (_running || (_buffSize == bSize)) return _buffSize;
    const size_t newSize = static_cast<size_t>(max(WIRE_BUFFER_SIZE_MIN, static_cast<int>(bSize)));
    uint8_t *grown = static_cast<uint8_t *>(std::realloc(_buff, newSize));
    if (grown) {
        _buff = grown;
        _buffSize = newSize;
    }
    return _buffSize;
}
