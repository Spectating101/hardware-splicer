#pragma once
// Register-level model of the SSD1306 as the Adafruit 2.5.17 library drives it. Shared by every part's
// vendor-host harness. Not silicon.

#include "Wire.h"
#include <cstdint>
#include <vector>

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
