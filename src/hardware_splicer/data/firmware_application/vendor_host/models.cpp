#include "models.h"
#include "Arduino.h"
#include <algorithm>
#include <cstring>

// BST-BME280-DS001-24 §8.1, lines ~2631–2682 of the text capture.
Bme280Oracle bme280_oracle_double(const Bme280Calib &c, int32_t adc_T, int32_t adc_P, int32_t adc_H) {
    Bme280Oracle out{};
    double var1 = (((double)adc_T) / 16384.0 - ((double)c.dig_T1) / 1024.0) * ((double)c.dig_T2);
    double var2 = ((((double)adc_T) / 131072.0 - ((double)c.dig_T1) / 8192.0) *
                   (((double)adc_T) / 131072.0 - ((double)c.dig_T1) / 8192.0)) *
                  ((double)c.dig_T3);
    out.t_fine = (int32_t)(var1 + var2);
    out.temp_c = (var1 + var2) / 5120.0;

    var1 = ((double)out.t_fine / 2.0) - 64000.0;
    var2 = var1 * var1 * ((double)c.dig_P6) / 32768.0;
    var2 = var2 + var1 * ((double)c.dig_P5) * 2.0;
    var2 = (var2 / 4.0) + (((double)c.dig_P4) * 65536.0);
    var1 = (((double)c.dig_P3) * var1 * var1 / 524288.0 + ((double)c.dig_P2) * var1) / 524288.0;
    var1 = (1.0 + var1 / 32768.0) * ((double)c.dig_P1);
    if (var1 == 0.0) {
        out.pressure_pa = 0;
    } else {
        double p = 1048576.0 - (double)adc_P;
        p = (p - (var2 / 4096.0)) * 6250.0 / var1;
        var1 = ((double)c.dig_P9) * p * p / 2147483648.0;
        var2 = p * ((double)c.dig_P8) / 32768.0;
        p = p + (var1 + var2 + ((double)c.dig_P7)) / 16.0;
        out.pressure_pa = p;
    }

    double var_H = (((double)out.t_fine) - 76800.0);
    var_H = (adc_H - (((double)c.dig_H4) * 64.0 + ((double)c.dig_H5) / 16384.0 * var_H)) *
            (((double)c.dig_H2) / 65536.0 *
             (1.0 + ((double)c.dig_H6) / 67108864.0 * var_H * (1.0 + ((double)c.dig_H3) / 67108864.0 * var_H)));
    var_H = var_H * (1.0 - ((double)c.dig_H1) * var_H / 524288.0);
    if (var_H > 100.0) var_H = 100.0;
    else if (var_H < 0.0) var_H = 0.0;
    out.humidity_pct = var_H;
    return out;
}

Bme280Calib synthetic_calib_a() {
    // Temperature/pressure words match the BMP280 datasheet compensation *example*
    // (not a particular BME280 module). Humidity words are synthetic.
    Bme280Calib c{};
    c.dig_T1 = 27504;
    c.dig_T2 = 26435;
    c.dig_T3 = -1000;
    c.dig_P1 = 36477;
    c.dig_P2 = -10685;
    c.dig_P3 = 3024;
    c.dig_P4 = 2855;
    c.dig_P5 = 140;
    c.dig_P6 = -7;
    c.dig_P7 = 15500;
    c.dig_P8 = -14600;
    c.dig_P9 = 6000;
    c.dig_H1 = 75;
    c.dig_H2 = 358;
    c.dig_H3 = 0;
    c.dig_H4 = 321;
    c.dig_H5 = 50;
    c.dig_H6 = 30;
    return c;
}

Bme280Calib synthetic_calib_b() {
    Bme280Calib c = synthetic_calib_a();
    c.dig_T1 = 28432;
    c.dig_T2 = 26789;
    c.dig_P1 = 35000;
    c.dig_H2 = 380;
    c.dig_H4 = 300;
    return c;
}

void synthetic_adc_a(int32_t &t, int32_t &p, int32_t &h) {
    t = 508450;
    p = 415148;
    h = 28012;
}

