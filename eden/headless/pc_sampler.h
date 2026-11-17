// SPDX-License-Identifier: GPL-3.0-or-later
// 0.68rc: a release-safe sampler of where the GPU threads spend their CPU time.
//
// The 0.67rc run showed draw recording costing 361 us per draw in slow stretches against 18 us in healthy ones
// while no wrapped wait explained it, so the thread is computing somewhere. The development profile has a
// program-counter sampler (EDEN_DEV_PROFILE, performance.cpp); this is the same mechanism for the release build:
// a sampling thread sends SIGUSR2 to the named threads, the handler stores the interrupted instruction pointer in
// a ring (no allocation, no locking, no logging in the handler), and the sampling thread prints the busiest
// addresses every 10 s:
//
//   EDEN_PC_SAMPLES up_s=<n> target=<GPU|GPUBack> n=<samples> lost=<overwritten> sent=<signals> failed=<kill errors>
//       base=<__eden_text_start> top: <pc relative to base>=<count> ...
//
// The addresses are relative to __eden_text_start so they can be symbolised against the exact ELF
// (tools/pc-sample-report.py). Off unless /data/eden-nx2/pc-sample.txt exists (a signal into a thread can hang a
// boot, so it is a switch and starts late). Optional lines in that file: rate_hz=<20..500> (default 100),
// delay_s=<0..600> (default 45, counted from the first target thread naming itself).
#pragma once

#include <pthread.h>
#include <signal.h>
#include <ucontext.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <thread>
#include <type_traits>
#include <unordered_map>
#include <vector>

// The start of our own code, from the link (src/wait_profile.c uses it the same way); absent in host tests.
extern "C" const char __eden_text_start[] __attribute__((weak));

