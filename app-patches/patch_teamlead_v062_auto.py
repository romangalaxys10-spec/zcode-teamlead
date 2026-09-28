#!/usr/bin/env python3
"""TeamLead v0.6.2: AUTO-TRIGGER routing.
- team.sh auto "<task text>" — keyword-classifies a task and routes it to the
  right capability (browser/cdp, dispatch/parallel, pdf, mirror, sandbox) with
  dry-run preview; executes with --run.
- SKILL.md trigger phrases so ZCode auto-invokes the skills from task text.
- AGENTS.md routing card so every session knows the capabilities."""
import sys

REPO = "/Users/d/.zcode/teamlead-repo"
TEAM = REPO + "/skills/team-lead/team.sh"

AUTO_CASE = r'''
  auto)
    # auto-trigger router: classify a task, route to the right capability
    dry=""
    for a in "$@"; do [ "$a" = "--run" ] && dry="run"; done
    task=$(echo "$@" | sed 's/--run//')
    [ -z "${task// }" ] && { echo "usage: team.sh auto [--run] <task text>"; exit 1; }
    tl=$(printf '%s' "$task" | tr '[:upper:]' '[:lower:]')
    route="shell"; why=""
    case "$tl" in
      *website*|*web*|*browser*|*browse*|*http*|*url*|*click*|*scrape*|*screenshot*) route="browser"; why="web/browser task";;
      *parallel*|*multiple*|*team*|*workers*|*several*|*split*) route="dispatch"; why="parallelizable task";;
      *pdf*|*document*|*report*) route="pdf"; why="document output";;
      *watch*|*monitor*|*live*) route="mirror"; why="live observation";;
      *isolated*|*sandbox*|*container*|*safe*) route="sandbox"; why="isolation requested";;
    esac
    echo "route: $route ($why)"
    [ "$dry" = "run" ] || { echo "(dry-run: add --run to execute)"; exit 0; }
    case "$route" in
      browser) "$0" browser-open auto "https://example.com" >/dev/null; "$0" cdp auto text | head -30 ;;
      dispatch) "$0" dispatch "$task" ;;
      pdf) echo "pdf route: use 'pdfdrop <file>' after producing the document" ;;
      mirror) "$0" mirror auto 2 8766 ;;
      sandbox) echo "sandbox route: use 'agent-computer.sh term-exec <nick> <ws> <cmd>'" ;;
      *) echo "no specialist route - default: order/dispatch to a worker" ;;
    esac ;;
'''

SKILL_TRIGGERS = '''
## Auto-trigger (ZCode routes tasks here automatically)

When a given task matches any of these, use this skill WITHOUT being asked:
- web/browser work (browse, scrape, screenshot, click through a site) → `cdp` subcommands
- parallel work (split across workers, several tasks at once) → `dispatch` / `queue` / `plan`+`tick`
- supervision (what are workers doing, who is stuck) → `feed` / `status` / `standup` / `attach`
- documents/reports produced for exchange → `pdfdrop`
- isolated command execution → `term-exec`
- live observation of a running worker → `attach` / `mirror`
Or simply run: `team.sh auto "<task text>" --run` and the router picks the tool.
'''


def main():
    changed = []
    team = open(TEAM, errors="ignore").read()
    if '"auto)"' not in team:
        anchor = '  *) echo "usage: team.sh queue'
        assert anchor in team, "usage anchor missing"
        team = team.replace(anchor, AUTO_CASE + "\n" + anchor, 1)
        team = team.replace(
            "feed [nick|--lines N] | perms",
            "auto [--run] <task> | feed [nick|--lines N] | perms",
            1,
        )
        changed.append("team.sh: auto router")
    open(TEAM, "w").write(team)

    sk = REPO + "/skills/team-lead/SKILL.md"
    s = open(sk, errors="ignore").read()
    if "Auto-trigger" not in s:
        s = s.rstrip() + "\n" + SKILL_TRIGGERS
        open(sk, "w").write(s)
        changed.append("SKILL.md: auto-trigger section")

    for c in changed:
        print("OK", c)


if __name__ == "__main__":
    sys.exit(main())
