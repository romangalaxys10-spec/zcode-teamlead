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
    if echo "$msg" | grep -iq "deploy\\|build\\|restart\\|ship"; then
      if [ -f "$ws/.team-deploy-lock" ]; then holder=$(cat "$ws/.team-deploy-lock"); case "$id" in "$holder") ;; *) echo "REFUSED: deploy window held by [$holder] — acquire/release via team.sh deploy-lock"; exit 1;; esac; fi
    fi
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
    mode=""; case "$mission" in "--plan "*) mode="plan"; mission="${mission#--plan }";; esac
    MODE_FLAG=""; [ -n "$mode" ] && MODE_FLAG="--mode plan"
    cd "$ws" || exit 1
    out=$(timeout 900 node "$ZC" $MODE_FLAG -p "You are $name on this project ($mode${mode:+, read-only} worker). Role/mission: $mission Confirm by replying: READY <one-line understanding>." --target "$name — $mission" --json 2>/dev/null)
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
  broadcast)
    [ -z "$1" ] && { echo "usage: team.sh broadcast <message...>"; exit 1; }
    msg="$*"
    python3 -c '
import json, os
try: r = json.load(open(os.environ["ZCODE_TEAM_ROSTER"]))
except Exception: r = {}
[print(k) for k in r]' | while read -r nick; do
      echo ">>> $nick"
      "$0" order "$nick" "$msg" || true
    done
    ;;
  tell)
    from="$1"; to="$2"; shift 3
    [ -z "$to" ] && { echo "usage: team.sh tell <fromNick> <toNick|sessId> <message...>"; exit 1; }
    "$0" order "$to" "RELAYED MESSAGE from $from (team lead relaying): $*" ;;
  proof)
    id=$(resolve "$1"); [ -z "$id" ] && { echo "usage: team.sh proof <sessId|nick>"; exit 1; }
    ws=$(sqlite3 "$DB" "SELECT workspace_path FROM tasks WHERE task_id='$id' LIMIT 1")
    [ -d "$ws" ] || exit 1
    echo "== objective proof @ $ws"
    (cd "$ws" && git log -3 --format='%h %ci %s' 2>/dev/null || echo "(not a git repo)")
    echo "branch: $(cd "$ws" && git branch --show-current 2>/dev/null)"
    echo "dirty files: $(cd "$ws" && git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
    echo "last commit age: $(cd "$ws" && git log -1 --format='%cr' 2>/dev/null)" ;;
  standup)
    echo "=== TEAM STANDUP $(date) ==="
    "$0" all-status
    echo; echo "=== workspaces ==="
    python3 -c '
import json, os
try: r = json.load(open(os.environ["ZCODE_TEAM_ROSTER"]))
except Exception: r = {}
[print(v.get("workspace","")) for v in r.values()]' | sort -u | while read -r w; do
      [ -d "$w" ] || continue
      echo "-- $w"
      (cd "$w" && git log -1 --format='head: %h %s' 2>/dev/null; echo "dirty: $(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')")
    done
    [ -n "$TEAM_WEBHOOK" ] && "$0" notify "📊 standup posted $(date '+%H:%M')" ;;
  notify)
    [ -z "$1" ] && { echo "usage: team.sh notify <text...>  (set TEAM_WEBHOOK to a Discord-style webhook URL)"; exit 1; }
    text="$*"
    mkdir -p "$(dirname "$ROSTER")"
    echo "[$(date '+%F %T')] $text" >> "${ROSTER%.json}-log.txt"
    if [ -n "$TEAM_WEBHOOK" ]; then
      curl -s -X POST -H 'content-type: application/json' -d "{\"content\":$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$text")}" "$TEAM_WEBHOOK" >/dev/null && echo "notified via webhook" || echo "webhook failed"
    else
      echo "(logged only — set TEAM_WEBHOOK to deliver) $text"
    fi ;;
  watch)
    iv="${1:-120}"
    while :; do
      clear 2>/dev/null || true
      echo "=== TEAM WATCH (refresh ${iv}s) — $(date) ==="
      "$0" all-status
      sleep "$iv"
    done ;;
  deploy-lock)
    op="$1"; nick="$2"
    ws="${3:-$PWD}"
    lock="$ws/.team-deploy-lock"
    case "$op" in
      acquire)
        if [ -f "$lock" ]; then holder=$(cat "$lock"); case "$holder" in "$nick "*) echo "lock already held by: $holder";; *) echo "LOCK HELD by: $holder — deploy window busy"; exit 1;; esac; fi
        echo "$nick $(date '+%F %T')" > "$lock"; echo "deploy window acquired: $nick" ;;
      release) rm -f "$lock" && echo "deploy window released ($nick)" ;;
      status) [ -f "$lock" ] && cat "$lock" || echo "no lock" ;;
      *) echo "usage: team.sh deploy-lock acquire|release|status <nick> [wsDir]" ;;
    esac ;;
  autopoll)
    op="$1"; mins="${2:-20}"
    tag="# teamlead-autopoll"
    line="*/$mins * * * * /bin/sh $(cd "$(dirname "$0")" && pwd)/team.sh autopoll-run $tag"
    case "$op" in
      on)
        (crontab -l 2>/dev/null | grep -v "$tag"; echo "$line") | crontab - 2>/dev/null \
          && echo "autopoll ON: every ${mins}min (log: ~/.zcode/team-autopoll.log; set TEAM_WEBHOOK for delivery)" \
          || { echo "crontab unavailable — add manually:"; echo "$line"; } ;;
      off) (crontab -l 2>/dev/null | grep -v "$tag") | crontab - 2>/dev/null && echo "autopoll OFF" ;;
      run)
        log="$HOME/.zcode/team-autopoll.log"
        { echo "=== autopoll $(date) ==="; "$0" all-status; } >> "$log" 2>&1
        [ "$(wc -c < "$log")" -gt 204800 ] && tail -c 102400 "$log" > "$log.tmp" && mv "$log.tmp" "$log"
        [ -n "$TEAM_WEBHOOK" ] && "$0" notify "🤖 autopoll ran — see log ($log)" ;;
      *) echo "usage: team.sh autopoll on [minutes] | off | run" ;;
    esac ;;
  *) echo "usage: team.sh list | roster | all-status | status <id|nick> | order <id|nick> <msg...> | nudge <id|nick> | broadcast <msg...> | tell <from> <to> <msg...> | proof <id|nick> | standup | notify <text...> | watch [sec] | deploy-lock acquire|release|status <nick> [ws] | autopoll on [min]|off|run | hire <nick> <wsDir> [--plan] [mission] | title <id|nick>" ;;
esac
