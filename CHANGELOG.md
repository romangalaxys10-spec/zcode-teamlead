# Changelog

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
