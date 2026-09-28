---
name: agent-computer
description: OpenMuse-style agent computer for ZCode workers — persistent per-worker Chrome profiles with takeover, a sandboxed worker terminal (macOS), and a PDF drop/exchange zone. Use for "give each worker its own browser", "run this isolated", "convert to PDF for the agents".
---

# Agent Computer — per-worker browser, terminal, PDF exchange

Every team worker gets its own isolated computer surface: a persistent Chrome
profile (cookies/sessions survive restarts), a write-sandboxed shell scoped to
its workspace, and a PDF exchange for moving documents in.

All commands go through `skills/agent-computer/agent-computer.sh`:

| Command | What it does |
|---|---|
| `browser-open <nick> [url]` | Launch the worker's persistent Chrome profile |
| `browser-takeover <nick>` | Same, foregrounded — you take the wheel |
| `browser-list` | List worker profiles |
| `term-exec <nick> <ws> <cmd...>` | Run a command write-sandboxed to the worker's workspace |
| `pdfdrop <file...>` | Convert (txt/md/html/rtf/doc/docx/img/pdf) into the exchange zone |
| `pdflist [n]` | List exchanged PDFs |
| `status` | Capability check |

## Team-lead integration

- lead + workers coordinate through the exchange: producer runs `pdfdrop`,
  consumer reads `~/.zcode/team-lead/ac/exchange/`.
- every `term-exec`/`browser-open` is written to the receipts audit log.
- pair with `team.sh takeover <nick>` to open the worker's *workspace* in the
  ZCode desktop app while `browser-takeover` grabs its *browser*.

## Honest limits (macOS edition)

- `term-exec` uses `sandbox-exec` write-restriction scoped to the workspace +
  profile dir. File reads and network are allowed BY DESIGN (workers need
  npm/curl). It is process isolation for semi-trusted team members, not a
  security boundary — keep groups/profiles to trusted workers.
- No Linux container in this edition (no Docker on the host). Commands run on
  macOS.
