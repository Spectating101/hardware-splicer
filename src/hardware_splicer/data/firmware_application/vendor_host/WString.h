#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>

class String {
public:
    String() = default;
    String(const char *value) : text_(value ? value : "") {}
    String(const String &other) = default;
    String &operator=(const String &other) = default;
    String &operator=(const char *value) {
        text_ = value ? value : "";
        return *this;
    }
    const char *c_str() const { return text_.c_str(); }
    size_t length() const { return text_.size(); }
    bool operator==(const char *other) const { return text_ == (other ? other : ""); }

private:
    std::string text_;
};
