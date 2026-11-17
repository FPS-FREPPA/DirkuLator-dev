// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// DirkuLator 0.5.18: a performance monitor beside the overlay's FPS. Once a second it appends
// one line to /data/eden-nx2/logs/perf-monitor.csv and flushes it, so the record survives the
// crash restart that empties eden_log: frame-time percentiles and hitches (which the overlay's
// worst-of-second MS cannot show), where the GPU thread's time goes (draws, waits, submits,
// pipeline builds), the guest's own waits, and memory. Every column is a delta over that second
// of the counters performance.h already keeps; nothing new is timed on a hot path.
//
// On by default in this debug build (diagnostics stay on). /data/eden-nx2/perf-monitor-off.txt
// turns it off, and then the counters are only on while a profiling session wants them, as
// before. /data/eden-nx2/perf-hud-off.txt keeps the CSV but drops the overlay's
// "P99 .. DRW .. SHD .." pieces (hud.h).
//
// Cost: while it runs, the draw-path timers (timers_on) and the Vulkan API timers
// (vulkan_cost_enabled) stay on, which the profiling session already does for its first 20
// minutes: two clock reads per timed phase. Compare fps with perf-monitor-off.txt if that matters.
#include "run_summary.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <ctime>
#include <fstream>
#include <string>
#include <vector>

#include "hud.h"
#include "performance.h"
#include "storage_paths.h"

namespace Eden::PerfMonitor {
// The guest's frames, as the overlay counts them (graphics.cpp, OnFrameDisplayed): the interval
// before each one in milliseconds, in a ring the monitor reads once a second. 1024 holds a
// second at any rate the console reaches.
inline constexpr size_t kRing = 1024;
inline std::array<std::atomic<float>, kRing> intervals_ms{};
inline std::atomic<unsigned long long> frames{0};
inline std::atomic<bool> enabled{false};
// Called by the renderer thread for every guest frame shown. A gap of more than half a second is
// a loading stop, not a frame, and is left out (as HudClock leaves it out of the FPS).
inline void Frame(double now_seconds) {
    if (!enabled.load(std::memory_order_relaxed)) return;
    static double last = -1;
    if (last >= 0 && now_seconds - last <= 0.5) {
        const auto at = frames.fetch_add(1, std::memory_order_relaxed);
        intervals_ms[at % kRing].store(static_cast<float>((now_seconds - last) * 1000.0),
                                       std::memory_order_relaxed);
    }
    last = now_seconds;
}

class Monitor {
public:
    Monitor() {
        const std::string data{kDataDir};
        if (std::ifstream(data + "/perf-monitor-off.txt").good()) {
            std::puts("EDEN_PERF_MONITOR off (perf-monitor-off.txt)");
            return;
        }
        hud = !std::ifstream(data + "/perf-hud-off.txt").good();
        const std::string path = data + "/logs/perf-monitor.csv";
        // Appended: a relaunch after a crash must not overwrite the seconds before it.
        file = std::fopen(path.c_str(), "a");
        if (!file) {
            std::printf("EDEN_PERF_MONITOR off (cannot open %s)\n", path.c_str());
            return;
        }
        const std::time_t wall = std::time(nullptr);
        char stamp[32]{};
        std::strftime(stamp, sizeof(stamp), "%Y-%m-%d %H:%M:%S", std::localtime(&wall));
        std::fprintf(file, "# session %s\n", stamp);
        std::fputs("t_s,frames,fps,ft_p50_ms,ft_p95_ms,ft_p99_ms,ft_max_ms,hitch_33ms,hitch_50ms,"
                   "core0_pct,core1_pct,core2_pct,core3_pct,host_cpu_pct,gpu_busy_pct,"
                   "draws,draw_ms,draw_pipeline_ms,draw_cache_lock_ms,gpu_dispatch_ms,gpu_queue_wait_ms,"
                   "fence_drains,fence_drain_ms,present_wait_ms,queue_full_ms,"
                   "vk_submits,vk_submit_ms,vk_fence_wait_ms,gfx_pipelines,gfx_pipeline_ms,"
                   "compute_pipelines,compute_pipeline_ms,guest_sync_wait_ms,guest_dequeue_wait_ms,"
                   "jit_blocks,texture_gc_drains,mem_used_mib,mem_total_mib,gfx_mib\n",
                   file);
        std::fflush(file);
        enabled.store(true, std::memory_order_relaxed);
        Hud::perf_shown.store(hud, std::memory_order_relaxed);
        start_ns = Performance::NowNs();
        std::printf("EDEN_PERF_MONITOR on file=%s hud=%d\n", path.c_str(), hud ? 1 : 0);
    }
    ~Monitor() {
        enabled.store(false, std::memory_order_relaxed);
        Hud::perf_shown.store(false, std::memory_order_relaxed);
        RunSummary::Get().Flush();  // 0.69rc: a clean exit writes the summary once more
        if (file) std::fclose(file);
    }
    Monitor(const Monitor&) = delete;
    Monitor& operator=(const Monitor&) = delete;

