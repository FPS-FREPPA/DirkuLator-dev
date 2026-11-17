// SPDX-License-Identifier: GPL-3.0-or-later
// 0.69rc: the console writes its own summary of a run, so a run nobody watched still leaves a result.
//
// /data/eden-nx2/logs/run-summary-<launch wall clock>.txt, one file per launch, rewritten every 30 s (so a crash or a
// power cut leaves a version at most 30 s old) and at a clean exit. Plain text, `key=value` lines:
//   launch / build / elapsed / gameplay seconds (from the first second with more than 8,000 draws), FPS statistics,
//   the slow waves with their FPS, GPU busy, draws and draw cost per draw, the same figures for the slow and the
//   healthy seconds, the audio output pacing (EDEN_AUDIO_OUT totals), and the busiest sampled addresses of the GPU
//   threads in slow and healthy periods when the PC sampler is on (pc_sampler.h).
// A second is slow under 6 frames and healthy from 10 frames. A wave is a run of slow seconds with gaps of at most
// 3 seconds that holds at least 10 slow seconds.
// Fed from the one-second monitor (perf_monitor.h), the audio output thread (audio.cpp) and the sampler thread.
// /data/eden-nx2/run-summary-off.txt switches it off.
#pragma once

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <ctime>
#include <fstream>
#include <iterator>
#include <mutex>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace Eden::RunSummary {

struct Wave {
    double start_s = 0, end_s = 0, fps = 0, gpu_busy = 0, draws = 0, us_per_draw = 0;
};

class Recorder {
public:
    // The data directory ("/data/eden-nx2") and the install directory (for the version).
    void Init(const std::string& data_dir, const std::string& install_dir) {
        std::lock_guard lock(mutex);
        if (std::ifstream(data_dir + "/run-summary-off.txt").good()) {
            std::puts("EDEN_RUN_SUMMARY off (run-summary-off.txt)");
            return;
        }
        launch_wall = static_cast<long long>(std::time(nullptr));
        path = data_dir + "/logs/run-summary-" + std::to_string(launch_wall) + ".txt";
        build = ReadVersion(install_dir + "/sce_sys/param.json");
        active = true;
        last_write = std::chrono::steady_clock::now();
        std::printf("EDEN_RUN_SUMMARY on (%s)\n", path.c_str());
    }

    // One second of the monitor. A negative gpu_busy means unknown.
    void AddSecond(double t_s, unsigned frames, unsigned long long draws, double draw_ms, int gpu_busy,
                   double submit_ms, double fence_drain_ms) {
        std::lock_guard lock(mutex);
        if (!active) return;
        elapsed_s = t_s;
        if (!gameplay && draws > 8000) {
            gameplay = true;
            gameplay_start_s = t_s;
        }
        if (!gameplay) return;
        ++seconds;
        ++fps_histogram[std::min(frames, 63u)];
        fps_sum += frames;
        no_frame += frames == 0;
        under8 += frames < 8;
        at_least12 += frames >= 12;
        // Each second is classified on its own, so the per-draw figures of the two classes are not blurred at the
        // edge of a wave.
        const bool is_slow = frames < 6;
        Totals* cls = is_slow ? &slow : (frames >= 10 ? &healthy : nullptr);
        if (cls) {
            ++cls->seconds;
            cls->frames += frames;
            cls->draws += draws;
            cls->draw_ms += draw_ms;
            cls->submit_ms += submit_ms;
            cls->fence_drain_ms += fence_drain_ms;
            if (gpu_busy >= 0) {
                cls->gpu_busy += gpu_busy;
                ++cls->gpu_known;
            }
        }
        if (is_slow && !run.active) {
            run = {};
            run.active = true;
            run.start_s = t_s;
        }
        if (run.active) {
            ++run.sums.seconds;
            run.sums.frames += frames;
            run.sums.draws += static_cast<double>(draws);
            run.sums.draw_ms += draw_ms;
            if (gpu_busy >= 0) {
                run.sums.gpu += gpu_busy;
                ++run.sums.gpu_n;
            }
            if (is_slow) {
                ++run.slow_seconds;
                run.gap = 0;
                run.last_slow_s = t_s;
                run.at_last_slow = run.sums;
            } else if (++run.gap > 3) {
                CloseRun();
            }
        }
        slow_now.store(run.active && run.slow_seconds >= 5, std::memory_order_relaxed);
        MaybeWrite(false);
    }

