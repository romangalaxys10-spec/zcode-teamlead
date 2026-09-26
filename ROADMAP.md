# 🗺️ TeamLead Strategy & Staffing Doctrine

How a team-lead session plans, staffs, and runs a project. This is the doctrine
the skill encodes — steal it for your own teams.

## Project lifecycle (5 phases)

| Phase | Lead activity | Team shape |
|---|---|---|
| 1. Bootstrap | Write the goal, definition of done, and **ownership map** (who owns which paths) | lead only |
| 2. Staff up | `hire` devs with lanes + hard bans; publish COORDINATION.md in the repo | lead + 2–4 devs |
| 3. Parallel build | `order` per lane, `all-status` on milestones, `proof` on every "done" | full team, one deploy-window holder |
| 4. Integrate & verify | read-only `--plan` workers sweep regressions while writers freeze | + QA lane |
| 5. Ship & harden | serialized deploy, `proof` on the live target, retrospective into project memory | lead + 1 |

## Staffing matrix — how many devs?

| Project size | Roster | Lanes |
|---|---|---|
| **Small** (one feature, days) | lead + **2 devs** | dev1 build · dev2 verify (`--plan`) |
| **Medium** (multi-feature, weeks) | lead + **3 devs** | dev1 backend · dev2 frontend · dev3 QA (`--plan`, read-only sweeps) |
| **Large** (product, ongoing) | lead + **4–5 devs** | dev1 backend · dev2 frontend · dev3 QA (`--plan`) · dev4 devops (deploy windows, monitoring) · dev5 floater (unblocks whoever is stuck) |

**Rule of thumb:** one code-writer per deploy window; every writer gets a
read-only counterpart. The lead **never codes** — it plans, orders, verifies, escalates.

## Lanes & skills per dev

| Role | Owns | Skills assigned | Hard bans |
|---|---|---|---|
| **dev1 — Backend** | `server/**`, API contracts, DB schema | API design, security hardening (authn/z, input validation, secrets), migrations, load checks | never touches frontend files; never deploys during another's window |
| **dev2 — Frontend** | `src/components/**`, pages, UX flows | React/Tailwind, state management, performance, accessibility, funnel re-verification after API changes | never edits server/**; pulls before builds |
| **dev3 — QA (`--plan`)** | nothing — read-only | regression sweeps, security audit (exposed endpoints, leaked secrets), spec-vs-build diff | zero file writes by definition; read-only mode enforced by the CLI |
| **dev4 — DevOps** | deploy pipeline, service health, monitoring | build/release, rollback, log/triage, tunnel/infra | only worker allowed to hold the deploy lock; announces windows |
| **dev5 — Floater** | whatever is blocked | inherits the stuck lane's skills | must announce lane takeover in COORDINATION.md |

## Orders that work (task-packet format)

```
team.sh order dev1 "GOAL: <outcome>. DONE WHEN: <3 verifiable conditions>.
OWNERSHIP: only <paths>. BANS: <what not to touch>. PROOF: show <git hash /
bundle hash / curl output> — the word 'done' requires evidence.
Report format: 3 lines max."
```

- Scope/ownership hat → mission → hard bans → proof protocol → report cap
- Claims are not facts: run `team.sh proof <dev>` after every "deployed"
- Foreground workers die when you type — background everything

## Coordination artifacts (in the shared repo)

- `COORDINATION.md` — ownership map, deploy-window log, announce-before-touch rules
- `.team-deploy-lock` — the serialization lock (toolkit-enforced)
- project memory — retrospectives, conventions, "why we stopped doing X"

## Anti-patterns (all learned the hard way)

- ❌ Two writers, one deploy window — serialize or suffer reverts
- ❌ `git add -A` on a shared tree — per-file staging only
- ❌ Believing "deploying now" without a bundle hash / commit id
- ❌ Letting the supervisor write code — it stops supervising
- ❌ Micro-managing — orders carry goals, not steps