    // From the runtime-control loop (main.cpp), which wakes every 50 ms: one line a second.
    void Tick() {
        if (!file) return;
        // The profiling session turns these off after its last report; the monitor needs them.
        Performance::timers_on.store(true, std::memory_order_relaxed);
        Performance::vulkan_cost_enabled.store(true, std::memory_order_relaxed);
        const long long now = Performance::NowNs();
        if (last_ns != 0 && now - last_ns < 1'000'000'000LL) return;
        const Counters current = Read();
        if (last_ns != 0) Write(now, current);
        previous = current;
        last_ns = now;
    }

private:
    struct Counters {
        unsigned long long frames, draws, draw_ns, pipeline_ns, lock_ns, dispatch_ns, queue_wait_ns,
            fence_drains, fence_drain_ns, present_wait_ns, queue_full_ns, submits, submit_ns,
            fence_wait_ns, gfx_pipelines, gfx_pipeline_ns, compute_pipelines, compute_pipeline_ns,
            sync_wait_ns, dequeue_wait_ns, jit_blocks, gc_drains;
    };
    static Counters Read() {
        using namespace Performance;
        const auto load = [](const std::atomic<unsigned long long>& value) {
            return value.load(std::memory_order_relaxed);
        };
        Counters c{};
        c.frames = frames.load(std::memory_order_relaxed);
        c.draws = load(rasterizer_draw.calls);
        c.draw_ns = load(rasterizer_draw.nanoseconds);
        c.pipeline_ns = load(draw_pipeline.nanoseconds);
        c.lock_ns = load(draw_lock_wait.nanoseconds);
        c.dispatch_ns = load(gpu_dispatch.nanoseconds);
        c.queue_wait_ns = load(gpu_queue_wait.nanoseconds);
        c.fence_drains = load(gpu_fence_drain.calls);
        c.fence_drain_ns = load(gpu_fence_drain.nanoseconds);
        c.present_wait_ns = load(gpu_present_wait.nanoseconds);
        c.queue_full_ns = load(gpu_queue_full.nanoseconds);
        // vulkan_api: 0 graphics_pipeline, 1 compute_pipeline, 2 submit, 3 fence_wait
        // (performance.h, ReportVulkan's names).
        c.gfx_pipelines = load(vulkan_api[0].calls);
        c.gfx_pipeline_ns = load(vulkan_api[0].nanoseconds);
        c.compute_pipelines = load(vulkan_api[1].calls);
        c.compute_pipeline_ns = load(vulkan_api[1].nanoseconds);
        c.submits = load(vulkan_api[2].calls);
        c.submit_ns = load(vulkan_api[2].nanoseconds);
        c.fence_wait_ns = load(vulkan_api[3].nanoseconds);
        c.sync_wait_ns = load(guest_sync_wait.nanoseconds);
        c.dequeue_wait_ns = load(guest_dequeue_wait.nanoseconds);
        // compilation: A64 blocks the JIT compiled, per emulated core.
        for (unsigned core = 0; core < 4; ++core) c.jit_blocks += load(compilation[core].calls);
        c.gc_drains = load(gc_batched_drain.calls) + load(gc_unbatched_drain.calls);
        return c;
    }
    void Write(long long now, const Counters& c) {
        const Counters& p = previous;
        const double seconds = static_cast<double>(now - last_ns) / 1e9;
        const auto ms = [](unsigned long long a, unsigned long long b) {
            return static_cast<double>(a - b) / 1e6;
        };
        // This second's frame intervals, at most the ring's worth.
        std::vector<float> times;
        const unsigned long long first = std::max(p.frames, c.frames > kRing ? c.frames - kRing : 0ULL);
        for (unsigned long long i = first; i < c.frames; ++i)
            times.push_back(intervals_ms[i % kRing].load(std::memory_order_relaxed));
        std::sort(times.begin(), times.end());
        // Nearest rank, as AnyPS5's run report and its trace summary take it.
        const auto rank = [&](double q) -> double {
            if (times.empty()) return -1;
            const size_t at = static_cast<size_t>(std::ceil(q * static_cast<double>(times.size()))) - 1;
            return times[std::min(at, times.size() - 1)];
        };
        unsigned hitch33 = 0, hitch50 = 0;
        for (const float t : times) {
            hitch33 += t > 33.4f;
            hitch50 += t > 50.0f;
        }
        unsigned cores[4];
        Performance::GuestCoreLoads(cores);
        const auto pct = [](unsigned value) { return value == ~0u ? -1 : static_cast<int>(value); };
        unsigned long long memory_free = 0, memory_total = 0;
        Performance::MemoryPool(&memory_free, &memory_total);
        unsigned long long graphics = 0;
        if (const auto held = Performance::graphics_memory_held.load(std::memory_order_relaxed)) graphics = held();
        const double mib = 1048576.0;
        const unsigned long long frame_count = c.frames - p.frames;
        std::fprintf(file,
                     "%.1f,%llu,%.1f,%.2f,%.2f,%.2f,%.2f,%u,%u,%d,%d,%d,%d,%d,%d,"
                     "%llu,%.2f,%.2f,%.2f,%.2f,%.2f,%llu,%.2f,%.2f,%.2f,"
                     "%llu,%.2f,%.2f,%llu,%.2f,%llu,%.2f,%.2f,%.2f,%llu,%llu,%.0f,%.0f,%.0f\n",
                     static_cast<double>(now - start_ns) / 1e9, frame_count, frame_count / seconds, rank(0.50),
                     rank(0.95), rank(0.99), times.empty() ? -1.0 : times.back(), hitch33, hitch50, pct(cores[0]),
                     pct(cores[1]), pct(cores[2]), pct(cores[3]), pct(Performance::HostCpuPercent()),
                     pct(Performance::GpuBusyPercent()), c.draws - p.draws, ms(c.draw_ns, p.draw_ns),
                     ms(c.pipeline_ns, p.pipeline_ns), ms(c.lock_ns, p.lock_ns), ms(c.dispatch_ns, p.dispatch_ns),
                     ms(c.queue_wait_ns, p.queue_wait_ns), c.fence_drains - p.fence_drains,
                     ms(c.fence_drain_ns, p.fence_drain_ns), ms(c.present_wait_ns, p.present_wait_ns),
                     ms(c.queue_full_ns, p.queue_full_ns), c.submits - p.submits, ms(c.submit_ns, p.submit_ns),
                     ms(c.fence_wait_ns, p.fence_wait_ns), c.gfx_pipelines - p.gfx_pipelines,
                     ms(c.gfx_pipeline_ns, p.gfx_pipeline_ns), c.compute_pipelines - p.compute_pipelines,
                     ms(c.compute_pipeline_ns, p.compute_pipeline_ns), ms(c.sync_wait_ns, p.sync_wait_ns),
                     ms(c.dequeue_wait_ns, p.dequeue_wait_ns), c.jit_blocks - p.jit_blocks,
                     c.gc_drains - p.gc_drains,
                     static_cast<double>(memory_total - std::min(memory_free, memory_total)) / mib,
                     static_cast<double>(memory_total) / mib, static_cast<double>(graphics) / mib);
        std::fflush(file);
        // 0.69rc: the console's own run summary (run_summary.h).
        RunSummary::Get().AddSecond(static_cast<double>(now - start_ns) / 1e9, static_cast<unsigned>(frame_count),
                                    c.draws - p.draws, ms(c.draw_ns, p.draw_ns), pct(Performance::GpuBusyPercent()),
                                    ms(c.submit_ns, p.submit_ns), ms(c.fence_drain_ns, p.fence_drain_ns));
        if (hud) {
            const double p99 = rank(0.99);
            Hud::perf_p99_tenths.store(p99 < 0 ? ~0u : static_cast<uint32_t>(std::lround(p99 * 10.0)),
                                       std::memory_order_relaxed);
            Hud::perf_draws.store(static_cast<uint32_t>(std::min<unsigned long long>(c.draws - p.draws, 999999)),
                                  std::memory_order_relaxed);
            Hud::perf_pipelines.store(static_cast<uint32_t>(std::min<unsigned long long>(
                                          (c.gfx_pipelines - p.gfx_pipelines) +
                                              (c.compute_pipelines - p.compute_pipelines),
                                          9999)),
                                      std::memory_order_relaxed);
        }
    }

    std::FILE* file = nullptr;
    bool hud = false;
    long long start_ns = 0, last_ns = 0;
    Counters previous{};
};
} // namespace Eden::PerfMonitor
