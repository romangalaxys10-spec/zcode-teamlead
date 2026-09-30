#!/usr/bin/env python3
"""No-admin second-screen streamer (low-latency build).

Capture: `screencapture -t jpg` writes native JPEG via CoreGraphics (no ffmpeg
round-trip per frame; ~50ms/frame on this display).
Stream:  MJPEG multipart over HTTP on 127.0.0.1:8383.
Input:   POST /input synthesizes mouse/scroll on the Mac via tsinput (CGEvent),
         coalesced to at most one event per 50ms so touch bursts don't spawn
         a process storm.
Reach:   adb reverse tcp:8383 -> tablet browser.
"""
import http.server, socketserver, subprocess, threading, os, sys, re, time
from urllib.parse import parse_qs
from collections import deque

PORT = 8383
TIN = "/Users/d/.zcode/tablet-screen/tsinput"
CAP_Q = 80            # JPEG quality (1-100); lower = smaller frames = more headroom
DEFAULT_FPS = 24       # target stream rate; capped automatically by capture speed
MIN_INTERVAL = 0.016  # never faster than 60 fps

_dims_cache = [0.0, (2048.0, 1330.0)]

def dims():
    """(pixels_w, pixels_h) of the main display; cached after first call."""
    now = time.time()
    if now - _dims_cache[0] > 30:
        try:
            out = subprocess.run([TIN, "dims"], capture_output=True, timeout=5, text=True).stdout.split()
            _dims_cache[0] = now
            _dims_cache[1] = (float(out[2]), float(out[3]))
        except Exception:
            pass
    return _dims_cache[1]

def grab_jpeg():
    """One screencapture frame -> native JPEG bytes. Returns (bytes, seconds_taken)."""
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".jpg", dir="/tmp")
    os.close(fd)
    t0 = time.time()
    try:
        rc = subprocess.run(["screencapture", "-x", "-o", "-t", "jpg", path],
                            capture_output=True, timeout=5).returncode
        data = open(path, "rb").read() if rc == 0 and os.path.exists(path) else b""
    except Exception:
        data = b""
    finally:
        try: os.unlink(path)
        except OSError: pass
    return data, time.time() - t0

# ---- input coalescing: one tsinput call per tick, newest command wins ----
_pending = [None]
_pending_lock = threading.Lock()
_INPUT_TICK = 0.05  # 50ms

def _input_worker():
    while True:
        time.sleep(_INPUT_TICK)
        with _pending_lock:
            cmd = _pending[0]
            _pending[0] = None
        if cmd:
            try:
                subprocess.run([TIN] + cmd, timeout=2)
            except Exception:
                pass

