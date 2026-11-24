#pragma once
// Helpers shared by every part's vendor-host harness: the simulated loop driver, event counters, the SSD1306
// pixel comparison, process isolation for sub-cases and live-allocation counting. Not part-specific.
// A pass is not silicon, not the ESP32 Wire driver's real timing, and not electrical behaviour.
#include "Arduino.h"
#include "Wire.h"
#include <stdexcept>
#include "ssd1306_model.h"
#include <Adafruit_GFX.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>
#include <regex>
#include <string>
#include <sys/wait.h>
#include <unistd.h>
#include <vector>

extern void setup();
extern void loop();

// Live heap blocks, counted across the harness, the adapter and the pinned Adafruit sources. The application
// retries a missing sensor forever, so a block leaked per attempt is a real failure mode; this can see it.
static long g_live_allocs = 0;
void *operator new(std::size_t size) {
    void *block = std::malloc(size ? size : 1);
    if (!block) throw std::bad_alloc();
    g_live_allocs += 1;
    return block;
}
void operator delete(void *block) noexcept {
    if (!block) return;
    g_live_allocs -= 1;
    std::free(block);
}
void operator delete(void *block, std::size_t) noexcept { operator delete(block); }

// Live blocks that belong to the adapter and the vendor sources: the bus log keeps a vector per recorded payload,
// and those are the harness's own allocations, not the application's.
[[maybe_unused]] static long live_allocs_excluding_bus_log() {
    long logged = 0;
    for (const auto &tx : g_i2c_bus.log)
        if (!tx.bytes.empty()) logged += 1;
    return g_live_allocs - logged;
}

[[maybe_unused]] static std::string json_escape(const std::string &text) {
    std::string out;
    out.reserve(text.size() + 8);
    for (char ch : text) {
        if (ch == '\\') out += "\\\\";
        else if (ch == '"') out += "\\\"";
        else if (ch == '\n') out += "\\n";
        else out += ch;
    }
    return out;
}

[[maybe_unused]] static int count_exact(const std::vector<std::string> &lines, const std::string &want) {
    int n = 0;
    for (const auto &line : lines)
        if (line == want) n += 1;
    return n;
}

[[maybe_unused]] static int count_contains(const std::vector<std::string> &lines, const std::string &part) {
    int n = 0;
    for (const auto &line : lines)
        if (line.find(part) != std::string::npos) n += 1;
    return n;
}

[[maybe_unused]] static bool call_loop(uint32_t *elapsed = nullptr) {
    sim_begin_loop();
    try {
        loop();
    } catch (const WatchdogAbort &) {
    }
    if (elapsed) *elapsed = sim_loop_elapsed_ms();
    const bool hung = g_sim_clock.watchdog_fired;
    sim_end_loop();
    return !hung;
}

static uint32_t g_max_loop_ms = 0;

[[maybe_unused]] static bool tracked_loop() {
    uint32_t elapsed = 0;
    const bool ok = call_loop(&elapsed);
    if (elapsed > g_max_loop_ms) g_max_loop_ms = elapsed;
    return ok;
}

[[maybe_unused]] static void pump_to(uint32_t t_ms) {
    while (millis() < t_ms) {
        const uint32_t now = millis();
        const uint32_t step = (t_ms - now > 50) ? 50 : (t_ms - now);
        if (step == 0) break;
        sim_advance_ms(step);
        if (!tracked_loop()) return;
    }
}

[[maybe_unused]] static bool framebuffer_matches(const Ssd1306Model &oled, const std::string &l1, const std::string &l2,
                                const std::string &l3, const std::string &l4, std::string &detail) {
    // Pixel compare, not raw buffer: GFXcanvas1 packs horizontally MSB-first
    // (Adafruit_GFX.cpp:2077); SSD1306 packs vertically by page
    // (Adafruit_SSD1306.cpp:678). Same four println() calls must light the same
    // pixels.
    GFXcanvas1 canvas(128, 64);
    canvas.fillScreen(0);
    canvas.setTextSize(1);
    canvas.setTextColor(1);
    canvas.setCursor(0, 0);
    canvas.println(l1.c_str());
    canvas.println(l2.c_str());
    canvas.println(l3.c_str());
    canvas.println(l4.c_str());
    for (int y = 0; y < 64; ++y) {
        for (int x = 0; x < 128; ++x) {
            if (oled.pixel(x, y) != canvas.getPixel(x, y)) {
                detail = "framebuffer pixels differ from GFXcanvas1 at " + std::to_string(x) + "," +
                         std::to_string(y);
                return false;
            }
        }
    }
    return true;
}

