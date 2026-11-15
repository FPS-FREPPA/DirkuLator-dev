// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
#include <cstdlib>

namespace Eden::StartupShader {
// Apply must be transactional: failure leaves the previous affinity intact.
// The scope lives inside a startup-cache task, never a runtime compilation task.
template<class Ops> class AffinityScope {
    Ops& ops;
    std::uint64_t previous{};
    bool changed{};
public:
    explicit AffinityScope(Ops& operations) : ops{operations} {
        const auto target = ops.Allowed();
        if (target && ops.Read(previous) && target != previous)
            changed = ops.Apply(target);
    }
    ~AffinityScope() {
        if (changed && !ops.Apply(previous)) std::abort();
    }
    AffinityScope(const AffinityScope&) = delete;
    AffinityScope& operator=(const AffinityScope&) = delete;
};
}