namespace Eden::PcSampler {

inline constexpr std::size_t kTargets = 2;
inline constexpr std::size_t kRing = 16384;  // 160 s at 100 Hz: far more than one report window
inline constexpr std::array<const char*, kTargets> kNames{"GPU", "GPUBack"};

struct Target {
    std::atomic<std::uintptr_t> thread{0};
    std::array<std::atomic<std::uintptr_t>, kRing> ring{};
    std::atomic<std::uint32_t> head{0};  // written only by the signal handler on that thread
    std::uint32_t tail = 0;              // read only by the sampling thread
    std::uint32_t lost = 0;
};
inline std::array<Target, kTargets> targets;
inline std::atomic<bool> enabled{false};
inline std::atomic<unsigned long long> signals_sent{0}, signals_failed{0};

// pthread_t is a pointer on the console and an integer on Linux. `if constexpr` only discards the branch that does
// not apply inside a template, hence the template parameter.
template <class T = pthread_t>
inline std::uintptr_t ToId(T t) {
    if constexpr (std::is_pointer_v<T>) return reinterpret_cast<std::uintptr_t>(t);
    else return static_cast<std::uintptr_t>(t);
}
template <class T = pthread_t>
inline T FromId(std::uintptr_t id) {
    if constexpr (std::is_pointer_v<T>) return reinterpret_cast<T>(id);
    else return static_cast<T>(id);
}

// The interrupted instruction pointer. On the console it is word 28 of the signal context (the native ABI
// the development sampler was qualified against: the SDK's ucontext field points elsewhere).
inline std::uintptr_t ContextPc(void* context) {
#ifdef PS5_NATIVE
    return static_cast<const std::uintptr_t*>(context)[224 / sizeof(std::uintptr_t)];
#else
    return static_cast<std::uintptr_t>(static_cast<ucontext_t*>(context)->uc_mcontext.gregs[REG_RIP]);
#endif
}

// Async-signal-safe: atomics and array stores only.
inline void Handler(int, siginfo_t*, void* context) {
    const std::uintptr_t self = ToId(pthread_self());
    for (auto& t : targets) {
        if (t.thread.load(std::memory_order_relaxed) != self) continue;
        const std::uint32_t h = t.head.load(std::memory_order_relaxed);
        t.ring[h % kRing].store(ContextPc(context), std::memory_order_relaxed);
        t.head.store(h + 1, std::memory_order_release);
        return;
    }
}

// Called by a thread that has just named itself (performance.cpp RegisterWorker). No-op unless sampling is on.
inline void NoteThread(const char* name) {
    if (!enabled.load(std::memory_order_acquire)) return;
    for (std::size_t i = 0; i < kTargets; ++i) {
        if (std::strcmp(name, kNames[i])) continue;
        sigset_t mask;
        sigemptyset(&mask);
        sigaddset(&mask, SIGUSR2);
        pthread_sigmask(SIG_UNBLOCK, &mask, nullptr);  // the signal must be deliverable to this thread
        targets[i].thread.store(ToId(pthread_self()), std::memory_order_release);
        std::fprintf(stderr, "EDEN_PC_SAMPLER target %s registered\n", name);
        return;
    }
}

// The samples of one target since the last call, oldest first (the sampling thread only).
inline std::vector<std::uintptr_t> Drain(std::size_t index) {
    Target& t = targets[index];
    const std::uint32_t head = t.head.load(std::memory_order_acquire);
    std::uint32_t from = t.tail;
    if (head - from > kRing) {  // more than a ring was produced: the oldest were overwritten
        t.lost += head - from - static_cast<std::uint32_t>(kRing);
        from = head - static_cast<std::uint32_t>(kRing);
    }
    std::vector<std::uintptr_t> out;
    out.reserve(head - from);
    for (std::uint32_t i = from; i != head; ++i) out.push_back(t.ring[i % kRing].load(std::memory_order_relaxed));
    t.tail = head;
    return out;
}

// One report line for a target from a set of samples; empty when there are none.
inline std::string FormatReport(std::size_t index, const std::vector<std::uintptr_t>& pcs, double up_s,
                                unsigned top = 24) {
    if (pcs.empty()) return {};
    std::unordered_map<std::uintptr_t, unsigned> count;
    for (std::uintptr_t pc : pcs) ++count[pc];
    std::vector<std::pair<std::uintptr_t, unsigned>> rows(count.begin(), count.end());
    std::sort(rows.begin(), rows.end(), [](const auto& a, const auto& b) { return a.second > b.second; });
    const std::uintptr_t base = reinterpret_cast<std::uintptr_t>(__eden_text_start);
    char head[256];
    std::snprintf(head, sizeof head,
                  "EDEN_PC_SAMPLES up_s=%.0f target=%s n=%zu lost=%u sent=%llu failed=%llu base=%#llx top:", up_s,
                  kNames[index], pcs.size(), targets[index].lost,
                  signals_sent.load(std::memory_order_relaxed), signals_failed.load(std::memory_order_relaxed),
                  static_cast<unsigned long long>(base));
    std::string line = head;
    for (std::size_t i = 0; i < rows.size() && i < top; ++i) {
        const std::uintptr_t pc = rows[i].first;
        char one[64];
        // Relative to our own code when the address lies above its start (else absolute: a library or JIT block).
        std::snprintf(one, sizeof one, " %s%#llx=%u", base && pc >= base ? "" : "abs:",
                      static_cast<unsigned long long>(base && pc >= base ? pc - base : pc), rows[i].second);
        line += one;
    }
    return line;
}

namespace detail {
struct Settings {
    unsigned rate_hz = 100;
    unsigned delay_s = 45;
};
inline Settings ReadSettings(const std::string& path) {
    Settings s;
    std::ifstream in(path);
    std::string line;
    while (std::getline(in, line)) {
        unsigned v = 0;
        if (std::sscanf(line.c_str(), "rate_hz=%u", &v) == 1) s.rate_hz = std::clamp(v, 20u, 500u);
        else if (std::sscanf(line.c_str(), "delay_s=%u", &v) == 1) s.delay_s = std::min(v, 600u);
    }
    return s;
}

inline void Run(Settings s) {
    using Clock = std::chrono::steady_clock;
    const auto began = Clock::now();
    // Wait for the first target thread, then the delay.
    for (;;) {
        bool any = false;
        for (auto& t : targets) any |= t.thread.load(std::memory_order_acquire) != 0;
        if (any) break;
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    std::this_thread::sleep_for(std::chrono::seconds(s.delay_s));
    std::fprintf(stderr, "EDEN_PC_SAMPLER sampling %u Hz\n", s.rate_hz);
    const auto period = std::chrono::microseconds(1000000 / s.rate_hz);
    auto next = Clock::now();
    auto window = next;
    for (;;) {
        for (auto& t : targets) {
            const std::uintptr_t id = t.thread.load(std::memory_order_acquire);
            if (!id) continue;
            if (pthread_kill(FromId(id), SIGUSR2) == 0) signals_sent.fetch_add(1, std::memory_order_relaxed);
            else signals_failed.fetch_add(1, std::memory_order_relaxed);
        }
        next += period;
        std::this_thread::sleep_until(next);
        const auto now = Clock::now();
        if (now - window >= std::chrono::seconds(10)) {
            window = now;
            const double up = std::chrono::duration<double>(now - began).count();
            for (std::size_t i = 0; i < kTargets; ++i) {
                const std::string line = FormatReport(i, Drain(i), up);
                if (!line.empty()) std::fprintf(stderr, "%s\n", line.c_str());
            }
        }
    }
}
}  // namespace detail

// At startup, before the guest threads exist. Returns whether sampling was switched on.
inline bool Init(const std::string& data_dir, bool start_thread = true) {
    const std::string path = data_dir + "/pc-sample.txt";
    if (!std::ifstream(path).good()) {
        std::fputs("EDEN_PC_SAMPLER off (pc-sample.txt absent)\n", stderr);
        return false;
    }
    struct sigaction previous{};
    if (sigaction(SIGUSR2, nullptr, &previous) || previous.sa_handler != SIG_DFL) {
        std::fputs("EDEN_PC_SAMPLER off (SIGUSR2 is already in use)\n", stderr);
        return false;
    }
    struct sigaction action{};
    action.sa_sigaction = Handler;
    action.sa_flags = SA_SIGINFO | SA_RESTART;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGUSR2, &action, nullptr)) {
        std::fputs("EDEN_PC_SAMPLER off (cannot install the handler)\n", stderr);
        return false;
    }
    const detail::Settings settings = detail::ReadSettings(path);
    enabled.store(true, std::memory_order_release);
    std::fprintf(stderr, "EDEN_PC_SAMPLER on (%u Hz after %u s; targets GPU, GPUBack)\n", settings.rate_hz,
                 settings.delay_s);
    if (start_thread) std::thread(detail::Run, settings).detach();
    return true;
}

}  // namespace Eden::PcSampler
