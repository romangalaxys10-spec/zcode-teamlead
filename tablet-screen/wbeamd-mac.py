#!/usr/bin/env python3
"""wbeamd-mac — macOS host for the WBeam Android tablet sink.

Pipes encoded H.264 frames from `cap` (ScreenCaptureKit + VideoToolbox) into the
WBeam tablet app over the WBeam WBTP/1 wire protocol, plus the minimal HTTP
control API the app polls, and a /input back-channel to tsinput for touch.

Ports (WBeam build defaults): stream 5000, control 5001. Both reach the tablet
via `adb reverse` over USB-C.

Wire protocol (WBeam WBTP/1, all big-endian):
  Per-connection handshake: 24-byte HELLO v2
    "WBS1" | u8 ver=0x02 | u8 codecFlags | u16 helloLen=24 | u64 sessionId
    | u16 width | u16 height | u16 fps | u16 reserved
  Then one WBTP frame per encoded H.264 access unit: 22-byte header + Annex-B payload
    "WBTP" | u8 ver=1 | u8 flags(0x02=keyframe) | u32 seq | u64 captureTsUs | u32 payloadLen

Feed: `cap` writes 28-byte CRCD records:
    "CRCD" | u32 w | u32 h | u32 key | u64 tsUs | u32 len | <annexB payload>

Tuning env vars: WBEAM_FPS (120) WBEAM_BITRATE (12000000) WBEAM_WIDTH WBEAM_HEIGHT
                 WBEAM_MODE (16=ultra low-latency, 32=stable, 48=quality)
"""
import json, os, queue, socketserver, struct, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.join(HERE, "cap")
TIN = os.path.join(HERE, "tsinput")
STREAM_PORT = 5000
CONTROL_PORT = 5001
FPS = int(os.environ.get("WBEAM_FPS", "120"))
BITRATE = int(os.environ.get("WBEAM_BITRATE", "12000000"))
SW = int(os.environ.get("WBEAM_WIDTH", "1920"))
SH = int(os.environ.get("WBEAM_HEIGHT", "1200"))
MODE_FLAG = int(os.environ.get("WBEAM_MODE", "16"), 10) & 0x30  # 0x10 ultra / 0x20 stable / 0x30 quality
# WBeam app blocks the stream when daemon build_revision != its own WBEAM_BUILD_REV (BuildRevisionGuard)
BUILD_REV = os.environ.get("WBEAM_BUILD_REV", "0.1.2.0e5e8")

FRAMES = [0]
ADB = os.environ.get("ADB", "/Users/d/.local/bin/adb")
CLOCK_OFFSET_US = [0]   # tablet_epoch_us - mac_epoch_us; refreshed periodically

def _clock_worker():
    """Keep CLOCK_OFFSET_US fresh: WBeam paces by (tabletNow - captureTs), so a
    skewed tablet clock makes every frame look ancient and gets dropped."""
    import subprocess as sp
    while True:
        try:
            tab_ms = int(sp.run([ADB, "shell", "date", "+%s%3N"], capture_output=True,
                                text=True, timeout=5).stdout.strip())
            mac_us = time.time_ns() // 1000
            CLOCK_OFFSET_US[0] = tab_ms * 1000 - mac_us
            print(f"clock offset (tablet-mac): {CLOCK_OFFSET_US[0]/1000:.0f} ms", flush=True)
        except Exception as e:
            print(f"clock sync err: {e}", flush=True)
        time.sleep(60)

threading.Thread(target=_clock_worker, daemon=True).start()

# ── control back-channel (coalesced: latest command wins, one tsinput per 50ms) ──
_pending = [None]
_plock = threading.Lock()

def _input_worker():
    while True:
        time.sleep(0.05)
        with _plock:
            cmd = _pending[0]
            _pending[0] = None
        if cmd:
            try:
                subprocess.run([TIN] + cmd, timeout=2)
            except Exception:
                pass

threading.Thread(target=_input_worker, daemon=True).start()

