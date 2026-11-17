// SPDX-License-Identifier: GPL-3.0-or-later
// 0.67rc: a log of what the player does on the physical pad, so a run played by hand can be replayed with
// the input bridge (tools/input-record-to-route.py turns it into a route for the bridge's route tool).
//
// /data/eden-nx2/logs/input-record.csv, one line per change of the pad state:
//   t_ms,buttons_hex,lx,ly,rx,ry,l2,r2
// t_ms counts from the launch (steady clock). A change is any button, or a stick or trigger moved by 3 or more
// steps; a button change is always written, an axis-only change at most once per 20 ms. The first line of a
// launch is a "# launch" comment with the wall time. Only physical pad samples are recorded (the bridge's own
// inputs are applied later and never reach this). /data/eden-nx2/input-record-off.txt switches it off.
#pragma once

#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <ctime>
#include <string>
#include "ps5_pad.hpp"

namespace Eden {

class InputRecorder {
public:
    // `directory` is the data directory (a test passes its own).
    explicit InputRecorder(const std::string& directory) {
        if (std::FILE* off = std::fopen((directory + "/input-record-off.txt").c_str(), "r")) {
            std::fclose(off);
            std::puts("EDEN_INPUT_RECORD off (input-record-off.txt)");
            return;
        }
        // Appended: a relaunch after a crash must not overwrite the minutes before it.
        file = std::fopen((directory + "/logs/input-record.csv").c_str(), "a");
        if (!file) {
            std::printf("EDEN_INPUT_RECORD off (cannot open %s/logs/input-record.csv)\n", directory.c_str());
            return;
        }
        start = Clock::now();
        last_flush = start;
        const std::time_t wall = std::time(nullptr);
        std::fprintf(file, "# launch wall_unix=%lld columns=t_ms,buttons_hex,lx,ly,rx,ry,l2,r2\n",
                     static_cast<long long>(wall));
        std::fflush(file);
        std::puts("EDEN_INPUT_RECORD on (logs/input-record.csv)");
    }
    InputRecorder(const InputRecorder&) = delete;
    InputRecorder& operator=(const InputRecorder&) = delete;
    ~InputRecorder() {
        if (file) std::fclose(file);
    }

    // One physical sample of player 1, in the order it was read. Cheap when nothing changed.
    void Observe(const ps5::pad::Data& sample) {
        if (!file || !ps5::pad::is_usable(sample)) return;
        const auto now = Clock::now();
        const std::uint32_t buttons = sample.buttons & ~ps5::pad::kButtonIntercepted;
        const std::array<std::uint8_t, 6> axes{sample.left_stick.x,  sample.left_stick.y, sample.right_stick.x,
                                               sample.right_stick.y, sample.triggers.l2,   sample.triggers.r2};
        const bool button_change = !have_last || buttons != last_buttons;
        if (!button_change && !AxesChanged(axes)) return;
        const auto t_ms =
            static_cast<long long>(std::chrono::duration_cast<std::chrono::milliseconds>(now - start).count());
        // An axis-only change is held back for up to 20 ms; nothing is stored until a line is written, so the
        // change is picked up by a later sample and a return to centre is never lost.
        if (!button_change && t_ms - last_t_ms < 20) return;
        std::fprintf(file, "%lld,%08x,%u,%u,%u,%u,%u,%u\n", t_ms, buttons, axes[0], axes[1], axes[2], axes[3],
                     axes[4], axes[5]);
        last_buttons = buttons;
        last_axes = axes;
        last_t_ms = t_ms;
        have_last = true;
        if (now - last_flush >= std::chrono::seconds(1)) {
            std::fflush(file);
            last_flush = now;
        }
    }

private:
    using Clock = std::chrono::steady_clock;
    bool AxesChanged(const std::array<std::uint8_t, 6>& axes) const {
        for (std::size_t i = 0; i < axes.size(); ++i) {
            const int delta = static_cast<int>(axes[i]) - static_cast<int>(last_axes[i]);
            if ((delta < 0 ? -delta : delta) >= 3) return true;
        }
        return false;
    }
    std::FILE* file = nullptr;
    Clock::time_point start{};
    Clock::time_point last_flush{};
    bool have_last = false;
    std::uint32_t last_buttons = 0;
    std::array<std::uint8_t, 6> last_axes{128, 128, 128, 128, 0, 0};
    long long last_t_ms = 0;
};

} // namespace Eden
