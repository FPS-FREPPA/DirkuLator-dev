# DirkuLator 0.59rc

Native PS5 title PPSA99862, content version 00.005.059.

## Ocarina floating-point select accuracy

Enable the existing FSEL operand-modifier correction for Ocarina of Time
(program 0400486024DEC000). A captured shader, key 1a55fa57a335b963,
contains FSEL R37, R14, -R14, P0 at offset 0x910 and FSEL R39, R20,
-R20, P1 at 0x9f0. NVIDIA nvdisasm 13.5.37, with the explicitly selected
SM86 decoder, independently confirms those instructions. The old Ocarina
policy ignored the negation and selected between identical register values.
The corrected path preserves negation and absolute-value modifiers using
bit operations, including signed zero and NaN payloads. Integer SEL keeps
its original behavior. Shader-cache tags change for Ocarina so previously
compiled incorrect shaders are rebuilt.

The shader inputs remain private. NVIDIA tool archive SHA256:
8cc7edd8219882d46eabbd6a686fdf7487fbb9faab4b79398051699ff88fa137.
Reference: https://docs.nvidia.com/cuda/cuda-binary-utilities/

## Evidence and limits

276 distinct archived native shader streams (320,873 instructions) passed
the existing lowerer under ASan/UBSan. Lowering acceptance does not establish
numerical correctness. The FSEL regression compares exact bits for real
captured instructions, execution and select predicates, negative/positive zero,
finite values, infinities and NaNs. Build/check results and exact source/binary
hashes are recorded in VALIDATION.json after qualification.

The 0.58rc logs contain non-finite position outputs and large projected triangle
spans, with zero out-of-range indices in the two current runs' sampled probes.
These findings do not establish FSEL as the cause of the visible geometry fan;
that requires matching shader/draw evidence and a hardware comparison.

The guest CPU is AArch64 (ARM64); the native PS5 host executable is x86-64.
Guest speed stays at 100%. No CPU/GPU power or FPS improvement is claimed.
The 0.58rc shared-pool OOM remains a separate unresolved issue. Its near-crash
idle staging retention already reached zero, so increasing retention or merely
reducing the cap is not established as a fix. This candidate retains the
existing memory policy pending stronger allocation-lifetime evidence.

Native build/package and bit-exact component checks do not qualify hardware
stability, image correctness or 30 FPS gameplay. Published notes must state
whether those hardware checks have actually been performed.

## Completed qualification

Compiled source: `5f83316b71c78027a78c2c891bb1172fa507f4e1`.
Native compilation/package checks, captured FSEL bit-exact regression under
ASan/UBSan, memory-pressure regression, package isolation, capture-archive tests,
repository hygiene and all 159 dependency-license hashes passed. All 72 installed
files matched full raw read-back. The old app was backed up and removed first.
A fresh PS5 00.005.059 boot loaded the game with status 0 and preserved accuracy
settings at 100% speed. The title was then closed and the three backed-up shader
caches cleared again. Saves and other user data were preserved. Camera stayed
stopped. This is startup qualification; no observed controllable gameplay,
geometry correction, sustained stability or FPS improvement is claimed.
