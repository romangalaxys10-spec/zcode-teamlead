#!/usr/bin/env python3
"""ac_cdp.py — CDP helper for agent-computer.sh (universal: needs only websockets).
cdp <port> navigate <url>   open url in the first tab
cdp <port> text             print visible page text
cdp <port> title            print page title
cdp <port> eval <js>        evaluate JS, print result value
cdp <port> shot <out.png>   capture viewport screenshot
cdp <port> url              print current page url
"""
import base64
import json
import sys
import urllib.request

import websockets
import http.client


def http_json(port, path, method="GET"):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request(method, path)
    r = c.getresponse()
    data = r.read()
    c.close()
    return json.loads(data) if data else {}


def page_ws(port):
    tabs = http_json(port, "/json/list")
    for t in tabs:
        if t.get("type") == "page" and not t.get("url", "").startswith("devtools"):
            return t["webSocketDebuggerUrl"]
    if tabs:
        return tabs[0]["webSocketDebuggerUrl"]
    raise SystemExit("no page targets — open the browser first (browser-open)")


class CDP:
    def __init__(self):
        self.id = 0

    async def connect(self, ws_url):
        import websockets
        self.ws = await websockets.connect(ws_url, max_size=2**24, open_timeout=30)

    async def cmd(self, method, params=None):
        self.id += 1
        await self.ws.send(json.dumps({"id": self.id, "method": method, "params": params or {}}))
        while True:
            d = json.loads(await self.ws.recv())
            if d.get("id") == self.id:
                if "error" in d:
                    raise RuntimeError(f"{method}: {d['error'].get('message', 'protocol error')}")
                return d

    async def eval(self, expr):
        r = await self.cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("result", {}).get("value")


async def main(port, action, arg):
    ws_url = page_ws(port)
    c = CDP()
    await c.connect(ws_url)
    if action == "navigate":
        await c.cmd("Page.navigate", {"url": arg})
        await c.eval("new Promise(r => setTimeout(r, 1500))")
        print("navigated:", arg)
    elif action == "text":
        print(await c.eval("document.body ? document.body.innerText.slice(0, 20000) : ''"))
    elif action == "title":
        print(await c.eval("document.title"))
    elif action == "url":
        print(await c.eval("location.href"))
    elif action == "eval":
        print(await c.eval(arg))
    elif action == "shot":
        r = await c.cmd("Page.captureScreenshot", {"format": "png"})
        open(arg, "wb").write(base64.b64decode(r["result"]["data"]))
        print("saved:", arg)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    port, action = int(sys.argv[1]), sys.argv[2]
    arg = sys.argv[3] if len(sys.argv) > 3 else ""
    asyncio_run = __import__("asyncio").run
    asyncio_run(main(port, action, arg))
