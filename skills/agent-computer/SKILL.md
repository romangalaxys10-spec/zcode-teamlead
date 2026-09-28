---
name: agent-computer
description: OpenMuse-style agent computer for ZCode workers — persistent per-worker Chrome (for Testing) with CDP automation (navigate/text/title/eval/screenshot), live browser mirroring, container-or-sandboxed terminal, PDF exchange. Universal: macOS + Linux.
---

# Agent Computer — universal edition

Per-worker computer surface, auto-adapting to the host:

| Capability | macOS | Linux |
|---|---|---|
| Browser | Chrome for Testing (playwright cache) or system Chrome, per-worker profile + CDP port | chromium/chrome, same flags |
| Terminal | `sandbox-exec` write-scoped to workspace | Docker container (`alpine:3.20`, workspace mounted at /work) when Docker present; otherwise host shell |
| PDF | cupsfilter / sips / textutil / libreoffice (auto-pick) |

## Commands

| Command | What |
|---|---|
| `browser-open <nick> [url]` | Launch worker's browser (persistent profile, CDP port) |
| `cdp <nick> title` / `text` / `url` / `eval "<js>"` / `shot out.png` / `navigate <url>` | Drive the browser over CDP |
| `mirror <nick> [interval] [port]` | Live screenshot mirroring served at http://127.0.0.1:<port> |
| `browser-takeover <nick>` | Foreground the worker's browser |
| `term-exec <nick> <ws> <cmd...>` | Sandboxed/container terminal (receipted) |
| `pdfdrop <file...>` / `pdflist` | PDF exchange |
| `status` | Capability report |

## Notes

- CDP port per worker: 9300 + hash(nick) % 300. If the endpoint is down or has
  no page targets, `cdp`/`mirror` auto-relaunch the profile browser.
- `term-exec` without Docker on macOS uses `sandbox-exec` (write-scoped);
  without Docker on Linux it runs on the host with a warning.
- `term-exec` is semi-trusted worker isolation, not a security boundary.
- Voice features are currently hidden from the ZCode app (removed from the
  asar; the services and this repo's voice-input/ remain for re-enabling).