    // A 5 s window of the audio output thread (audio.cpp).
    void AddAudioOut(unsigned long long blocks, unsigned long long late8, unsigned long long late16,
                     unsigned long long late50, double max_gap_ms) {
        std::lock_guard lock(mutex);
        if (!active) return;
        ++audio_reports;
        audio_blocks += blocks;
        audio_late8 += late8;
        audio_late16 += late16;
        audio_late50 += late50;
        audio_max_gap = std::max(audio_max_gap, max_gap_ms);
        if (late8) ++audio_windows_late;
    }

    // The busiest addresses of one report window of a sampled thread (pc_sampler.h), as printed text and counts.
    void AddPc(const std::string& target, const std::vector<std::pair<std::string, unsigned>>& entries) {
        std::lock_guard lock(mutex);
        if (!active) return;
        auto& table = (slow_now.load(std::memory_order_relaxed) ? pc_slow : pc_healthy)[target];
        for (const auto& [address, count] : entries) {
            auto it = table.find(address);
            if (it != table.end()) it->second += count;
            else if (table.size() < 50000) table.emplace(address, count);
        }
    }

    bool SlowNow() const { return slow_now.load(std::memory_order_relaxed); }

    // At a clean exit.
    void Flush() {
        std::lock_guard lock(mutex);
        if (active) MaybeWrite(true);
    }

    // The text of the summary (also what a test reads).
    std::string Text() {
        std::lock_guard lock(mutex);
        return Format();
    }

private:
    struct Totals {
        unsigned long long seconds = 0, frames = 0, draws = 0, gpu_known = 0;
        double draw_ms = 0, submit_ms = 0, fence_drain_ms = 0, gpu_busy = 0;
    };
    struct Sums {
        unsigned seconds = 0, gpu_n = 0;
        double frames = 0, draws = 0, draw_ms = 0, gpu = 0;
    };
    struct Run {
        bool active = false;
        double start_s = 0, last_slow_s = 0;
        unsigned slow_seconds = 0, gap = 0;
        Sums sums, at_last_slow;  // the sums at the last slow second leave out the trailing gap
    };

    static std::string ReadVersion(const std::string& param_json) {
        std::ifstream in(param_json);
        std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
        const std::string key = "\"contentVersion\"";
        const auto k = text.find(key);
        if (k == std::string::npos) return "unknown";
        const auto a = text.find('"', text.find(':', k) + 1);
        const auto b = a == std::string::npos ? a : text.find('"', a + 1);
        return b == std::string::npos ? "unknown" : text.substr(a + 1, b - a - 1);
    }

    static Wave WaveOf(const Run& r) {
        Wave w;
        w.start_s = r.start_s;
        w.end_s = r.last_slow_s;
        const Sums& m = r.at_last_slow;
        w.fps = m.seconds ? m.frames / m.seconds : 0;
        w.gpu_busy = m.gpu_n ? m.gpu / m.gpu_n : -1;
        w.draws = m.seconds ? m.draws / m.seconds : 0;
        w.us_per_draw = m.draws > 0 ? 1000.0 * m.draw_ms / m.draws : 0;
        return w;
    }

    void CloseRun() {
        if (run.slow_seconds >= 10) {
            if (waves.size() < 64) waves.push_back(WaveOf(run));
            ++wave_count;
        }
        run = {};
    }

    void MaybeWrite(bool force) {
        const auto now = std::chrono::steady_clock::now();
        if (!force && now - last_write < std::chrono::seconds(30)) return;
        last_write = now;
        const std::string text = Format();
        const std::string temp = path + ".tmp";
        if (std::FILE* f = std::fopen(temp.c_str(), "w")) {
            std::fwrite(text.data(), 1, text.size(), f);
            std::fclose(f);
            std::rename(temp.c_str(), path.c_str());  // the last complete version always exists
        }
    }

