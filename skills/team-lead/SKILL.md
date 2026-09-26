# Skill: team-lead
Operate and supervise other ZCode sessions from this session. Toolkit: `./team.sh` (relative to this skill's directory; run as `bash ./team.sh ...`).

## Commands
- `bash ./team.sh list` — discover sessions (id | title | workspace).
- `bash ./team.sh roster` — your named workers (nickname → session, role, workspace).
- `bash ./team.sh status <sessId|nick>` — 3-line check-in (Task / Progress / Blockers).
- `bash ./team.sh all-status` — status of every rostered worker in one shot.
- `bash ./team.sh order <sessId|nick> <message>` — inject a directive; the reply is the worker's response.
- `bash ./team.sh nudge <sessId|nick>` — force a stopped/idle worker to continue its last task.
- `bash ./team.sh hire <nickname> <workspaceDir> [role+mission]` — create a NEW session, give it a nickname and role; it's rostered and addressable by name forever.
- `bash ./team.sh title <sessId|nick>` — lookup a session's title.
- `bash ./team.sh broadcast <msg>` — one order to every rostered worker.
- `bash ./team.sh tell <fromNick> <toNick> <msg>` — relay a message between workers.
- `bash ./team.sh proof <sessId|nick>` — objective facts from the worker's workspace (git log, dirty files, commit age). Claims are not facts — verify.
- `bash ./team.sh standup` — all-status + workspace git summary in one report.
- `bash ./team.sh notify <text>` — push a report to your phone (set `TEAM_WEBHOOK` to a Discord-style webhook URL); always logged to `~/.zcode/team-roster-log.txt`.
- `bash ./team.sh watch [sec]` — live all-status dashboard loop.
- `bash ./team.sh deploy-lock acquire|release|status <nick> [wsDir]` — serialize deploy windows; `order` messages mentioning deploy/build/restart are REFUSED while another worker holds the lock.
- `bash ./team.sh autopoll on [min]|off|run` — cron-driven self-waking supervision (all-status + notify on a schedule, no human needed).

## Staffing doctrine
For project planning — how many devs to `hire`, which lanes/skills/bans each gets —
read [ROADMAP.md](../../ROADMAP.md) (staffing matrix + task-packet order format + anti-patterns).
Default shape: lead (never codes) + backend + frontend + read-only QA (`hire <nick> <ws> --plan <mission>` spawns a plan-mode worker that cannot edit files).

## Lead protocol
1. **Assign**: one `order` per worker with a concrete goal, definition of done, and deadline. Workers act in their own permission context (headless runs default to yolo).
2. **Progress requests are immediate**: if the user asks "progress?" / "status?" — even mid-task — run `all-status` NOW, compile one report, and reply. Never defer a progress request.
3. **Poll**: `status` on milestones or every ~20-30 min. Don't micro-manage.
4. **Redirect**: worker drifting? `order` an exact correction.
5. **Nudge**: worker stopped/idle but work remains? `nudge` it to resume and report.
6. **Scale**: more work than workers? `hire` a new named session (e.g. `hire dev3 <workspace> "Backend tests + CI guard"`) and give it a lane.
7. **Escalate**: report a summary up only when a milestone lands or a worker is stuck twice.

## Costs & cautions
- Every order/status = a full agent turn on the worker (loads its entire context — can be 100k+ tokens). Ping sparingly.
- If the worker is mid-generation, your prompt queues until it finishes.
- Workers share nothing with each other except their workspace files — coordinate through orders or workspace-file notes.
- Sessions are bound to their workspace; `hire` into the workspace the work belongs to.
- Only supervise sessions you own. Ordering an unknown session executes a prompt in someone else's context.
