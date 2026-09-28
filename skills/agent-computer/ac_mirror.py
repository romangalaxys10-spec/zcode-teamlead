#!/usr/bin/env python3
"""ac_mirror.py — live browser mirroring for agent-computer.
Polls CDP screenshots, saves shot.png, serves a self-refreshing viewer.
Usage: ac_mirror.py <cdp_port> <interval_sec> <outdir> <serve_port>"""
import asyncio
import base64
import http.server
import json
import os
import socketserver
import sys
import urllib.request

OUT = sys.argv[3] if len(sys.argv) > 3 else "."
SERVE_PORT = int(sys.argv[4]) if len(sys.argv) > 4 else 8766
HTML = """<!doctype html><meta charset=utf-8><title>worker mirror</title>
<style>body{background:#111;color:#eee;font:13px monospace;margin:0;padding:8px}
img{max-width:100%;border:1px solid #333;border-radius:6px}</style>
<h3>worker live mirror</h3><img src="shot.png?t=0">
<script>setInterval(()=>{document.images[0].src="shot.png?t="+Date.now()},%d)</script>"""


async def capture_once(port, out_png):
    ws_url = None
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5).read())
    for t in tabs:
        if t.get("type") == "page" and not t.get("url", "").startswith("devtools"):
            ws_url = t["webSocketDebuggerUrl"]; break
    if not ws_url and tabs:
        ws_url = tabs[0]["webSocketDebuggerUrl"]
    if not ws_url:
        return "no page target"
    import websockets
    async with websockets.connect(ws_url, max_size=2**24, open_timeout=15, ping_timeout=60) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.captureScreenshot", "params": {"format": "png"}}))
        while True:
            d = json.loads(await ws.recv())
            if d.get("id") == 1:
                if "error" in d:
                    return d["error"].get("message", "cdp error")
                open(out_png, "wb").write(base64.b64decode(d["result"]["data"]))
                return None


def serve(outdir):
    os.chdir(outdir)
    page = HTML % 1000
    open("index.html", "w").write(page)

    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

    with socketserver.TCPServer(("127.0.0.1", SERVE_PORT), H) as httpd:
        httpd.serve_forever()


async def loop(port, interval, outdir):
    png = os.path.join(outdir, "shot.png")
    while True:
        try:
            err = await asyncio.wait_for(capture_once(port, png), timeout=interval * 4 + 20)
            if err:
                print(err, flush=True)
        except Exception as e:
            print("capture:", e, flush=True)
        await asyncio.sleep(interval)


if __name__ == "__main__":
    port = int(sys.argv[1]); interval = float(sys.argv[2])
    if len(sys.argv) > 4:
        import threading
        threading.Thread(target=serve, args=(sys.argv[3],), daemon=True).start()
    asyncio.run(loop(port, interval, OUT))
