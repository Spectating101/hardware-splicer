#include "ssd1306_model.h"
#include <algorithm>
#include <cstring>

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