threading.Thread(target=_input_worker, daemon=True).start()

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.path.startswith("/stream"):
            q = parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
            try:
                fps = max(2, min(60, float((q.get("fps") or [DEFAULT_FPS])[0])))
            except ValueError:
                fps = DEFAULT_FPS
            interval = max(MIN_INTERVAL, 1.0 / fps)
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            boundary = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
            consec_fail = 0
            try:
                while True:
                    data, taken = grab_jpeg()
                    if data:
                        consec_fail = 0
                        self.wfile.write(boundary + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n")
                        self.wfile.flush()
                    else:
                        consec_fail += 1
                        if consec_fail > 30:
                            break
                    sleep_for = interval - taken
                    if sleep_for > 0:
                        time.sleep(sleep_for)  # pacer: don't saturate CPU capturing faster than needed
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception as e:
                print("stream stop:", e)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            pw, ph = dims()
            html = BYTES_HTML.replace(b"__PW__", str(int(pw)).encode()).replace(b"__PH__", str(int(ph)).encode())
            self.wfile.write(html)

    def do_POST(self):
        try:
            ln = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(ln).decode()
        except (ValueError, TypeError):
            self.send_response(400); self.end_headers(); return
        if self.path.startswith("/input"):
            action, _, coords = body.partition(":")
            cmd = {"leftclick": "click"}.get(action, action)
            cmd = cmd if cmd in ("move", "click", "rmbclick", "down", "up", "scroll") else "move"
            try:
                if cmd == "scroll":
                    try: delta = int(float(coords or 0))
                    except ValueError: delta = 300
                    if not delta: delta = 300
                    entry = ["scroll", str(delta)]
                else:
                    x, y = [float(v) for v in coords.split(",")] if "," in coords else (0.0, 0.0)
                    entry = [cmd, str(int(x)), str(int(y))]
            except ValueError:
                self.send_response(400); self.end_headers(); return
            with _pending_lock:
                _pending[0] = entry
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

BYTES_HTML = b"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,user-scalable=no">
<title>Mac Screen</title>
<style>
*{margin:0;padding:0}html,body{width:100%;height:100%;background:#000;overflow:hidden;touch-action:none}
img{width:100%;height:100%;object-fit:contain;display:block}
#fps{position:fixed;top:6px;right:8px;z-index:9;background:#000a;color:#8f8;font:12px monospace;padding:2px 6px;border-radius:6px}
</style></head><body><span id=fps></span><img id=s src="/stream?fps=24">
<script>
// touch back-channel: map touch to display points via the drawn image box.
const s=document.getElementById('s'), fpsEl=document.getElementById('fps');
const urlFps=n=>{s.src='/stream?fps='+n;};
function zoom(z){urlFps(z)}
let _lastTap=0,_lastPing=0;
function pt(e){
  const r=s.getBoundingClientRect();
  const imW=__PW__, imH=__PH__;
  const ar=r.width/r.height, imAr=imW/imH, boxW=r.height*imAr, boxH=r.width/imAr;
  let ox=r.left,oy=r.top; if(r.width>boxW)ox+=(r.width-boxW)/2; else if(r.height>boxH)oy+=(r.height-boxH)/2;
  const t=e.touches[0]||e.changedTouches[0];
  if(!t)return[0,0];
  const x=Math.min(Math.max((t.clientX-ox)/boxW*imW,0),imW), y=Math.min(Math.max((t.clientY-oy)/boxH*imH,0),imH);
  return [Math.round(x),Math.round(y)];
}
document.body.addEventListener('touchstart',e=>{e.preventDefault();
  const now=Date.now();
  if(e.touches.length===1&&now-_lastTap<300){post('rmbclick:'+pt(e)[0]+','+pt(e)[1]);_lastTap=0;}
  else if(e.touches.length===2){
    _swipe={y:(e.touches[0].clientY+e.touches[1].clientY)/2};
  }
  else{_lastTap=now;const[x,y]=pt(e);post('move:'+x+','+y)}
},{passive:false});
document.body.addEventListener('touchmove',e=>{e.preventDefault();
  if(e.touches.length===2&&_swipe){
    const y=(e.touches[0].clientY+e.touches[1].clientY)/2;
    const r=s.getBoundingClientRect();
    if(Math.abs(y-_swipe.y)>8){post('scroll:'+Math.round((y-_swipe.y)/r.height*600));_swipe.y=y;}
  } else {const[x,y]=pt(e);post('move:'+x+','+y)}
},{passive:false});
document.body.addEventListener('touchend',e=>{e.preventDefault();
  if(e.touches.length===0){const[x,y]=pt(e);post('leftclick:'+x+','+y);_swipe=null}
},{passive:false});
function post(b){if(Date.now()-_lastPing>45)return;_lastPing=Date.now();
  fetch('/input',{method:'POST',body:b,headers:{'Content-Type':'text/plain'}}).catch(()=>{})}
s.onload=()=>{fpsEl.textContent='24fps';};
// double-tap-and-hold in top-right = cycle fps 12/24/60 (approximate; use ?fps= for manual)
</script></body></html>"""

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"low-latency stream on http://127.0.0.1:{PORT}/  (stream: /stream?fps=24)")
    srv.serve_forever()
