#pragma once
#include "WString.h"
#include <cstdarg>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>

class __FlashStringHelper;

class Print {
public:
    virtual ~Print() = default;
    virtual size_t write(uint8_t ch) = 0;
    virtual size_t write(const uint8_t *buffer, size_t size) {
        size_t n = 0;
        if (!buffer) return 0;
        while (n < size) {
            if (write(buffer[n]) == 0) break;
            n += 1;
        }
        return n;
    }
    size_t write(const char *str) {
        if (!str) return 0;
        return write(reinterpret_cast<const uint8_t *>(str), strlen(str));
    }
    size_t print(const char *str) { return write(str); }
    size_t print(const String &str) { return write(str.c_str()); }
    size_t print(char ch) { return write(static_cast<uint8_t>(ch)); }
    size_t print(int value, int base = 10) { return print_number(static_cast<long>(value), base); }
    size_t print(unsigned int value, int base = 10) {
        return print_number(static_cast<unsigned long>(value), base);
    }
    size_t print(long value, int base = 10) { return print_number(value, base); }
    size_t print(unsigned long value, int base = 10) { return print_number(value, base); }
    size_t print(double value, int digits = 2) {
        char buf[64];
        std::snprintf(buf, sizeof buf, "%.*f", digits, value);
        return write(buf);
    }
    size_t println() { return write('\n'); }
    size_t println(const char *str) {
        size_t n = print(str);
        return n + println();
    }
    size_t println(const String &str) { return println(str.c_str()); }
    size_t println(char ch) {
        size_t n = print(ch);
        return n + println();
    }
    size_t println(int value, int base = 10) {
        size_t n = print(value, base);
        return n + println();
    }
    size_t println(unsigned int value, int base = 10) {
        size_t n = print(value, base);
        return n + println();
    }
    size_t println(long value, int base = 10) {
        size_t n = print(value, base);
        return n + println();
    }
    size_t println(unsigned long value, int base = 10) {
        size_t n = print(value, base);
        return n + println();
    }
    size_t println(double value, int digits = 2) {
        size_t n = print(value, digits);
        return n + println();
    }
    size_t printf(const char *fmt, ...) {
        char buf[256];
        va_list args;
        va_start(args, fmt);
        int n = std::vsnprintf(buf, sizeof buf, fmt, args);
        va_end(args);
        if (n <= 0) return 0;
        size_t len = static_cast<size_t>(n) < sizeof buf ? static_cast<size_t>(n) : sizeof buf - 1;
        return write(reinterpret_cast<const uint8_t *>(buf), len);
    }

private:
    size_t print_number(long value, int base) {
        char buf[34];
        if (base < 2) base = 10;
        std::snprintf(buf, sizeof buf, base == 16 ? "%lx" : (base == 8 ? "%lo" : "%ld"), value);
        return write(buf);
    }
    size_t print_number(unsigned long value, int base) {
        char buf[34];
        if (base < 2) base = 10;
        std::snprintf(buf, sizeof buf, base == 16 ? "%lx" : (base == 8 ? "%lo" : "%lu"), value);
        return write(buf);
    }
};
