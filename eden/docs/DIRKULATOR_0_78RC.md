# DirkuLator 0.78rc

Title PPSA99863, content version 00.005.078, development channel. Built on 0.77rc.

## What 0.78rc changes

- **A new title ID.** The app is now `PPSA99863` (concept ID 99863, content ID `UP9000-PPSA99863_00-EDENNX2PROTO0001`) instead of
  `PPSA99862`. It installs as its own app in `/data/homebrew/PPSA99863`, so the old PPSA99862 tile is a separate app and is
  removed on the console by hand. Saves, settings, shader caches and logs live in `/data/eden-nx2` and are not tied to the
  title ID, so they carry over. The update notice looks the app up on homebrew.page by title ID; the new ID has no listing
  there. Release notes for builds up to 0.77rc keep the ID they were built with.