    std::string Format() {
        std::string out;
        char buf[400];
        std::snprintf(buf, sizeof buf, "launch_wall_unix=%lld\nbuild=%s\nelapsed_s=%.0f\n", launch_wall, build.c_str(),
                      elapsed_s);
        out += buf;
        if (!gameplay) return out + "gameplay=not reached (no second with more than 8000 draws)\n";
        std::snprintf(buf, sizeof buf, "gameplay_start_s=%.0f\ngameplay_seconds=%llu\n", gameplay_start_s, seconds);
        out += buf;
        unsigned long long seen = 0, median = 0;  // from the histogram
        for (unsigned i = 0; i < fps_histogram.size(); ++i) {
            seen += fps_histogram[i];
            if (seen * 2 >= seconds) {
                median = i;
                break;
            }
        }
        std::snprintf(buf, sizeof buf,
                      "fps_mean=%.1f\nfps_median=%llu\nseconds_no_frame=%llu\nseconds_under_8fps=%llu\n"
                      "seconds_12fps_or_more=%llu\n",
                      seconds ? static_cast<double>(fps_sum) / seconds : 0.0, median, no_frame, under8, at_least12);
        out += buf;
        const auto totals = [&](const char* name, const Totals& t) {
            const double us = t.draws ? 1000.0 * t.draw_ms / t.draws : 0;
            const double n = static_cast<double>(t.seconds);
            std::snprintf(buf, sizeof buf,
                          "%s_seconds=%llu\n%s_fps=%.1f\n%s_gpu_busy_pct=%.0f\n%s_draws_per_s=%.0f\n"
                          "%s_draw_ms_per_s=%.0f\n%s_us_per_draw=%.0f\n%s_submit_ms_per_s=%.0f\n"
                          "%s_fence_drain_ms_per_s=%.0f\n",
                          name, t.seconds, name, n ? t.frames / n : 0.0, name,
                          t.gpu_known ? t.gpu_busy / t.gpu_known : -1.0, name, n ? t.draws / n : 0.0, name,
                          n ? t.draw_ms / n : 0.0, name, us, name, n ? t.submit_ms / n : 0.0, name,
                          n ? t.fence_drain_ms / n : 0.0);
            out += buf;
        };
        totals("slow", slow);
        totals("healthy", healthy);
        const bool open = run.active && run.slow_seconds >= 10;
        std::snprintf(buf, sizeof buf, "slow_waves=%u\n", wave_count + (open ? 1 : 0));
        out += buf;
        std::vector<Wave> all = waves;
        if (open) all.push_back(WaveOf(run));  // the open wave, as it stands
        for (const Wave& w : all) {
            std::snprintf(buf, sizeof buf,
                          "wave=t %.0f-%.0f s (%.0f s), %.1f FPS, GPU busy %.0f %%, %.0f draws/s, %.0f us per draw\n",
                          w.start_s, w.end_s, w.end_s - w.start_s + 1, w.fps, w.gpu_busy, w.draws, w.us_per_draw);
            out += buf;
        }
        std::snprintf(buf, sizeof buf,
                      "audio_out_reports=%u\naudio_out_blocks=%llu\naudio_out_late_over_8ms=%llu\n"
                      "audio_out_late_over_16ms=%llu\naudio_out_late_over_50ms=%llu\n"
                      "audio_out_windows_with_late_block=%u\naudio_out_max_gap_ms=%.1f\n",
                      audio_reports, audio_blocks, audio_late8, audio_late16, audio_late50, audio_windows_late,
                      audio_max_gap);
        out += buf;
        for (const auto* which : {&pc_slow, &pc_healthy}) {
            const char* label = which == &pc_slow ? "slow" : "healthy";
            for (const auto& [target, table] : *which) {
                std::vector<std::pair<std::string, unsigned long long>> rows(table.begin(), table.end());
                std::sort(rows.begin(), rows.end(), [](const auto& a, const auto& b) { return a.second > b.second; });
                unsigned long long total = 0;
                for (const auto& r : rows) total += r.second;
                std::snprintf(buf, sizeof buf, "pc_%s_%s_samples=%llu\n", label, target.c_str(), total);
                out += buf;
                for (std::size_t i = 0; i < rows.size() && i < 14; ++i) {
                    std::snprintf(buf, sizeof buf, "pc_%s_%s=%s %llu\n", label, target.c_str(), rows[i].first.c_str(),
                                  rows[i].second);
                    out += buf;
                }
            }
        }
        return out;
    }

    std::mutex mutex;
    bool active = false;
    std::string path, build = "unknown";
    long long launch_wall = 0;
    double elapsed_s = 0, gameplay_start_s = 0;
    bool gameplay = false;
    std::chrono::steady_clock::time_point last_write{};
    unsigned long long seconds = 0, fps_sum = 0, no_frame = 0, under8 = 0, at_least12 = 0;
    std::array<unsigned long long, 64> fps_histogram{};
    std::atomic<bool> slow_now{false};
    Totals slow, healthy;
    Run run;
    unsigned wave_count = 0;
    std::vector<Wave> waves;
    unsigned audio_reports = 0, audio_windows_late = 0;
    unsigned long long audio_blocks = 0, audio_late8 = 0, audio_late16 = 0, audio_late50 = 0;
    double audio_max_gap = 0;
    std::unordered_map<std::string, std::unordered_map<std::string, unsigned long long>> pc_slow, pc_healthy;
};

inline Recorder& Get() {
    static Recorder recorder;
    return recorder;
}

}  // namespace Eden::RunSummary
