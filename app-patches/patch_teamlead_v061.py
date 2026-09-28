#!/usr/bin/env python3
"""TeamLead v0.6.1: port the last three OpenMuse patterns.
- plan-card: boxed progress card from the scheduler state (done/active/blocked)
- stage <nick> <assigned|working|review|done>: delegated-task lifecycle in the roster
- filerec <nick>: record which files a worker touched (git porcelain) into receipts"""
import sys

TEAM = "/Users/d/.zcode/teamlead-repo/skills/team-lead/team.sh"

CASES = r'''
  plan-card)
    python3 - <<'ZCPYT'
import json, os
p = os.path.join(os.environ.get("ZCODE_TEAM_STATE", os.path.expanduser("~/.zcode/team-lead")), "scheduler.json")
try:
    s = json.load(open(p))
except Exception:
    print("no plan loaded (team.sh plan <goals.json>)"); raise SystemExit(0)
done = set(s.get("done", []))
tasks = s.get("tasks", [])
top = chr(9484) + " PLAN " + chr(9472) * 30
print(top)
for t in tasks:
    mark = chr(10003) if t["id"] in done else (chr(9654) if all(n in done for n in t.get("needs", [])) else chr(9679))
    print(chr(9474) + " " + mark + " " + t["id"] + ": " + t.get("goal", "")[:46])
d = len([t for t in tasks if t["id"] in done])
print(chr(9492) + chr(9472) * 3 + f" {d}/{len(tasks)} done")
ZCPYT
    ;;
  stage)
    nick="$1"; stage="$2"
    [ -z "$nick" ] || [ -z "$stage" ] && { echo "usage: team.sh stage <nick> <assigned|working|review|done>"; exit 1; }
    NICK="$nick" STAGE="$stage" python3 -c '
import json, os
p = os.environ["ZCODE_TEAM_ROSTER"]
try: r = json.load(open(p))
except Exception: r = {}
e = r.setdefault(os.environ["NICK"], {})
e["stage"] = os.environ["STAGE"]
json.dump(r, open(p, "w"), indent=1)
print(os.environ["NICK"], "->", os.environ["STAGE"])' ;;
  filerec)
    nick="$1"; ws="${2:-$PWD}"
    [ -d "$ws" ] || { echo "no dir: $ws"; exit 1; }
    (cd "$ws" && git status --porcelain 2>/dev/null) | NICK="$nick" WS="$ws" python3 -c '
import sys, os, time
lines = [l.rstrip() for l in sys.stdin if l.strip()]
entry = time.strftime("%F %T") + "  " + os.environ["NICK"] + "  " + os.environ["WS"] + "  files-touched: " + str(len(lines))
out = entry + ("\n    " + "\n    ".join(lines) if lines else "\n    (clean)")
p = os.environ.get("ZCODE_TEAM_ROSTER", os.path.expanduser("~/.zcode/team-roster.json")).replace(".json", "-receipts.txt")
open(p, "a").write(out + "\n")
print(out)'
    ;;
'''

old_usage_anchor = '  *) echo "usage: team.sh queue'
new_cases_block = CASES + "\n" + old_usage_anchor


def main():
    src = open(TEAM, errors="ignore").read()
    if "plan-card" in src:
        print("  already: v0.6.1"); return 0
    n = src.count(old_usage_anchor)
    assert n == 1, f"anchor count={n}"
    src = src.replace(old_usage_anchor, new_cases_block, 1)
    open(TEAM, "w").write(src)
    print("OK plan-card + stage + filerec added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
