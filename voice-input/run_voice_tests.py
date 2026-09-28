#!/usr/bin/env python3
"""T2/T5 closed-loop verification for the ZCode voice STT service.
Synthesizes fixtures with Kokoro TTS, POSTs them to 127.0.0.1:8399, checks
transcripts + adversarial cases. Numeric only (no vision)."""
import difflib
import json
import os
import struct
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import wave

FIX = "/Users/d/.zcode/workspace/default/.smart/13cf2560/audio-fixtures"
KOKORO = "/Users/d/.venvs/kokoro311/bin/python3"
URL = "http://127.0.0.1:8399/transcribe"
os.makedirs(FIX, exist_ok=True)

SENTENCES = [
    ("en1", "The quick brown fox jumps over the lazy dog while the compiler rebuilds the module cache.", "a"),
    ("en2", "Voice dictation makes coding faster when your hands are tired from typing all day.", "a"),
    ("ru1", "Голосовой ввод работает локально, без облака и без ключей.", "ru"),
]

log = []


def check(test, ok, evidence):
    log.append(f"[T2/T5] {test} {'PASS' if ok else 'FAIL'} {evidence}")
    print(("PASS " if ok else "FAIL ") + test + " — " + evidence)


def synth(name, text, lang):
    out = os.path.join(FIX, name + ".wav")
    if lang != "a":  # Kokoro has no non-EN voices — use Edge-TTS for those
        mp3 = os.path.join(FIX, name + ".mp3")
        subprocess.run(["/Users/d/.venvs/kokoro311/bin/edge-tts", "--voice", "ru-RU-DmitryNeural",
                        "--text", text, "--write-media", mp3], check=True, capture_output=True, timeout=120)
        subprocess.run(["/Users/d/.local/bin/ffmpeg", "-y", "-loglevel", "error", "-i", mp3,
                        "-ar", "24000", "-ac", "1", out], check=True)
        return out
    script = (
        "import json,numpy as np,soundfile as sf\n"
        "from kokoro import KPipeline\n"
        "job=json.loads('''" + json.dumps({'text': text, 'out': out, 'lang': lang}) + "''')\n"
        "pipe=KPipeline(lang_code=job['lang'])\n"
        "a=np.concatenate([x for _,_,x in pipe(job['text'], voice='am_michael', speed=0.9)])\n"
        "sf.write(job['out'], a, 24000)\n"
    )
    subprocess.run([KOKORO, "-c", script], check=True, capture_output=True, timeout=300)
    return out


def post(path_or_bytes):
    try:
        if isinstance(path_or_bytes, bytes):
            data = path_or_bytes
        else:
            data = open(path_or_bytes, "rb").read()
        req = urllib.request.Request(URL, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def sim(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def resample16k(path):
    out = path + ".16k.wav"
    subprocess.run(["/Users/d/.local/bin/ffmpeg", "-y", "-loglevel", "error", "-i", path,
                    "-ar", "16000", "-ac", "1", out], check=True)
    return out


def main():
    # health
    with urllib.request.urlopen("http://127.0.0.1:8399/health", timeout=10) as r:
        check("E0 health", r.status == 200, r.read().decode()[:80])

    # E5 multilingual + P2 similarity/determinism
    for name, text, lang in SENTENCES:
        wav = synth(name, text, lang)
        wav16 = resample16k(wav)
        s1, d1 = post(wav16)
        got1 = d1.get("text", "")
        check(f"P2 {name} sim>=0.8", s1 == 200 and sim(got1, text) >= 0.8,
              f"sim={sim(got1, text):.2f} got={got1[:60]!r}")
        s2, d2 = post(wav16)
        check(f"P2 {name} deterministic", d2.get("text", "") == got1, "second call identical")

    # E1 empty body
    s, d = post(b"")
    check("E1 empty body -> 400", s == 400, f"status={s}")

    # E3 non-audio bytes
    s, d = post(b"\x00\x01\x02this is not audio" * 100)
    check("E3 non-audio -> 400", s == 400, f"status={s} err={str(d.get('error'))[:60]}")

    # E2 digital silence
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000 * 3)  # 3s silence
    s, d = post(tmp.name)
    check("E2 silence -> 200 empty-ish", s == 200 and len(d.get("text", "").strip()) < 10,
          f"status={s} text={d.get('text','')!r}")

    # E4 long audio: repeat sentence ~60s via ffmpeg concat of en1 fixture
    wav = os.path.join(FIX, "en1.wav")
    long_path = os.path.join(FIX, "long60.wav")
    subprocess.run(["/Users/d/.local/bin/ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "9",
                    "-i", wav, "-ar", "16000", "-ac", "1", long_path], check=True)
    s, d = post(long_path)
    dur_probe = subprocess.run(["/Users/d/.local/bin/ffprobe", "-v", "quiet", "-show_entries",
                                "format=duration", "-of", "csv=p=0", long_path],
                               capture_output=True, text=True).stdout.strip()
    check("E4 long audio ok", s == 200 and len(d.get("text", "")) > 50,
          f"dur={dur_probe}s status={s} len={len(d.get('text',''))}")

    # E8 concurrency: two parallel posts, both must complete without server crash
    results = []

    def worker():
        results.append(post(wav))

    ts = [threading.Thread(target=worker) for _ in range(2)]
    ts[0].start(); ts[0].join(0.2); ts[1].start()
    ts[0].join(600); ts[1].join(600)
    codes = sorted(r[0] for r in results)
    check("E8 concurrent", len(results) == 2 and all(c in (200, 503) for c in codes), f"results={len(results)} codes={codes}")

    with open("/Users/d/.zcode/workspace/default/.smart/13cf2560/verify.log", "a") as f:
        f.write("\n".join(log) + "\n")
    fails = sum(1 for l in log if " FAIL " in l)
    print(f"DONE fails={fails}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
