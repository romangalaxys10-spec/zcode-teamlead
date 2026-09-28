#!/usr/bin/env python3
"""ZCode local voice-input STT service — 127.0.0.1:8399 only.

POST /transcribe  body = raw audio bytes (wav, webm/opus, mp3, m4a...)
  -> {"text": "..."} 200
  -> {"error": "..."} 400/413/503
GET /health -> {"ok": true, "model": "..."}
Fully local: mlx-whisper (Apple silicon MLX). No cloud, no keys.
"""
import io
import json
import subprocess
import tempfile
import threading
import time
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import mlx_whisper

MODEL = os.environ.get("ZCODE_STT_MODEL", "mlx-community/whisper-turbo")
PORT = int(os.environ.get("ZCODE_STT_PORT", "8399"))
FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
MAX_BODY = 50 * 1024 * 1024

_infer_lock = threading.Lock()


def _is_wav(head: bytes) -> bool:
    return head[:4] == b"RIFF" and head[8:12] == b"WAVE"


def _to_wav(data: bytes) -> str:
    """Normalize any audio input to 16 kHz mono wav; returns temp file path."""
    src = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
    src.write(data)
    src.close()
    out = src.name + ".wav"
    try:
        subprocess.run(
            [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", src.name,
             "-ar", "16000", "-ac", "1", out],
            check=True, timeout=120,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
    except Exception:
        os.unlink(src.name)
        raise
    os.unlink(src.name)
    return out


def transcribe(data: bytes) -> str:
    t0 = time.perf_counter()
    if _is_wav(data[:16]):
        wav_path = None
        src = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        src.write(data)
        src.close()
        audio_path = src.name
    else:
        audio_path = wav_path = _to_wav(data)
    try:
        import numpy as np
        import soundfile as sf

        audio, _sr = sf.read(audio_path, dtype="float32")
        if audio.size == 0 or float(np.sqrt(np.mean(audio**2))) < 2e-4:
            sys.stderr.write("[stt] silence gate -> empty\n")
            return ""
        result = mlx_whisper.transcribe(audio_path, path_or_hf_repo=MODEL)
        text = " ".join(str(result.get("text", "")).split())
        sys.stderr.write(f"[stt] ok {len(data)}B -> {len(text)}ch in {time.perf_counter()-t0:.2f}s\n")
        return text
    finally:
        if wav_path:
            os.unlink(wav_path)
        else:
            os.unlink(audio_path)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True, "model": MODEL})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/transcribe":
            self._json(404, {"error": "not found"})
            return
        if not _infer_lock.acquire(blocking=False):
            self._json(503, {"error": "busy — another transcription is running"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                self._json(400, {"error": "empty body"})
                return
            if length > MAX_BODY:
                self._json(413, {"error": f"body too large ({length} > {MAX_BODY})"})
                return
            data = self.rfile.read(length)
            if not data.strip():
                self._json(400, {"error": "empty body"})
                return
            try:
                text = transcribe(data)
            except Exception as e:
                self._json(400, {"error": f"could not decode/transcribe audio: {e}"})
                return
            self._json(200, {"text": text})
        finally:
            _infer_lock.release()

    def log_message(self, fmt, *args):
        sys.stderr.write("[http] " + fmt % args + "\n")


if __name__ == "__main__":
    sys.stderr.write(f"[stt] loading {MODEL} ...\n")
    import numpy as np
    warm = np.zeros(16000, dtype="float32")
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    import wave
    with wave.open(tmp.name, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes((warm * 32767).astype("int16").tobytes())
    mlx_whisper.transcribe(tmp.name, path_or_hf_repo=MODEL)
    os.unlink(tmp.name)
    sys.stderr.write(f"[stt] warm; serving on 127.0.0.1:{PORT}\n")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
