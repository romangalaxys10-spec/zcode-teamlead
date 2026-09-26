# Changelog

## 0.1.1 — 2026-09-26
- fix: `team.sh order|status|title` positional-arg bug (id was read from the wrong
  position after `shift`, so every order failed with the usage error)
- `order`/`status` command timeout raised 300s → 900s (lead missions with nested
  worker calls take minutes)

## 0.1.0 — 2026-09-26
- initial release: team.sh toolkit (list/order/status/title), team-lead skill,
  /team command, app-patches/ for Telegram group-chat + Discord bot upgrades
