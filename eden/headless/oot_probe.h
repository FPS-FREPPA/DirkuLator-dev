// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// 0.73rc: a read-only probe of Ocarina of Time (Switch 2, 1.1.1) while it runs. It never writes to the game. It checks the
// memory layout published by PracticeROM/sloperina (docs/FINDINGS.md, GPL-3.0) against this emulator, as the groundwork for a
// fly shortcut: the actor manager at main+0x4E90D90, its tree of live actors, Link's position at actor+0x31C, and the doubles
// of Link's physics record near the actor. It logs `EDEN_OOT_PROBE ...` lines to stderr: once a second for the first minute and
// every five seconds after. Only the game with program id 0400486024DEC000 and main build id E0F3CCFAF50065AE; anything else
// starts nothing.
#include <algorithm>
#include <atomic>
#include <bit>
#include <cctype>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <set>
#include <string>
#include <thread>
#include <vector>

#include "core/arm/debug.h"
#include "core/hle/kernel/k_process.h"
#include "core/memory.h"

namespace Eden::OotProbe {

inline constexpr std::uint64_t kProgramId = 0x0400486024DEC000ULL;
inline constexpr std::uint8_t kBuildId[8] = {0xE0, 0xF3, 0xCC, 0xFA, 0xF5, 0x00, 0x65, 0xAE};
inline constexpr std::uint64_t kActorManager = 0x4E90D90;
inline constexpr std::uint64_t kCamera = 0x4E98068;

class Session {
public:
    ~Session() { Stop(); }
    void Start(std::uint64_t program_id, const std::uint8_t* build, std::size_t build_size, Kernel::KProcess* process) {
        if (program_id != kProgramId || build_size < sizeof(kBuildId) || std::memcmp(build, kBuildId, sizeof(kBuildId)) != 0 ||
            process == nullptr || running_)
            return;
        running_ = true;
        worker_ = std::thread([this, process] { Run(process, process->GetMemory()); });
    }
    void Stop() {
        stop_ = true;
        if (worker_.joinable()) worker_.join();
        running_ = false;
    }

private:
    using u64 = std::uint64_t;
    static bool Valid(Core::Memory::Memory& m, u64 a, std::size_t n = 8) {
        return a >= 0x10000 && a < 0x8000000000ULL && m.IsValidVirtualAddressRange(a, n);
    }
    static bool Read64(Core::Memory::Memory& m, u64 a, u64& out) {
        if (!Valid(m, a)) return false;
        out = m.Read64(a);
        return true;
    }
    static bool ReadFloat(Core::Memory::Memory& m, u64 a, float& out) {
        if (!Valid(m, a, 4)) return false;
        out = std::bit_cast<float>(m.Read32(a));
        return true;
    }
    // The text behind a pointer, if it is a short printable string.
    static std::string Text(Core::Memory::Memory& m, u64 p) {
        std::string s;
        for (int i = 0; i < 40; ++i) {
            if (!Valid(m, p + static_cast<u64>(i), 1)) return {};
            const char c = static_cast<char>(m.Read8(p + static_cast<u64>(i)));
            if (c == 0) return s.size() >= 3 ? s : std::string{};
            if (c < 0x20 || c > 0x7e) return {};
            s += c;
        }
        return {};
    }

