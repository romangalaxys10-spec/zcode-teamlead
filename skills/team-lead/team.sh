#!/bin/sh
# team.sh — team-lead toolkit: operate/supervise other ZCode sessions from inside a session.
# Env overrides: ZCODE_CLI (path to zcode.cjs), ZCODE_TASKS_DB (tasks-index.sqlite).
# Usage:
#   team.sh list                     — all sessions (id | title | workspace)
#   team.sh order <sessId> <msg...>  — inject a directive into a session, print its reply
#   team.sh status <sessId>          — standard 3-line status check
#   team.sh title <sessId>           — lookup title
DB="${ZCODE_TASKS_DB:-$HOME/.zcode/v2/tasks-index.sqlite}"
ZC="${ZCODE_CLI:-/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs}"
cmd="$1"; [ $# -gt 0 ] && shift
case "$cmd" in
  list)
    sqlite3 "$DB" "SELECT task_id||'  |  '||substr(coalesce(title,'(untitled)'),1,45)||'  |  '||workspace_path FROM tasks ORDER BY rowid DESC" ;;
  title)
    sqlite3 "$DB" "SELECT coalesce(title,'(untitled)') FROM tasks WHERE task_id='$1' LIMIT 1" ;;
  order|status)
    id="$1"; [ -z "$id" ] && { echo "usage: team.sh $cmd <sessId> <message...>"; exit 1; }
    echo "$id" | grep -q '^sess_[A-Za-z0-9-]*$' || { echo "bad session id"; exit 1; }
    ws=$(sqlite3 "$DB" "SELECT workspace_path FROM tasks WHERE task_id='$id' LIMIT 1")
    [ -z "$ws" ] && { echo "unknown session: $id"; exit 1; }
    if [ "$cmd" = "status" ]; then
      msg="STATUS CHECK: reply in 3 short lines — Task: <current> | Progress: <pct> | Blockers: <none/list>. Do not use tools."
    else
      shift; msg="$*"
    fi
    cd "$ws" || exit 1
    timeout 900 node "$ZC" --resume "$id" -p "$msg" --json 2>/dev/null \
      | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("response","(no response)"))
except Exception as e: print("ORDER FAILED:", e)'
  ;;
  *) echo "usage: team.sh list | order <sessId> <msg...> | status <sessId> | title <sessId>" ;;
esac
