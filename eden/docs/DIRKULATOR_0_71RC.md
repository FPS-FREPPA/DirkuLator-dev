# DirkuLator 0.71rc

Content version 00.005.071, development channel, local candidate (not published until tested). Built on 0.70rc.

## What 0.71rc changes

- **GPU capture from the controller.** Hold the left side of the touchpad and press L2: the next frame's images are written to
  `logs/capture/`, as `capture-now.txt` does. The game does not see the touchpad or L2 during the chord. Only the newest five capture
  folders are kept (a capture is 100-270 MB; the game stalls about 30 s while it is written). The log line
  `EDEN_FRAME_CAPTURE requested from the controller` marks each request. There is no on-screen message yet.
