# 0.57rc repeat-route test protocol

Test one verified binary and fixed settings. The target is sustained 30 FPS of
real displayed guest frames at repeatable gameplay checkpoints. Host tests and
successful installation do not establish performance or long-session stability.

1. Verify all package hashes, installed content version 00.005.057 and the exact
   compiled source from VALIDATION.json. Preserve earlier evidence.
2. Before every run close only this title, back up/hash the shader caches, and
   clear RADV, startup-shader and native OpenGL shader caches. Do not delete saves,
   ROMs, firmware, keys, settings, logs or diagnostic dumps.
3. Start photography/log collection before launch. Record PC UTC, the previous
   photo boundary, session identity, cold-cache state and settings.
4. Launch, observe the actual title menu, select New Game and confirm the same
   test slot/start prompt. Never Continue or Load. Require a fresh opening image.
   In the game A is Circle and B is Cross; the launcher confirmation uses Cross.
5. Watch the full opening without skip input. Record tapestry/nightmare, daylight
   Deku Tree, Navi flight, waking Link and first controllable room separately.
6. Establish visual reference landmarks once, then repeat the same route:
   Link's house, ladder base, nearest bridge, Kokiri Shop entrance, bridge,
   ladder and back inside Link's house. No exploration/item/combat detours.
7. Each circuit holds the same room view for 60 seconds, the same bridge view for
   120 seconds (measure the final 60), and the shop entrance for 30 seconds.
   Verify each actual door transition. Continue for at least 30 minutes of
   controllable gameplay and 45 minutes after New Game began, unless it fails.
8. Use tools/bridge/client.py with --host and --evidence-dir. Read status, arm,
   send one short pulse and require its native applied acknowledgment. Read a
   newer completed photo after every input. Physical input overrides the bridge.
   Prefer 150-300 ms buttons, 250-750 ms steering, at most 2500 ms straight movement.
9. Collect boot/stderr/heap/CSV/bridge telemetry every checkpoint/two minutes and
   on a fault. Preserve newest crash report plus stderr/heap/eden_log companions
   before restarting; split game and automatic launcher sessions. Neutralize,
   archive, close, clear shader caches and start New Game on the same route again.
10. Record FPS distribution and samples near 30, p95/p99/max frame time, hitches,
    stalls, shader compilation, draws/submits/waits, total free/largest memory,
    CPU/GPU backing and route duration. Split CSV sessions and loading/cinematics
    from gameplay. Command-buffer busy is not whole-chip utilization; metrics
    can overlap. Long gaps may be excluded from the existing frame-time ring.
11. Track new fragmented CPU backing, allocation refusals, Vulkan OOM/device loss,
    map/ownership failures, crashes, fog washout/rectangles, holes/fans/spikes and
    input/audio faults. Private camera photos do not prove numerical shader errors.
12. Keep accuracy and rendering work intact. Do not change timing, use generated
    frames, hide draws, or request intrusive GPU dumps during timed measurements.
    Report failed/disturbed runs honestly and repeat the same reached route prefix.

The local Luna handoff supplies exact machine-specific lifecycle, cache-backup,
phone, controller, logging and stop/recovery commands. Those private host paths
and diagnostics are not part of this public repository. No warm-cache comparison
is claimed by this protocol because every run starts with cleared shader caches.
