# Skill: team-lead
Operate and supervise other ZCode sessions from this session. Toolkit: `./team.sh` (relative to this skill's directory; run as `bash ./team.sh ...`).

## Commands
- `bash ./team.sh list` — discover sessions (id | title | workspace).
- `bash ./team.sh status <sessId>` — 3-line check-in (Task / Progress / Blockers).
- `bash ./team.sh order <sessId> <message>` — inject a directive; the reply is the worker's response.
- `bash ./team.sh title <sessId>` — lookup a session's title.

## Lead protocol
1. **Assign**: one `order` per worker with a concrete goal, definition of done, and deadline. Workers act in their own permission context (headless runs default to yolo).
2. **Poll**: `status` on each worker before deciding. Don't micro-manage — poll on milestones or every ~20-30 min.
3. **Redirect**: if a worker drifts or blocks, `order` a correction with exactly what to change.
4. **Escalate**: report a summary up (to the user) only when a milestone lands or a worker is stuck twice.

## Costs & cautions
- Every order/status = a full agent turn on the worker (loads its entire context — can be 100k+ tokens). Ping sparingly.
- If the worker is mid-generation, your prompt queues until it finishes.
- Workers share nothing with each other except their workspace files — coordinate through orders, or have workers leave notes in workspace files.
- Sessions are bound to their workspace; switching a worker's project is out of scope.
- Only supervise sessions you own. Ordering an unknown session executes a prompt in someone else's context.
