# ZCode TeamLead 🧭

Turn any ZCode session into a **team lead** that operates, supervises and manages your other sessions — assign goals, poll status, redirect drift, get things done.

```
You ──▶ TeamLead session ──▶ "Supra-Dev #1"  (assign goal, poll status)
                      ──────▶ "Super-Dev #2" (assign goal, poll status)
```

## How it works

ZCode's CLI can resume any persisted session and inject a prompt:

```bash
zcode --resume <sessId> -p "your directive" --json
```

The plugin wraps this into a toolkit + a lead protocol skill, so a lead session can run its team hands-free.

## Install

**From this repo (marketplace):**
```bash
zcode plugins marketplace add <your-github-user>/zcode-teamlead
zcode plugins install team-lead@zcode-teamlead
```

**Or manually** — copy the skill:
```bash
git clone https://github.com/<your-github-user>/zcode-teamlead
mkdir -p ~/.zcode/skills
cp -r zcode-teamlead/skills/team-lead ~/.zcode/skills/
```

Then start a new ZCode session (or mention `/team` / the team-lead skill in an existing one).

## Usage

```bash
# discover sessions
bash ./skills/team-lead/team.sh list
#   sess_cbe7857e…  |  Supervisor TeamLead (TG)  |  ~/Projects/Supra-Tengiz
#   sess_58bddcee…  |  Supra-Dev #1             |  ~/Projects/Supra-Tengiz

# standard check-in
bash ./skills/team-lead/team.sh status sess_58bddcee-003b-441d-8396-a39fafdb488b
#   Task: guest-page rework | Progress: 100% | Blockers: none

# assign work
bash ./skills/team-lead/team.sh order sess_58bddcee-003b-441d-8396-a39fafdb488b \
  "Implement dark-mode toggle on settings page. Done = toggle persists, tests pass. Report when shipped."
```

Or in a session, just tell the lead: *"Use the team-lead skill: manage sess_A and sess_B — goal: ship X by 5pm. Poll status every 20 minutes."*

## The lead protocol (from the skill)

1. **Assign** — one order per worker: concrete goal + definition of done + deadline
2. **Poll** — `status` on milestones, not constantly
3. **Redirect** — correction orders when a worker drifts
4. **Escalate** — summarize to the human when a milestone lands or a worker is stuck twice

## Requirements

- ZCode desktop or CLI (`zcode`) on macOS/Linux
- `sqlite3`, `python3`, `node` on PATH
- Env overrides: `ZCODE_CLI` (path to `zcode.cjs`), `ZCODE_TASKS_DB` (path to `tasks-index.sqlite`)

## Costs & safety

- Every `order`/`status` is a **full agent turn** on the target session (its entire context is loaded — can be 100k+ tokens). Poll on milestones.
- Headless orders run with the session's permission mode (CLI `-p` defaults to **yolo**) — order sessions you trust.
- Only supervise sessions you own: an order executes a prompt in that session's context.
- Prompts sent to a busy session queue until it finishes.

## License

MIT

## Bonus: unlock bot group chats (unofficial app patch)

The Telegram group-chat support this plugin was born from is an app-bundle mod,
not plugin material — it lives in [`app-patches/`](app-patches/): bots answer in
groups, every group member can drive them, `@botname` command suffixes parse.
Byte-exact for macOS ZCode 3.14.3.7762; aborts safely on other versions.

```bash
python3 app-patches/patch-zcode-bots.py
```
