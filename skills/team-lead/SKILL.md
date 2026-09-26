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
