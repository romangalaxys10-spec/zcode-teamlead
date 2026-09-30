#!/bin/bash
# start90.sh — bring up the WBeam-protocol tablet second screen (USB-C, no Wi-Fi).
# Host: cap (ScreenCaptureKit@120fps -> VideoToolbox H.264) -> wbeamd-mac (WBTP :5000 + control :5001)
# Tablet: com.wbeam APK (MediaCodec decode) over `adb reverse`.
#
# Tuning env: FPS=120 BITRATE=14000000 MODE=48(quality,renders every frame)/16(ultra)
cd "$(dirname "$0")"

FPS="${FPS:-120}"; BITRATE="${BITRATE:-14000000}"; MODE="${MODE:-48}"
ADB=/Users/d/.local/bin/adb

# stop any previous instance
pkill -f wbeamd-mac.py 2>/dev/null; pkill -f "$PWD/cap" 2>/dev/null; sleep 1

# 1. host daemon (starts cap internally)
WBEAM_FPS=$FPS WBEAM_BITRATE=$BITRATE WBEAM_MODE=$MODE \
  nohup python3 wbeamd-mac.py > wbeamd.log 2>&1 &
sleep 3

# 2. USB tunnel + app
$ADB reverse tcp:5000 tcp:5000 && $ADB reverse tcp:5001 tcp:5001
$ADB shell am force-stop com.wbeam
$ADB shell am start -n com.wbeam/.MainActivity

sleep 3
STATE=$(curl -s "http://127.0.0.1:5001/status" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['state'], d['metrics']['frames'])" 2>/dev/null)
echo "wbeamd: $STATE"
echo "tablet now shows the Mac screen (com.wbeam). fps: adb logcat -d | grep inputFps | tail -3"
