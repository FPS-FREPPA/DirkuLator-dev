# DirkuLator 0.70rc

Native PS5 title PPSA99862, content version 00.005.070, development channel. **Local candidate: not published
until it has been tested on a console.** Built on 0.69rc (the console's own run summary and the PC sampler, neither
yet run on a console as of this build).

## What 0.70rc changes

1. **`TextureHeaderIndex`** (Eden patch `99zzzzzzc-texture-header-index.diff`; the design of Eglantine pull request 900).
   Adds `Tegra::Texture::TextureHeaderIndex` and `UsesHeaderByteOffsetHandles` and uses them where a texture handle
   becomes a header index: the shader-compile read (`GenericEnvironment::ReadTextureInfo`) and the texture cache
   (`VisitImageView`). Some Switch 2 bindless handles (Switch Sports Resort's scenery) hold the header's byte offset
   (index * 32); that reading is switched on only for that title (program id `0x0400000000000849`), only on the
   native-tiling path, and only when the plain index lies past the pool and the offset lands inside it. Ocarina of Time
   has an out-of-range handle (`0xbe000`) that must stay out of range, and does. The shader-compile read no longer
   reads past the end of the header table for an out-of-range index (it was guarded by an assert only): it returns an
   empty header, "no texture", as the runtime path already did. Our core never had the Switch Sports heuristic that
   pull request 900 removes from Eglantine, so this adds the function and the gating without changing what Ocarina of
   Time samples. Compile-time checks in `texture.h`.
2. **Output at 1440p.** The picture the app puts out (Settings > Video > Output resolution) defaults to 1440p
   (`kDefaultOutput`); it was 1080p. The console's `dirkulator.json` was set to 1440p at the user's request. The internal
   rendering scale stays 1x (the game's own 720p handheld output, scaled by the upscaling filter): 2x would be a real
   1440p render but quadruples the render targets, and the game already runs out of memory in about 17 minutes
   (the 0.68rc crash). The launcher still falls back to 1080p if a display refuses the size.
3. **No game autostart.** The one-click start (the app opens straight into the last game, 0.5.14) is off: the launcher
   opens. It happens only while `/data/eden-nx2/autostart.txt` exists; the test scripts create it for a run and remove
   it afterwards. Never after a crash restart, as before.
4. **In-app branding removed.** The Dirk launcher theme and its generated backdrop art are gone (Canopy, the default, and
   Slate remain; a saved `dirk` theme reads as the default), the loading screen's wordmark reads "LOADING" instead of
   "DIRKULATOR" (baked text regenerated), and the on-screen keyboard prompt's title is "Name". The PS5 tile (name,
   icon, background, sound), the config and file names and the credits are unchanged.
5. **Renderer switch in the menu** (already there, checked): Settings > Video > Renderer flips the global renderer between
   Vulkan (recommended) and OpenGL, and each game's own options have a Renderer row with the same two choices. OpenGL is
   Eden's OpenGL backend on the PS5 OpenGL 4.6 SDK 1.0.2 (the SDK the launcher already uses); it has not been run in a
   test run for this project in this session.

