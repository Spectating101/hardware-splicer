#pragma once
// Register-level models. Behaviour is taken from BST-BME280-DS001-24 and from
// the SSD1306 control-byte framing Adafruit 2.5.17 actually writes. Synthetic
// ADC and calibration bytes are labelled so. Not silicon.

#include "Wire.h"
#include <cstdint>
#include <vector>

struct Bme280Calib {
    uint16_t dig_T1 = 0;
    int16_t dig_T2 = 0;
    int16_t dig_T3 = 0;
    uint16_t dig_P1 = 0;
    int16_t dig_P2 = 0;
    int16_t dig_P3 = 0;
    int16_t dig_P4 = 0;
    int16_t dig_P5 = 0;
    int16_t dig_P6 = 0;
    int16_t dig_P7 = 0;
    int16_t dig_P8 = 0;
    int16_t dig_P9 = 0;
    uint8_t dig_H1 = 0;
    int16_t dig_H2 = 0;
    uint8_t dig_H3 = 0;
    int16_t dig_H4 = 0;
    int16_t dig_H5 = 0;
    int8_t dig_H6 = 0;
};

// Datasheet 8.1 double-precision formulas, implemented independently of Adafruit.
struct Bme280Oracle {
    double temp_c = 0;
    double pressure_pa = 0;
    double humidity_pct = 0;
    int32_t t_fine = 0;
};

Bme280Oracle bme280_oracle_double(const Bme280Calib &c, int32_t adc_T, int32_t adc_P, int32_t adc_H);

class Bme280Model final : public I2cDevice {
public:
    static constexpr uint8_t kChipId = 0x60;  // BST-BME280-DS001-24 §5.4.1

    explicit Bme280Model(uint8_t addr);
    void plug(const Bme280Calib &nvm, int32_t adc_T, int32_t adc_P, int32_t adc_H);
    void unplug();
    void set_adc(int32_t adc_T, int32_t adc_P, int32_t adc_H);
    void set_im_update_stuck(bool stuck);
    // A chip that answers at the address but is not a BME280 (e.g. a BMP280 answers 0x58).
    void set_chip_id(uint8_t id);
    bool present() const override { return present_; }
    uint8_t address() const { return addr_; }
    Bme280Calib nvm() const { return nvm_; }
    int32_t adc_T() const { return adc_T_; }
    int32_t adc_P() const { return adc_P_; }
    int32_t adc_H() const { return adc_H_; }
    Bme280Oracle oracle() const { return bme280_oracle_double(nvm_, adc_T_, adc_P_, adc_H_); }

    uint8_t on_write(const uint8_t *data, size_t len) override;
    size_t on_read(uint8_t *data, size_t len) override;

private:
    void por_from_nvm();
    void pack_calib();
    void pack_adc();
    uint8_t status_value() const;

    uint8_t addr_;
    bool present_ = false;
    bool im_update_stuck_ = false;
    uint8_t chip_id_ = kChipId;
    uint32_t reset_ms_ = 0;
    bool reset_pending_ = false;
    uint8_t ptr_ = 0;
    uint8_t reg_[256]{};
    Bme280Calib nvm_{};
    int32_t adc_T_ = 0;
    int32_t adc_P_ = 0;
    int32_t adc_H_ = 0;
};

class Ssd1306Model final : public I2cDevice {
public:
    static constexpr int kWidth = 128;
    static constexpr int kHeight = 64;
    static constexpr int kBuf = kWidth * (kHeight / 8);

    explicit Ssd1306Model(uint8_t addr);
    void plug();
    void unplug();
    bool present() const override { return present_; }
    uint8_t address() const { return addr_; }
    const std::vector<uint8_t> &commands() const { return commands_; }
    const uint8_t *framebuffer() const { return fb_; }
    bool saw_display_on() const;
    bool saw_data_bytes() const { return data_bytes_ > 0; }
    int data_bytes() const { return data_bytes_; }
    bool pixel(int x, int y) const;

    uint8_t on_write(const uint8_t *data, size_t len) override;
    size_t on_read(uint8_t *data, size_t len) override;

private:
    uint8_t addr_;
    bool present_ = false;
    uint8_t fb_[kBuf]{};
    size_t fb_index_ = 0;
    std::vector<uint8_t> commands_;
    int data_bytes_ = 0;
};

// Synthetic calibration / ADC sets. Not from a particular physical module.
Bme280Calib synthetic_calib_a();
Bme280Calib synthetic_calib_b();
void synthetic_adc_a(int32_t &t, int32_t &p, int32_t &h);
void synthetic_adc_b(int32_t &t, int32_t &p, int32_t &h);
