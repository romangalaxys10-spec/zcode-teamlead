#!/bin/sh
# team.sh v0.2 — team-lead toolkit: operate/supervise other ZCode sessions.
# Env: ZCODE_CLI, ZCODE_TASKS_DB, ZCODE_TEAM_ROSTER (default ~/.zcode/team-roster.json)
DB="${ZCODE_TASKS_DB:-$HOME/.zcode/v2/tasks-index.sqlite}"
ROSTER="${ZCODE_TEAM_ROSTER:-$HOME/.zcode/team-roster.json}"
export ZCODE_TEAM_ROSTER="$ROSTER"
ZC="${ZCODE_CLI:-/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs}"
cmd="$1"; [ $# -gt 0 ] && shift

resolve() { # nickname-or-sessId -> sessId
  case "$1" in
    sess_*) echo "$1" ;;
    *) NAME="$1" python3 -c '
import json, os
try: r = json.load(open(os.environ["ZCODE_TEAM_ROSTER"]))
except Exception: r = {}
print((r.get(os.environ["NAME"]) or {}).get("sessId", ""))' ;;
  esac
}

case "$cmd" in
  list)
    sqlite3 "$DB" "SELECT task_id||'  |  '||substr(coalesce(title,'(untitled)'),1,45)||'  |  '||workspace_path FROM tasks ORDER BY rowid DESC" ;;
  roster)
    python3 -c '
import json, os
try: r = json.load(open(os.environ["ZCODE_TEAM_ROSTER"]))
except Exception: r = {}
for k, v in r.items():
    print(k, " -> ", v.get("sessId",""), " | ", v.get("role","")[:60], " | ", v.get("workspace",""))' ;;
  title)
    id=$(resolve "$1")
    sqlite3 "$DB" "SELECT coalesce(title,'(untitled)') FROM tasks WHERE task_id='$id' LIMIT 1" ;;
  status|order|nudge)
    id=$(resolve "$1"); [ -z "$id" ] && { echo "usage: team.sh $cmd <sessId|nickname> [message...]"; exit 1; }
    echo "$id" | grep -q '^sess_[A-Za-z0-9-]*$' || { echo "bad session id"; exit 1; }
    ws=$(sqlite3 "$DB" "SELECT workspace_path FROM tasks WHERE task_id='$id' LIMIT 1")
    [ -z "$ws" ] && ws=$(NAME="$id" python3 -c '
import json, os
try: r = json.load(open(os.environ["ZCODE_TEAM_ROSTER"]))
except Exception: r = {}
print((r.get(os.environ["NAME"]) or {}).get("workspace", ""))')
    [ -z "$ws" ] && { echo "unknown session: $id"; exit 1; }
    if [ "$cmd" = "status" ]; then
      msg="STATUS CHECK: reply in 3 short lines — Task: <current> | Progress: <pct> | Blockers: <none/list>. Do not use tools."
    elif [ "$cmd" = "nudge" ]; then
      msg="CONTINUE: pick up where you left off — re-check your last task state and keep driving it to completion. If truly nothing is pending, reply IDLE with what you need next. Report progress when done."
    else
      shift; msg="$*"
      [ -z "$msg" ] && { echo "usage: team.sh order <sessId|nickname> <message...>"; exit 1; }
    fi
    cd "$ws" || exit 1
    timeout 900 node "$ZC" --resume "$id" -p "$msg" --json 2>/dev/null \
      | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("response","(no response)"))
except Exception as e: print("ORDER FAILED:", e)'
  ;;
  all-status)
    ids=$(python3 -c '
import json, os
try: r = json.load(open(os.environ["ZCODE_TEAM_ROSTER"]))
except Exception: r = {}
[print(v["sessId"]) for v in r.values()]')
    [ -z "$ids" ] && ids=$(sqlite3 "$DB" "SELECT task_id FROM tasks ORDER BY rowid DESC LIMIT 6")
    n=0
    for id in $ids; do
      n=$((n+1)); [ $n -gt 1 ] && echo "---"
      echo "== $id"
      "$0" status "$id"
    done ;;
  hire)
    name="$1"; ws="$2"; [ $# -gt 2 ] && shift 2
    mission="$*"
    [ -z "$name" ] || [ -z "$ws" ] && { echo 'usage: team.sh hire <nickname> <workspaceDir> [role+mission]'; exit 1; }
    echo "$name" | grep -q '^[A-Za-z0-9_-]*$' || { echo "bad nickname (alnum/-/_ only)"; exit 1; }
    [ -d "$ws" ] || { echo "no such workspace dir: $ws"; exit 1; }
    [ -z "$mission" ] && mission="You are $name, a dev worker on this project. Await task orders from the team lead."
    cd "$ws" || exit 1
    out=$(timeout 900 node "$ZC" -p "You are $name on this project. Role/mission: $mission Confirm by replying: READY <one-line understanding>." --target "$name — $mission" --json 2>/dev/null)
    sid=$(printf '%s' "$out" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("sessionId",""))
except Exception: print("")')
    [ -z "$sid" ] && { echo "HIRE FAILED:"; printf '%s\n' "$out" | tail -3; exit 1; }
    MISSION="$mission" WS="$ws" SID="$sid" NAME="$name" python3 -c '
import json, os
p = os.environ["ZCODE_TEAM_ROSTER"]
try: r = json.load(open(p))
except Exception: r = {}
r[os.environ["NAME"]] = {"sessId": os.environ["SID"], "role": os.environ["MISSION"][:160], "workspace": os.environ["WS"]}
json.dump(r, open(p, "w"), indent=1)'
    echo "rostered: $name -> $sid"
    printf '%s\n' "$out" | python3 -c 'import json,sys
try: print("reply:", (json.load(sys.stdin).get("response") or "")[:200])
except Exception: pass'
  ;;
  *) echo "usage: team.sh list | roster | all-status | status <id|nick> | order <id|nick> <msg...> | nudge <id|nick> | hire <nick> <wsDir> [mission] | title <id|nick>" ;;
esac
