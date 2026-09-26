# Changelog

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
