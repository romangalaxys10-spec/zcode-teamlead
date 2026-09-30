# Tablet second screen (WBeam WBTP protocol, macOS host)

Android tablet = live Mac second screen over USB-C. Host captures via
ScreenCaptureKit @120Hz, hardware-encodes H.264 (VideoToolbox), serves WBeam's
WBTP/1 wire protocol on :5000 (+ control API :5001) through `adb reverse`;
the open-source WBeam Android app (com.wbeam) hardware-decodes and renders.

## Files
- `cap.swift` / `cap` — SCK -> VideoToolbox H.264 -> CRCD records (stdout). AVCC->Annex-B, SPS/PPS on keyframes, monotonic ts.
- `wbeamd-mac.py` — WBTP multiplexer :5000 + WBeam control API :5001 + /input (tsinput). Per-client pump queues, clock-skew sync to tablet clock (critical!), /stop //start lifecycle.
- `start90.sh` — one-shot bring-up (FPS/BITRATE/MODE env).
- `stream.py` + `tsinput` — legacy MJPEG fallback + touch injection tool.

## Run
    cd tablet-screen && ./start90.sh
Tune: FPS=120 BITRATE=14000000 MODE=48 (48=quality renders every frame; 16=ultra lowest latency but renders only newest).

## Build the tablet APK (one-time)
JDK+SDK live in ~/.local/android/ (Temurin 17 + cmdline-tools + platforms;android-35 + build-tools;35.0.0).
    git clone https://github.com/ppotepa/WBeam && cd WBeam/android
    # optional: raise DECODE_QUEUE_MAX_FRAMES/RENDER_QUEUE_MAX_FRAMES 2->10 and NO_PRESENT ladder in stream/H264TcpPlayer.java
    JAVA_HOME=~/.local/android/jdk-17.0.20.1+1/Contents/Home ./gradlew :app:assembleDebug
    adb install -r app/build/outputs/apk/debug/app-debug.apk

## Measured (OnePlus OPD2403, USB-C)
Host capture 120.4fps; host->tablet 120fps; tablet decode 30-36fps; render 32fps steady, discardFps 0 (quality mode).
Residual cap is WBeam's Android render loop (~30ms/frame drain) — host has 120fps headroom.
Pitfalls (all hit live): AVCC-not-AnnexB, tablet clock skew (+13.6s -> decoder drops to ~12fps),
queue depth 2, ultra-mode render-latest-only. Details in repo CHANGELOG + memory.
