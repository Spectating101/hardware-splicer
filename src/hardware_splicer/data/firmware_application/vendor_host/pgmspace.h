#pragma once
// Host stand-in for avr/pgmspace.h / ESP32 pgmspace.h. Flash is RAM here.
#include <stdint.h>
#include <stddef.h>
#include <string.h>

#define PROGMEM
#define PGM_P const char *
#define PSTR(s) (s)

static inline uint8_t pgm_read_byte(const void *addr) {
    return *reinterpret_cast<const uint8_t *>(addr);
}
static inline uint16_t pgm_read_word(const void *addr) {
    uint16_t value;
    const uint8_t *p = reinterpret_cast<const uint8_t *>(addr);
    value = static_cast<uint16_t>(p[0]) | (static_cast<uint16_t>(p[1]) << 8);
    return value;
}
static inline uint32_t pgm_read_dword(const void *addr) {
    uint32_t value;
    const uint8_t *p = reinterpret_cast<const uint8_t *>(addr);
    value = static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
            (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24);
    return value;
}
static inline float pgm_read_float(const void *addr) {
    float value;
    const uint8_t *p = reinterpret_cast<const uint8_t *>(addr);
    uint32_t raw = static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
                   (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24);
    static_assert(sizeof(float) == 4, "float is 4 bytes");
    reinterpret_cast<uint32_t &>(value) = raw;
    return value;
}
#define pgm_read_byte_near(addr) pgm_read_byte(addr)
#define pgm_read_word_near(addr) pgm_read_word(addr)
#define pgm_read_dword_near(addr) pgm_read_dword(addr)
#ifndef pgm_read_pointer
#define pgm_read_pointer(addr) (*(const void *const *)(addr))
#endif
#define memcpy_P memcpy
#define strcpy_P strcpy
#define strlen_P strlen
#define sprintf_P sprintf
#define snprintf_P snprintf
