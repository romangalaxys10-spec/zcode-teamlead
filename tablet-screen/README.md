# Tablet as Mac Second Screen (no-admin, all local)

Components (all in this folder):
- stream.py — MJPEG server: screencapture main display -> ffmpeg mjpeg -> HTTP on 127.0.0.1:8383
  - GET /          control page (touch -> back-channel)
  - GET /stream    MJPEG frames (multipart/x-mixed-replace)
  - POST /input    "move:x,y" | "leftclick:x,y" | "rmbclick:x,y" | "scroll:delta" (coords in display points)
- tsinput (built from tsinput.swift) — synthetic mouse/scroll via CGEvent; `dims` prints
  "pointsW pointsH pixelsW pixelsH" for the main display.
- start.sh — restart the stream server + re-tunnel to the tablet.

Per-session activation (USB-C):
  1. /Users/d/.local/bin/adb devices          # tablet (OnePlus OPD2403) must be visible
  2. python3 stream.py &                      # or: ./start.sh
  3. /Users/d/.local/bin/adb reverse tcp:8383 tcp:8383
  4. /Users/d/.local/bin/adb shell am start -a android.intent.action.VIEW -d "http://127.0.0.1:8383/"
     -> open on the tablet browser: Chrome -> menu -> "Cast screen / desktop site" optional.

Back-channel gesture map (on the tablet page):
  tap        = left click
  double-tap = right click
  drag       = move
  two-finger swipe = scroll

Permissions that MUST exist (macOS TCC):
  - Screen Recording: granted to the terminal that runs screencapture (already granted)
  - Accessibility: granted to the terminal/process tree that runs tsinput (synthetic events).
    If clicks don't fire: System Settings -> Privacy & Security -> Accessibility, toggle the
    terminal app. screencapture works already, so this is likely the only gap.

Known blocked piece (needs admin password, not available to the agent):
  BetterDisplay v5.0.6 installed at /Applications/BetterDisplay.app — its virtual-display
  (true extended 2nd monitor) requires the PrivilegedHelper to be installed with admin.
  Until then: this rig mirrors the MAIN display onto the tablet (control of whole Mac),
  which is functionally what a 2nd-screen setup drives.