void synthetic_adc_b(int32_t &t, int32_t &p, int32_t &h) {
    t = 520000;
    p = 400000;
    h = 26000;
}

Bme280Model::Bme280Model(uint8_t addr) : addr_(addr & 0x7f) {}

void Bme280Model::pack_calib() {
    auto put16 = [&](uint8_t reg, uint16_t v) {
        reg_[reg] = static_cast<uint8_t>(v & 0xff);
        reg_[reg + 1] = static_cast<uint8_t>(v >> 8);
    };
    put16(0x88, nvm_.dig_T1);
    put16(0x8A, static_cast<uint16_t>(nvm_.dig_T2));
    put16(0x8C, static_cast<uint16_t>(nvm_.dig_T3));
    put16(0x8E, nvm_.dig_P1);
    put16(0x90, static_cast<uint16_t>(nvm_.dig_P2));
    put16(0x92, static_cast<uint16_t>(nvm_.dig_P3));
    put16(0x94, static_cast<uint16_t>(nvm_.dig_P4));
    put16(0x96, static_cast<uint16_t>(nvm_.dig_P5));
    put16(0x98, static_cast<uint16_t>(nvm_.dig_P6));
    put16(0x9A, static_cast<uint16_t>(nvm_.dig_P7));
    put16(0x9C, static_cast<uint16_t>(nvm_.dig_P8));
    put16(0x9E, static_cast<uint16_t>(nvm_.dig_P9));
    reg_[0xA1] = nvm_.dig_H1;
    put16(0xE1, static_cast<uint16_t>(nvm_.dig_H2));
    reg_[0xE3] = nvm_.dig_H3;
    // Table 16: 0xE4 / 0xE5[3:0] = dig_H4[11:4] / [3:0]; 0xE5[7:4] / 0xE6 = dig_H5[3:0] / [11:4]
    reg_[0xE4] = static_cast<uint8_t>((nvm_.dig_H4 >> 4) & 0xff);
    reg_[0xE5] = static_cast<uint8_t>((nvm_.dig_H4 & 0x0f) | ((nvm_.dig_H5 & 0x0f) << 4));
    reg_[0xE6] = static_cast<uint8_t>((nvm_.dig_H5 >> 4) & 0xff);
    reg_[0xE7] = static_cast<uint8_t>(nvm_.dig_H6);
}

void Bme280Model::pack_adc() {
    auto put20 = [&](uint8_t msb_reg, int32_t adc) {
        uint32_t raw = static_cast<uint32_t>(adc) << 4;
        reg_[msb_reg] = static_cast<uint8_t>((raw >> 16) & 0xff);
        reg_[msb_reg + 1] = static_cast<uint8_t>((raw >> 8) & 0xff);
        reg_[msb_reg + 2] = static_cast<uint8_t>(raw & 0xff);
    };
    put20(0xF7, adc_P_);
    put20(0xFA, adc_T_);
    reg_[0xFD] = static_cast<uint8_t>((adc_H_ >> 8) & 0xff);
    reg_[0xFE] = static_cast<uint8_t>(adc_H_ & 0xff);
}

void Bme280Model::por_from_nvm() {
    std::memset(reg_, 0, sizeof reg_);
    reg_[0xD0] = chip_id_;
    // Table 18 reset states for data MSBs.
    reg_[0xF7] = 0x80;
    reg_[0xFA] = 0x80;
    reg_[0xFD] = 0x80;
    pack_calib();
    pack_adc();
    reset_ms_ = millis();
    reset_pending_ = true;
}

void Bme280Model::plug(const Bme280Calib &nvm, int32_t adc_T, int32_t adc_P, int32_t adc_H) {
    nvm_ = nvm;
    adc_T_ = adc_T;
    adc_P_ = adc_P;
    adc_H_ = adc_H;
    present_ = true;
    im_update_stuck_ = false;
    por_from_nvm();
}

void Bme280Model::unplug() {
    present_ = false;
    std::memset(reg_, 0, sizeof reg_);
    reset_pending_ = false;
}

