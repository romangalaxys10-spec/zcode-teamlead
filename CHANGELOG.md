# Changelog

## 0.5.0 — 2026-09-28
- `feed` — live event tap: real-time per-worker milestones from the host jsonl stream
- `perms [--push]` — permission-prompt surfacing (detect + relay; workers never stall silently)
- `burn [--days D]` — token/cost telemetry per session from turn_usage (TEAM_BUDGET_TOKENS ceiling)
- `plan <goals.json>` + `tick` + `done` — goal-DAG scheduler: dependency-ordered task distribution, failed orders stay pending
- `handoff <id|nick>` — context handoff pack (title/ws/turn stats/milestones) for cheap session respawn
- `qa <id|nick>` — adversarial QA lane: fresh read-only reviewer attacks the recent changes (BLOCKER/MAJOR/MINOR or PASS)
- `register <nick> k=v...` — worker capability registry (caps/models/lanes)
- `dispatch [cap:tags] <task>` — load-balanced task routing to the idlest capable worker
- `gate <ws> <stage> pass|fail|status` + `rollback <ws> <tag> [--force]` — lifecycle gates with dry-run-first rollback
- `patches status|reapply` — patch fleet drift detection + guarded re-apply (tools/reapply-patches.sh)
- `tests/run_tests.sh` — 14 headless tests covering every addition (all green)

## 0.4.0 — 2026-09-28
- supervisor v13 (queue mid-task messages: ACK + 20s retry, 30 min cap, delivered notice) and v14 (draft-path stale model falls back to host-preferred instead of the Chinese resolution error) — full mitigation of parallel-task failures
- supervisor v12 (`patch_supervisor_v12.py`) — stale session model no longer dead-ends locked sessions: when a selected session's saved model selection can't resolve, the resume path falls back to the group's default model instead of throwing (saved selection stays preserved)
- `skills/fable/` — the fable plugin (experience-research + boost layer) is now auto-synced into this repo every 2 min alongside the app patches (running cache version, `__pycache__` excluded)
- supervisor v9 (`patch_supervisor_v9.py`) — CRITICAL fix: removed the v3 numeric page-jump intercept — Telegram task buttons decode to `/task <optionIndex>`, which the intercept hijacked as page jumps, re-rendering the picker on every tap. `/task <n>` is native select-Nth again; pagination advances only via the `Next page` option (`__next__` token)
- supervisor v8 (`patch_supervisor_v8.py`) — group callback queries (inline-button taps) now carry the group chat id as actor identity, matching message actors — fixes /task selection buttons re-rendering the picker instead of confirming (pending-selection key mismatch)
- supervisor v7 (`patch_supervisor_v7.py`) — `/task` FOCUS LOCK: selecting a session stamps the context (`_lock:1`) so the busy-spawn skips locked groups and messages submit INTO the selected session (running or not); `/new` clears the lock
- supervisor v6 (`patch_supervisor_v6.py`) — PER-GROUP ISOLATION: bot context (project/session/mode) gets a scoped state key per group chat (`botId::g:<chatId>`), so `/project`/`/task`/`/new`/`/stop` in one Telegram group never affect another group or private chats. Private chats keep the original unscoped key; telegram offset stays bot-level (single poller)
- supervisor v5 (`patch_supervisor_v5.py`) — working heartbeat: the native typing indicator now starts at task SUBMIT (it previously only started after permission/elicitation resolution), so Telegram/Discord show continuous activity during long tool runs instead of silence
- supervisor v4 (`patch_supervisor_v4.py`) — `/queue` command (running-task list with focused marker, registered in the Telegram menu), spawn notices now name the new task (sanitized slug); note: approve/deny permission buttons for bot-driven tasks are native since 3.14 (see app-patches/README.md)
- supervisor v3 (`patch_supervisor_v3.py`) — `/task` picker pagination: 10 per page with a `Next page` option, `/task 2` page jumps; `patch-watch.sh` + LaunchAgent `com.user.zcode-patch-watch` — auto re-applies the whole patch fleet within 5 min of a ZCode app update
- supervisor v2 (`patch_supervisor_v2.py`) — `/task` unfenced: the session/task picker no longer refuses while busy (that guard survived the original supervisor patch), and `/task` is now registered in the Telegram command menu
- `app-patches/patch-groups.py` — re-enable Telegram group chats (lost in the 3.14.3 update): replies route to the group, members authorized by botId, @BotName command suffix stripped
- `app-patches/patch-supervisor.py` — supervisor mode: bots accept unlimited parallel tasks (busy messages spawn a fresh session instead of the "task still running" refusal), /tasks focus-switching while running, /new while busy, per-task streaming updates
- `app-patches/patch-discord-native.py` — first-class Discord bot provider: fills the app's reserved `discord:null` registry slot with a REST v10 adapter + Gateway WebSocket runtime (DMs always, guilds on @mention)
- `app-patches/asar_{unpacked_list,spotcheck}.py` — asar verification helpers (unpacked-set listing, sha256 spot-checks)
- `voice-input/` — fully local voice dictation for the ZCode chat input (mlx-whisper service :8399 + Alt+V hold-to-talk renderer injection + LaunchAgent + 12-test closed-loop rig)
- `tools/unarchive-task` — one-liner fix for accidentally archived chats (flips `archived` in the desktop tasks-index SQLite)
- README: patches guide table comparing queue-vs-parallel mechanisms

## 0.3.0 — 2026-09-26
- `hire --plan` — spawn READ-ONLY workers (plan mode): QA/review lanes that run in parallel with writers
- `broadcast` — one order to every rostered worker
- `tell <from> <to>` — lead-relayed worker-to-worker messaging
- `proof <dev>` — objective workspace facts (git log, dirty files, commit age) to verify worker claims
- `standup` — all-status + workspace git summary in one report
- `notify` — deliver reports to a webhook (TEAM_WEBHOOK); everything logged
- `watch` — live all-status dashboard loop
- `deploy-lock` — serialize deploy windows; orders mentioning deploy/build/restart are refused while another worker holds the lock
- `autopoll on [min]|off|run` — cron-driven self-waking supervision (all-status + optional webhook notify)
- `ROADMAP.md` — staffing doctrine: project lifecycle, how many devs per project size, lanes/skills/bans per role, task-packet order format, anti-patterns

## 0.2.0 — 2026-09-26
- `hire <nick> <wsDir> [mission]` — the lead can CREATE new sessions with a role
  and nickname; rostered and addressable by name forever
- `nudge <id|nick>` — force a stopped/idle dev to continue its last task
- `all-status` — one-shot progress report across every rostered worker
- nicknames: `order`/`status`/`nudge` accept roster nicknames (`dev1`) as well as session ids
- lead protocol: progress requests mid-task are answered IMMEDIATELY via all-status
- roster persisted at `~/.zcode/team-roster.json`

## unreleased — 2026-09-26 (app-patches)
- patch 8: mid-task messages no longer bounce with "task still running" — the bot
  ACKs ("📥 Queued…"), auto-retries every 60s (up to 30×), and when the running
  task finishes your message is processed and folded into a full report

## 0.1.1 — 2026-09-26
- fix: `team.sh order|status|title` positional-arg bug (id was read from the wrong
  position after `shift`, so every order failed with the usage error)
- `order`/`status` command timeout raised 300s → 900s (lead missions with nested
  worker calls take minutes)

## 0.1.0 — 2026-09-26
- initial release: team.sh toolkit (list/order/status/title), team-lead skill,
  /team command, app-patches/ for Telegram group-chat + Discord bot upgrades
