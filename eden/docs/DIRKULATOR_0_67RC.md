# DirkuLator 0.67rc

Native PS5 title PPSA99862, content version 00.005.067, development channel. **Local candidate: not published
until it has been tested on a console.** Built on 0.66rc (music on); the changes are diagnostics only, the
emulated result is unchanged.

## What 0.67rc changes

1. **Thread names in the wait profile.** `EDEN_WAIT_PROFILE` entries are now `t<N>(<address>,<name>)`. In the
   0.66rc run the RADV driver's queue thread sat idle up to 1.9 s during the stall waves but the other long waits
   could not be attributed because threads were only numbered. The names come from the table the crash report keeps
   (`Eden::Crash::named_threads`, filled by the `SetCurrentThreadName` hook); `eden_thread_name_of` in
   `headless/performance.cpp` looks them up. The system calls are not used: `pthread_setname_np` hangs on this
   platform and the SDK has no stub for `pthread_get_name_np` (the first 0.67rc build failed on it). `-` when a
   thread never named itself. Host check updated.
2. **Audio output pacing probe.** `EDEN_AUDIO_OUT name=... blocks=... max_gap_ms=... late8= late16= late50=
   max_render_ms= max_output_ms=` every 5 s from the thread that feeds the PS5 AudioOut port one 256-frame
   (5.33 ms) block at a time (`headless/audio.cpp`). The render queue never ran dry in 0.66rc (`EDEN_AUDIO_SINK
   padded=0`, `EDEN_AUDIO_VOICE starved=0`) yet the user heard choppy sound, so the break-up must be on the
   output side; this measures it. The timer restarts after a pause so a pause is not counted as a dropout.

3. **Physical pad log for replay.** `logs/input-record.csv` (`t_ms,buttons_hex,lx,ly,rx,ry,l2,r2`, one line per
   change of the player's physical pad, from the launch; `# launch` comment lines; appended across launches;
   `/data/eden-nx2/input-record-off.txt` switches it off). `tools/input-record-to-route.py` turns a launch of it into
   a route for the bridge's route tool, so a run played by hand can be repeated by the input bridge. The bridge's own
   inputs never reach the log. Host check `tools/check-input-record.py`.

## Reference clones reviewed (nothing taken)

`repos/yuzu-mainline` (the original yuzu, last commit June 2025, GPL-2.0-or-later) and `repos/Ryubing` (Ryujinx
fork, C#, MIT) were compared with the Eden audio core we build. yuzu-mainline's `SinkStream::ProcessAudioOutAndRender`
is the same algorithm as Eden's (underrun repeats the last frame), and nearly every audio_core file differs only by
15 months of divergence and licence headers, so there is no fix to port for the choppy audio. No code from either
clone is in this build; any later use needs the evidence first and a licence check (GPL-2.0-or-later and MIT code in a
GPL-3.0-or-later project).

