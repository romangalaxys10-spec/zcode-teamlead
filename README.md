<div align="center">

# 🧭 ZCode TeamLead

**Your ZCode sessions, managed by a ZCode session.**

[![version](https://img.shields.io/badge/version-0.1.1-blue)](CHANGELOG.md)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)](#requirements)
[![battle-tested](https://img.shields.io/badge/battle--tested-✔-success)](#-battle-tested-not-a-demo)

One session becomes the **team lead** — it assigns goals to your other sessions,
polls their progress, redirects drifters, and reports milestones back to you.
You run one session. It runs the team.

`zcode plugins marketplace add romangalaxys10-spec/zcode-teamlead`

</div>

---

## ⚡ What it does

| Command | What happens |
|---|---|
| `team.sh list` | 📋 Roster of every session — id, title, workspace |
| `team.sh status <sessId>` | 🔍 3-line check-in: **Task / Progress / Blockers** |
| `team.sh order <sessId> <msg>` | 🎯 Injects a directive **into** that session — it executes with its full context and replies |
| `team.sh title <sessId>` | 🏷️ Session title lookup |

Under the hood: ZCode's CLI can resume any persisted session and inject a prompt
(`zcode --resume <sessId> -p "..." --json`). This plugin turns that into a
team-lead toolkit **plus** the supervision protocol that makes it actually work.

## 🚀 60-second setup

**1 — install**
```bash
zcode plugins marketplace add romangalaxys10-spec/zcode-teamlead
zcode plugins install team-lead@zcode-teamlead
```
*(or manually: `cp -r skills/team-lead ~/.zcode/skills/`)*

**2 — arm your lead.** Send this to the session that will lead (paste as-is,
fill in your worker session ids from `team.sh list`):

```text
You are TEAM LEAD with a working toolkit: bash <path-to>/team.sh
(subcommands: list | status <sessId> | order <sessId> <message>).

Your workers:
- sess_<worker-1-id> (Dev #1)
- sess_<worker-2-id> (Dev #2)

Standing orders: poll both workers with the status command every ~20 minutes.
Distribute new goals between them with order — one concrete goal per worker,
with a definition of done. Redirect any worker that drifts. Report a one-line
summary to me when a milestone lands or a worker is stuck twice.
```

**3 — watch it manage.** First thing the lead does is poll both workers and
show you their state. Then it delegates. You supervise the supervisor. 😎

💡 Sessions already open won't see the new skill until restarted — the arming
message above contains the absolute toolkit path, so it works on *any* running
session regardless.

## 🏆 Battle-tested (not a demo)

Shipped from a real 3-session team running in parallel on one shared VPS —
**Supervisor TeamLead (TG)** + **Supra-Dev #1** (backend) + **Super-Dev #2**
(frontend). A live status poll through the toolkit:

```text
Task:      Full QA security hardening — 5 bugs fixed, deployed, verified, pushed (8970fd3)
Progress:  100% (all fixes live, cleanup done)
Blockers:  None — optional follow-ups only
```

The lead's protocol (assignment → polling → redirection → escalation) was
forged there, including the golden rules: *worker claims are not facts — verify
on the target before believing "done"*, and *foreground workers get killed by
mid-turn messages — always run them in the background*.

## 🧠 The lead protocol

1. **Assign** — one order per worker: concrete goal + definition of done + deadline
2. **Poll** — `status` on milestones, not constantly
3. **Redirect** — exact correction orders when a worker drifts
4. **Escalate** — one-line summaries to the human when a milestone lands or a worker is stuck twice

There's also a `/team` slash command for quick dispatches, and a full playbook
in [`skills/team-lead/SKILL.md`](skills/team-lead/SKILL.md).

## 📡 Bonus: unlock bot group chats (unofficial app patch)

Born from the same project: **bots that refuse group chats**. The
[`app-patches/`](app-patches/) tool mods the ZCode app bundle so that:

- 🤖 **Telegram bots answer in groups** — and *every group member* can drive
  the group's bot (no per-user binding — your friends can code with it too)
- ⚡ `/new@yourbot` style commands parse correctly (Telegram appends the
  bot name in groups; that used to be an "unknown command")
- 💬 **Discord bots** get rich embeds, native slash commands, ephemeral
  interaction acks, and a token field in the settings UI

```bash
python3 app-patches/patch-zcode-bots.py            # telegram groups
python3 app-patches/patch-zcode-bots.py --discord  # + discord upgrades
python3 app-patches/patch-zcode-bots.py --restore  # roll back anytime
```

Equal-length in-place edits (asar header untouched = macOS-safe), automatic
backup, idempotent, syntax-verified after patching. Byte-exact for macOS ZCode
3.14.3.7762 — aborts safely on other versions. **Unofficial app mod; not
affiliated with the ZCode project.** Details in [`app-patches/README.md`](app-patches/README.md).

## 🩺 Maintenance tools

- `tools/unarchive-task` — accidentally archived a chat/project? `unarchive-task '<name>'`
  flips it back in the desktop tasks-index (see `agents/zcode/2026-09-24` learnings).
- `app-patches/` — supervisor mode (parallel bot tasks), native Discord provider,
  asar verify helpers. See its README for queue-vs-parallel trade-offs.
- `voice-input/` — hold **Alt+V**, talk, transcript lands at the caret. Fully local
  mlx-whisper; install guide + 12-test rig included.

## 💰 Costs & safety (read this once)

- Every `order`/`status` is a **full agent turn** on the target session — its
  entire context is reloaded (100k+ tokens is normal). Poll on milestones.
- Prompts to a busy session **queue** until it finishes.
- Headless orders run with the session's permission mode (CLI default: **yolo**).
  Order sessions you trust; don't `order` sessions you don't own.

## 🧰 Requirements

- ZCode desktop or CLI (macOS/Linux), `node` + `sqlite3` + `python3` on PATH
- Env overrides: `ZCODE_CLI`, `ZCODE_TASKS_DB`, `ZCODE_APP`

## 📜 Changelog

See [CHANGELOG.md](CHANGELOG.md) — v0.1.1 fixed the order-command bug and
raised timeouts for long lead missions.

<div align="center">

**Star it if your sessions now have a boss.** ⭐

</div>