[[maybe_unused]] static bool default_begin_inited_bus() {
    for (const auto &c : Wire.begin_calls()) {
        if (c.default_args && c.actually_inited) return true;
    }
    return false;
}

[[maybe_unused]] static int default_begin_count() {
    int n = 0;
    for (const auto &c : Wire.begin_calls())
        if (c.default_args) n += 1;
    return n;
}

struct Result {
    bool pass = false;
    std::string detail;
    bool finding = false;
};

// The adapter keeps function-static state and a simulated clock, so each sub-case runs in a forked child
// that starts from the same pristine process and reports its Result through a pipe.
[[maybe_unused]] static Result run_isolated(Result (*fn)(int), int arg) {
    int fds[2];
    if (pipe(fds) != 0) return {false, "could not create a pipe for an isolated case", false};
    const pid_t pid = fork();
    if (pid < 0) return {false, "could not fork an isolated case", false};
    if (pid == 0) {
        close(fds[0]);
        Result r;
        try {
            r = fn(arg);
        } catch (const std::exception &error) {
            r.detail = std::string("the core halted: ") + error.what();
        }
        const std::string wire = std::string(r.pass ? "1" : "0") + r.detail;
        const ssize_t sent = write(fds[1], wire.data(), wire.size());
        (void)sent;
        _exit(0);
    }
    close(fds[1]);
    std::string got;
    char chunk[512];
    for (ssize_t n; (n = read(fds[0], chunk, sizeof chunk)) > 0;) got.append(chunk, static_cast<size_t>(n));
    close(fds[0]);
    int status = 0;
    waitpid(pid, &status, 0);
    if (got.empty() || !WIFEXITED(status) || WEXITSTATUS(status) != 0) return {false, "an isolated case did not finish", false};
    return {got[0] == '1', got.substr(1), false};
}

// Runs the named scenario, or every scenario in its own forked child, printing one JSON line each.
[[maybe_unused]] static int vendor_main(int argc, char **argv, const char *const *names, size_t count,
                                        Result (*run_named)(const char *)) {
    // A modelled core panic (an illegal pin on the RP2040, for example) throws; it fails the scenario with its message.
    auto guarded = [run_named](const char *name) -> Result {
        try {
            return run_named(name);
        } catch (const std::exception &error) {
            Result failed;
            failed.detail = std::string("the core halted: ") + error.what();
            return failed;
        }
    };
    if (argc >= 2 && argv[1][0] != '\0') {
        const Result r = guarded(argv[1]);
        std::printf("{\"scenario\":\"%s\",\"pass\":%s,\"detail\":\"%s\"%s}\n", argv[1],
                    r.pass ? "true" : "false", json_escape(r.detail).c_str(),
                    r.finding ? ",\"finding\":true" : "");
        std::fflush(stdout);
        return r.finding ? 0 : (r.pass ? 0 : 1);
    }
    bool all = true;
    for (size_t i = 0; i < count; ++i) {
        const char *name = names[i];
        const pid_t pid = fork();
        if (pid < 0) {
            std::fprintf(stderr, "fork failed\n");
            return 1;
        }
        if (pid == 0) {
            const Result r = guarded(name);
            std::printf("{\"scenario\":\"%s\",\"pass\":%s,\"detail\":\"%s\"%s}\n", name,
                        r.pass ? "true" : "false", json_escape(r.detail).c_str(),
                        r.finding ? ",\"finding\":true" : "");
            std::fflush(stdout);
            _exit(r.finding ? 0 : (r.pass ? 0 : 1));
        }
        int status = 0;
        waitpid(pid, &status, 0);
        if (!(WIFEXITED(status) && WEXITSTATUS(status) == 0)) all = false;
    }
    return all ? 0 : 1;
}