class Feed:
    """Reads CRCD records from cap's stdout, pushes WBTP frames to per-client pump threads."""
    def __init__(self):
        self.state = "idle"
        self.state_ts = time.time()
        self.stop_requested = False
        self._clients = []          # client dicts {sock, q, hello, addr}
        self._cclients_lock = threading.Lock()
        self._last_key = b""       # most recent WBTP keyframe, replayed to new joins

    def run_once(self):
        cap_args = [str(FPS), str(BITRATE), str(SW), str(SH)]
        cap = subprocess.Popen([CAP] + cap_args, stdout=subprocess.PIPE,
                               stderr=open(os.path.join(HERE, "cap.err"), "wb"), bufsize=0)
        self.state = "streaming"; self.state_ts = time.time()
        buf = cap.stdout
        seq = 0
        try:
            while True:
                hdr = self._read_all(buf, 28)
                if hdr is None:
                    break
                if hdr[:4] != b"CRCD":
                    print("feed: bad CRCD magic, restarting cap", flush=True)
                    break
                is_key = struct.unpack(">I", hdr[12:16])[0]
                ts_us, plen = struct.unpack(">QI", hdr[16:28])
                if plen > 16 * 1024 * 1024:   # guard against corrupt length
                    break
                payload = self._read_all(buf, plen)
                if payload is None:
                    break
                seq = (seq + 1) & 0xFFFFFFFF
                flags = 0x02 if is_key else 0
                ts_out = (ts_us + CLOCK_OFFSET_US[0]) & 0xFFFFFFFFFFFFFFFF
                frame = struct.pack(">4sBBIQI", b"WBTP", 1, flags, seq,
                                    ts_out, plen) + payload
                FRAMES[0] += 1
                if is_key:
                    self._last_key = frame
                with self._cclients_lock:
                    clients = list(self._clients)
                for c in clients:
                    q = c["q"]
                    if q.full():
                        # drop oldest frames until room, keeping a keyframe if drained
                        drained_key = None
                        while True:
                            try:
                                drained_key = q.get_nowait()
                            except queue.Empty:
                                break
                            if drained_key[5] & 0x02:      # keep the keyframe
                                break
                        if drained_key is not None and (drained_key[5] & 0x02):
                            q.put_nowait(drained_key)
                        if q.full():
                            continue
                    q.put_nowait(frame)
                if self.stop_requested:
                    break
        finally:
            cap.terminate()
            try:
                cap.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cap.kill()
            self.state = "idle"
            print("feed: cap stopped", flush=True)

    def pump_client(self, c):
        try:
            c["sock"].sendall(c["hello"])
        except OSError:
            self._drop(c); return
        while True:
            try:
                frame = c["q"].get(timeout=1.0)
            except queue.Empty:
                with self._cclients_lock:
                    if c not in self._clients:
                        break
                continue
            try:
                c["sock"].sendall(frame)
            except OSError:
                break
        self._drop(c)

    def _drop(self, c):
        with self._cclients_lock:
            if c in self._clients:
                self._clients.remove(c)
        try:
            c["sock"].close()
        except OSError:
            pass

    @staticmethod
    def _read_all(f, n):
        data = b""
        while len(data) < n:
            chunk = f.read(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def serve_client(self, sock, addr):
        """Handshake (WBS1 HELLO v2), then hand the socket to a per-client pump thread."""
        session_id = time.time_ns() & 0xFFFFFFFFFFFFFFFF
        hello = (b"WBS1" + bytes([0x02, MODE_FLAG]) + struct.pack(">H", 24)
                 + struct.pack(">Q", session_id)
                 + struct.pack(">HHH", SW, SH, FPS) + b"\x00\x00")
        entry = {"sock": sock, "hello": hello, "q": queue.Queue(maxsize=480), "addr": addr}
        with self._cclients_lock:
            self._clients.append(entry)
            key = self._last_key
        if key:
            entry["q"].put_nowait(key)
        print(f"stream client connected: {addr} (total {len(self._clients)})", flush=True)
        threading.Thread(target=self.pump_client, args=(entry,), daemon=True).start()


FEED = Feed()

class ControlHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?", 1)[0]
        if p == "/status":
            self._json({"host_name": "mac-wbeamd", "state": FEED.state, "last_error": "",
                        "run_id": 1, "uptime": int(time.time() - FEED.state_ts),
                        "service": "wbeamd-mac", "build_revision": BUILD_REV,
                        "metrics": {"frames": FRAMES[0]}})
        elif p == "/health":
            self._json({"service": "wbeamd-mac", "build_revision": BUILD_REV, "state": FEED.state})
        elif p in ("/metrics", "/v1/client-metrics", "/client-metrics"):
            self._json({"metrics": {"frames": FRAMES[0]}, "ok": True})
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        p = self.path.split("?", 1)[0]
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n).decode() if n else ""
        except (ValueError, TypeError):
            body = ""
        if p in ("/v1/client-metrics", "/client-metrics", "/apply", "/metrics"):
            self._json({"ok": True})
        elif p == "/start":
            FEED.state = "streaming"; FEED.state_ts = time.time()
            self._json({"state": "streaming", "ok": True})
        elif p == "/stop":
            FEED.stop_requested = True
            FEED.state = "idle"
            self._json({"state": "idle", "ok": True})
        elif p == "/input":
            action, _, coords = body.partition(":")
            cmd = {"leftclick": "click"}.get(action, action)
            if cmd not in ("move", "click", "rmbclick", "down", "up", "scroll"):
                cmd = "move"
            if cmd == "scroll":
                try:
                    d = int(float(coords or 0))
                except ValueError:
                    d = 300
                entry = ["scroll", str(d or 300)]
            else:
                try:
                    x, y = (float(v) for v in coords.split(",")) if "," in coords else (0.0, 0.0)
                except ValueError:
                    x, y = 0.0, 0.0
                entry = [cmd, str(int(x)), str(int(y))]
            with _plock:
                _pending[0] = entry
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404); self.end_headers()


class StreamServer(socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True
    def __init__(self):
        super().__init__(("127.0.0.1", STREAM_PORT), _StreamSocketHandler)
    def process_request(self, sock, addr):
        threading.Thread(target=FEED.serve_client, args=(sock, addr), daemon=True).start()

class _StreamSocketHandler:
    pass


def main():
    print(f"wbeamd-mac: control :{CONTROL_PORT}  stream :{STREAM_PORT}  "
          f"cap {FPS}fps {SW}x{SH} mode={MODE_FLAG:#x}", flush=True)
    threading.Thread(target=lambda: ThreadingHTTPServer(("127.0.0.1", CONTROL_PORT),
                                                         ControlHandler).serve_forever(),
                     daemon=True).start()
    srv = StreamServer()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    while True:
        FEED.run_once()
        if FEED.stop_requested:
            FEED.stop_requested = False
            while FEED.state != "streaming":
                time.sleep(0.5)
            continue
        time.sleep(1)   # auto-restart on cap crash


if __name__ == "__main__":
    main()