void Bme280Model::set_adc(int32_t adc_T, int32_t adc_P, int32_t adc_H) {
    adc_T_ = adc_T;
    adc_P_ = adc_P;
    adc_H_ = adc_H;
    if (present_) pack_adc();
}

void Bme280Model::set_im_update_stuck(bool stuck) { im_update_stuck_ = stuck; }

void Bme280Model::set_chip_id(uint8_t id) {
    chip_id_ = id;
    if (present_) reg_[0xD0] = id;
}

uint8_t Bme280Model::status_value() const {
    uint8_t status = 0;
    if (im_update_stuck_) {
        status |= 0x01;
    } else if (reset_pending_) {
        // After soft-reset / POR, im_update is 1 until NVM copy finishes.
        // Adafruit waits delay(10) then polls; we clear after 10 ms of simulated time.
        if (millis() - reset_ms_ < 10) status |= 0x01;
    }
    return status;
}

uint8_t Bme280Model::on_write(const uint8_t *data, size_t len) {
    if (!present_) return 2;
    if (len == 0) return 0;  // address-only probe (I2CDevice::detected / adapter presence check)
    ptr_ = data[0];
    for (size_t i = 1; i < len; ++i) {
        const uint8_t reg = ptr_;
        const uint8_t value = data[i];
        if (reg == 0xE0) {
            // §5.4.2: 0xB6 triggers the complete power-on-reset procedure.
            if (value == 0xB6) por_from_nvm();
        } else if (reg == 0xF2 || reg == 0xF4 || reg == 0xF5) {
            reg_[reg] = value;
        }
        ptr_ = static_cast<uint8_t>(ptr_ + 1);
    }
    return 0;
}

size_t Bme280Model::on_read(uint8_t *data, size_t len) {
    if (!present_) return 0;
    for (size_t i = 0; i < len; ++i) {
        uint8_t reg = ptr_;
        if (reg == 0xF3) data[i] = status_value();
        else data[i] = reg_[reg];
        ptr_ = static_cast<uint8_t>(ptr_ + 1);
    }
    return len;
}

Ssd1306Model::Ssd1306Model(uint8_t addr) : addr_(addr & 0x7f) {}

void Ssd1306Model::plug() {
    present_ = true;
    std::memset(fb_, 0, sizeof fb_);
    fb_index_ = 0;
    commands_.clear();
    data_bytes_ = 0;
}

void Ssd1306Model::unplug() {
    present_ = false;
    std::memset(fb_, 0, sizeof fb_);
    fb_index_ = 0;
    commands_.clear();
    data_bytes_ = 0;
}

bool Ssd1306Model::saw_display_on() const {
    return std::find(commands_.begin(), commands_.end(), 0xAF) != commands_.end();
}

bool Ssd1306Model::pixel(int x, int y) const {
    if (x < 0 || y < 0 || x >= kWidth || y >= kHeight) return false;
    return (fb_[x + (y / 8) * kWidth] & (1 << (y & 7))) != 0;
}

uint8_t Ssd1306Model::on_write(const uint8_t *data, size_t len) {
    if (!present_) return 2;
    if (len == 0) return 0;  // address-only presence probe
    const uint8_t control = data[0];
    if (control == 0x00) {
        for (size_t i = 1; i < len; ++i) commands_.push_back(data[i]);
    } else if (control == 0x40) {
        for (size_t i = 1; i < len; ++i) {
            fb_[fb_index_ % kBuf] = data[i];
            fb_index_ += 1;
            data_bytes_ += 1;
        }
    } else if ((control & 0x80) == 0x80) {
        // Co=1: one command/data byte follows, then another control.
        // Adafruit 2.5.17 uses Co=0 (0x00 / 0x40) for the sequences we see.
        if (len >= 2) {
            if (control & 0x40) {
                fb_[fb_index_ % kBuf] = data[1];
                fb_index_ += 1;
                data_bytes_ += 1;
            } else {
                commands_.push_back(data[1]);
            }
        }
    }
    return 0;
}

size_t Ssd1306Model::on_read(uint8_t *data, size_t len) {
    if (!present_) return 0;
    std::memset(data, 0, len);
    return len;
}
