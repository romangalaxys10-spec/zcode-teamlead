# Voice input for ZCode — fully local dictation

Hold **Alt+V** in ZCode (or click the 🎤 pill, bottom-right), talk, release —
the transcript is inserted at the cursor of the chat input. Speech-to-text runs
**fully local** (mlx-whisper on Apple Silicon, no cloud, no keys).

## Components

| File | What it is |
|---|---|
| `stt_server.py` | HTTP STT service on `127.0.0.1:8399` — `POST /transcribe` (wav/webm/mp3 → `{text}`), `GET /health`. ffmpeg-normalizes input, RMS silence gate (no whisper hallucinations on mute), serializes inference (503 when busy), 50 MB cap. |
| `voice-inject.js` | Renderer patch: mic pill + Alt+V hold-to-talk, race-safe MediaRecorder, caret insertion via `execCommand('insertText')` (React-safe) with `setRangeText` fallback, clipboard fallback when no input focused. |
| `voice-bootstrap.js` | Main-process bootstrap (ESM) — injects `voice-inject.js` into `file:`/`app:` pages only. Installed by rewriting `package.json` `"main"`. |
| `com.user.zcode-voice-stt.plist` | LaunchAgent: auto-start + KeepAlive for the STT service. |
| `run_voice_tests.py` | Closed-loop test rig (12 tests): Kokoro/Edge-TTS speaks ground truth → service transcribes → similarity + determinism + adversarial cases (silence, garbage bytes, 70 s audio, concurrency). All green at ship time (en + ru sim=1.00). |

## Install

```bash
# 1. venv + engine
~/.venvs/kokoro311/bin/python3 -m venv ~/.venvs/voice-stt
~/.venvs/voice-stt/bin/pip install mlx-whisper soundfile numpy

# 2. files (adjust $HOME paths inside to match)
mkdir -p ~/.zcode/voice
cp stt_server.py voice-inject.js voice-bootstrap.js ~/.zcode/voice/
cp com.user.zcode-voice-stt.plist ~/Library/LaunchAgents/

# 3. app patch: backup asar, extract, set package.json main -> voice-bootstrap.js
#    (add voice-inject.js + voice-bootstrap.js to the asar root), repack, install.
# 4. start the service
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.zcode-voice-stt.plist
# 5. restart ZCode, grant microphone permission, hold Alt+V and talk
```

## Gotchas (learned the hard way)

- LaunchAgent has **no PATH** — mlx-whisper shells out to `ffmpeg`; set `PATH`
  in the plist or every request 400s.
- `mlx-whisper` pulls numpy but **not** `soundfile` — install it explicitly or
  the silence gate kills every request.
- Whisper hallucinates on silence ("Thank you.") — keep the RMS gate (~2e-4).
- `keyup` during the mic-permission prompt races `getUserMedia` — the inject
  script marks `stopRequested` and cancels instead of recording forever.

## Test

```bash
python3 run_voice_tests.py   # needs the service on :8399 + kokoro venv for fixtures
```
