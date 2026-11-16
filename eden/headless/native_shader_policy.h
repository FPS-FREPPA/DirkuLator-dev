// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>

namespace Eden::NativeShaderPolicy {
// FSEL operand modifiers are required by captured Pokopia and Ocarina shaders.
// Select per program and invalidate the corresponding shader cache below.
constexpr bool CorrectFloatSelect(std::uint64_t program_id) {
    return program_id == 0x0400A3A01EE4C000ULL || program_id == 0x0400486024DEC000ULL;
}
constexpr unsigned CacheTag(std::uint64_t program_id) {
    if (program_id == 0x040074A01BF12000ULL) return 0x201U;
    return CorrectFloatSelect(program_id) ? 0x100U : 0U;
}
} // namespace Eden::NativeShaderPolicy