    void Run([[maybe_unused]] Kernel::KProcess* process, Core::Memory::Memory& m) {
        int tick = 0;
        u64 main_base = 0;
        int scans = 0;
        std::set<std::string> seen;
        while (!stop_) {
            std::this_thread::sleep_for(std::chrono::milliseconds(tick < 60 ? 1000 : 5000));
            ++tick;
            // The game's main module is found once the loader has mapped it; until then the answer is the start of the code
            // region (0.73rc asked too early and read from there).
            // Where the loader put main (CMakeLists.txt, EDEN_MAIN_BASE): the emulator's own module finder (Core::
            // FindMainModuleEntrypoint) answers with the start of the code region for this game.
            u64 found_main = 0;
            if (const char* text = std::getenv("EDEN_MAIN_BASE")) found_main = std::strtoull(text, nullptr, 16);
            if (found_main == 0) {
                if (tick % 10 == 1) std::fprintf(stderr, "EDEN_OOT_PROBE tick=%d main module not loaded yet\n", tick);
                continue;
            }
            if (found_main != main_base) {
                main_base = found_main;
                std::fprintf(stderr, "EDEN_OOT_PROBE on main=%llx\n", static_cast<unsigned long long>(main_base));
            }
            u64 mgr = 0;
            if (!Read64(m, main_base + kActorManager, mgr) || !Valid(m, mgr)) {
                if (tick % 10 == 1) std::fprintf(stderr, "EDEN_OOT_PROBE tick=%d actor manager not readable\n", tick);
                continue;
            }
            u64 root = 0;
            Read64(m, mgr + 0x38, root);
            if (tick <= 3) {
                std::fprintf(stderr, "EDEN_OOT_PROBE tick=%d manager=%llx words+0x30:", tick, static_cast<unsigned long long>(mgr));
                for (u64 o = 0x30; o <= 0x58; o += 8) {
                    u64 w = 0;
                    Read64(m, mgr + o, w);
                    std::fprintf(stderr, " %llx", static_cast<unsigned long long>(w));
                }
                std::fprintf(stderr, "\n");
            }
            // The tree: left at +0, right at +8 of each node; the actor is the node, or a pointer in its value.
            std::vector<u64> todo{root};
            std::set<u64> visited;
            int actors = 0;
            u64 link = 0;
            while (!todo.empty() && visited.size() < 4096) {
                const u64 node = todo.back();
                todo.pop_back();
                if (!Valid(m, node) || !visited.insert(node).second) continue;
                u64 left = 0, right = 0;
                Read64(m, node, left);
                Read64(m, node + 8, right);
                todo.push_back(left);
                todo.push_back(right);
                u64 candidates[3] = {node, 0, 0};
                Read64(m, node + 0x20, candidates[1]);
                Read64(m, node + 0x28, candidates[2]);
                for (const u64 actor : candidates) {
                    u64 name_pointer = 0;
                    if (!Valid(m, actor) || !Read64(m, actor + 0x20, name_pointer)) continue;
                    const std::string name = Text(m, name_pointer);
                    if (name.empty()) continue;
                    ++actors;
                    std::string lower = name;
                    for (char& c : lower) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
                    const bool is_link = lower.find("player") != std::string::npos || lower.find("link") != std::string::npos;
                    if (is_link && link == 0) link = actor;
                    if (seen.size() < 80 && seen.insert(name).second)
                        std::fprintf(stderr, "EDEN_OOT_PROBE actor name=%s at=%llx node=%llx%s\n", name.c_str(),
                                     static_cast<unsigned long long>(actor), static_cast<unsigned long long>(node),
                                     is_link ? " (Link?)" : "");
                    break;
                }
            }
            float x = 0, y = 0, z = 0;
            const bool have = link != 0 && ReadFloat(m, link + 0x31C, x) && ReadFloat(m, link + 0x320, y) &&
                              ReadFloat(m, link + 0x324, z);
            float vx = 0, vy = 0, vz = 0;
            if (have) {
                ReadFloat(m, link + 0x388, vx);
                ReadFloat(m, link + 0x38C, vy);
                ReadFloat(m, link + 0x390, vz);
            }
            std::fprintf(stderr, "EDEN_OOT_PROBE tick=%d tree_nodes=%zu actors=%d link=%llx pos=%s%.3f,%.3f,%.3f vel=%.3f,%.3f,%.3f\n",
                         tick, visited.size(), actors, static_cast<unsigned long long>(link), have ? "" : "unread:", x, y, z, vx, vy,
                         vz);
            // Once Link is found and standing somewhere real: where do doubles equal to his position sit near the actor?
            if (have && scans < 3 && tick >= 5 && tick % 10 == 5 && std::isfinite(x) && std::isfinite(z)) {
                ++scans;
                Scan(m, link, x, y, z);
            }
        }
    }

    // Three doubles in a row: x, y (+ about 0.585), z within a few tenths of the actor's float position.
    static void Scan(Core::Memory::Memory& m, u64 link, float x, float y, float z) {
        constexpr u64 kSpan = 32ULL << 20;
        const u64 begin = link > kSpan ? (link - kSpan) & ~7ULL : 0x10000;
        const u64 end = link + kSpan;
        int found = 0;
        for (u64 page = begin & ~0xFFFULL; page < end && found < 12; page += 0x1000) {
            if (!Valid(m, page, 0x1000)) continue;
            for (u64 at = std::max(page, begin); at + 24 <= page + 0x1000; at += 8) {
                const double dx = std::bit_cast<double>(m.Read64(at));
                if (!std::isfinite(dx) || std::fabs(dx - x) > 0.25) continue;
                const double dy = std::bit_cast<double>(m.Read64(at + 8));
                const double dz = std::bit_cast<double>(m.Read64(at + 16));
                if (!std::isfinite(dy) || !std::isfinite(dz) || std::fabs(dz - z) > 0.25 || std::fabs(dy - y) > 1.5) continue;
                ++found;
                std::fprintf(stderr, "EDEN_OOT_PROBE physics-candidate at=%llx (actor%+lld) doubles=%.3f,%.3f,%.3f\n",
                             static_cast<unsigned long long>(at), static_cast<long long>(at) - static_cast<long long>(link), dx, dy, dz);
            }
        }
        std::fprintf(stderr, "EDEN_OOT_PROBE physics scan done: %d candidates near actor %llx\n", found,
                     static_cast<unsigned long long>(link));
    }

    std::atomic<bool> stop_{false};
    bool running_ = false;
    std::thread worker_;
};

} // namespace Eden::OotProbe
