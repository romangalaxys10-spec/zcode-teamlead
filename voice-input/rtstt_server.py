#!/usr/bin/env python3
"""ZCode real-time voice dictation service — 127.0.0.1:8398 only.

WS /stream: client streams raw PCM16 LE 16 kHz mono frames (binary messages).
Server transcribes with faster-whisper (CPU int8) and replies:
  {"type":"partial","text": ...}  rolling 5 s window transcription while speaking
  {"type":"final","text": ...}    full-buffer transcription on FLUSH
A text frame "FLUSH" requests the final transcript and resets the buffer.
GET /health -> {"ok": true, "model": "small"}

Self-contained: faster-whisper only (no PyAudio/torch deps). Fully local.
Concurrency: one shared model; transcription calls serialized by a lock.
"""
import asyncio
import json
import os
import sys
import time

import numpy as np
from faster_whisper import WhisperModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

MODEL = os.environ.get("ZCODE_RTSTT_MODEL", "small")
PORT = int(os.environ.get("ZCODE_RTSTT_PORT", "8398"))

app = FastAPI()
model = None
gen_lock = asyncio.Lock()  # serialize transcription across connections


def get_model():
    global model
    if model is None:
        model = WhisperModel(MODEL, device="cpu", compute_type="int8")
    return model


def to_float(pcm16_bytes):
    return np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32) / 32768.0


def transcribe(audio):
    segments, _ = get_model().transcribe(audio, language=None, vad_filter=True,
                                         beam_size=1, without_timestamps=True)
    return " ".join(s.text.strip() for s in segments).strip()


@app.get("/health")
async def health():
    return {"ok": True, "model": MODEL}


@app.websocket("/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    buf = np.zeros(0, dtype=np.float32)
    last_partial = ""
    last_partial_at = 0.0
    in_flight = False
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                return
            if "bytes" in msg and msg["bytes"]:
                try:
                    buf = np.concatenate([buf, to_float(msg["bytes"])])
                except ValueError:
                    continue
                if len(buf) > 16000 * 60:
                    buf = buf[-16000 * 60:]
                if len(buf) > 16000 * 30:
                    buf = buf[-16000 * 30:]
            elif "text" in msg and msg["text"]:
                cmd = msg["text"].strip()
                if cmd in ("FLUSH", "zc:flush"):
                    async with gen_lock:
                        try:
                            text = await asyncio.to_thread(transcribe, buf) if len(buf) >= 16000 * 0.2 else ""
                        except Exception:
                            text = ""
                    await ws.send_text(json.dumps({"type": "final", "text": text}))
                    buf = np.zeros(0, dtype=np.float32)
                continue
            now = time.time()
            if len(buf) >= 16000 * 1.0 and now - last_partial_at >= 2.0 and not in_flight:
                in_flight = True
                async with gen_lock:
                    if len(buf) >= 16000 * 0.5:
                        window = buf[-16000 * 5:]
                        try:
                            text = await asyncio.to_thread(transcribe, window)
                            if text and text != last_partial:
                                await ws.send_text(json.dumps({"type": "partial", "text": text}))
                                last_partial = text
                        except Exception:
                            pass
                        finally:
                            in_flight = False
                last_partial_at = now
    except (WebSocketDisconnect, RuntimeError):
        pass


if __name__ == "__main__":
    sys.stderr.write(f"[rtstt] loading {MODEL} ...\n")
    get_model()
    sys.stderr.write(f"[rtstt] serving on 127.0.0.1:{PORT}\n")
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning", ws_ping_interval=20, ws_ping_timeout=60)
