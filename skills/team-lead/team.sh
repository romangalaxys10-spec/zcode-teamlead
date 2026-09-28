#!/bin/sh
# team.sh v0.2 — team-lead toolkit: operate/supervise other ZCode sessions.
# Env: ZCODE_CLI, ZCODE_TASKS_DB, ZCODE_TEAM_ROSTER (default ~/.zcode/team-roster.json)
DB="${ZCODE_TASKS_DB:-$HOME/.zcode/v2/tasks-index.sqlite}"
ROSTER="${ZCODE_TEAM_ROSTER:-$HOME/.zcode/team-roster.json}"
export ZCODE_TEAM_ROSTER="$ROSTER"
ZC="${ZCODE_CLI:-/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs}"
LEADLIB="$(cd "$(dirname "$0")" && pwd)/leadlib.py"
TEAM_DRY="${TEAM_DRY_RUN:-0}"
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
    raw="$1"
    id=$(resolve "$raw"); [ -z "$id" ] && { echo "usage: team.sh $cmd <sessId|nickname> [message...]"; exit 1; }
    echo "$id" | grep -q '^sess_[A-Za-z0-9-]*$' || { echo "bad session id"; exit 1; }
    ws=$(sqlite3 "$DB" "SELECT workspace_path FROM tasks WHERE task_id='$id' LIMIT 1")
    [ -z "$ws" ] && ws=$(NAME="$raw" python3 -c '
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
    out=$(timeout 900 node "$ZC" $MODE_FLAG -p "/goal $name — $mission
You are $name on this project ($mode${mode:+, read-only} worker). Role/mission: $mission Confirm by replying: READY <one-line understanding>." --json 2>/dev/null)
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

  feed)
    python3 "$LEADLIB" feed "$@" ;;
  perms)
    if [ "${1:-}" = "--push" ]; then shift; python3 "$LEADLIB" perms "$@" | while IFS= read -r l; do echo "$l"; "$0" notify "$l"; done
    else python3 "$LEADLIB" perms "$@"; fi ;;
  burn)
    python3 "$LEADLIB" burn "$@" ;;
  handoff)
    python3 "$LEADLIB" handoff "$@" ;;
  plan)
    f="$1"; [ -f "$f" ] || { echo "usage: team.sh plan <goals.json>  ({tasks:[{id,needs:[],goal,nick}]})"; exit 1; }
    GOALS="$f" python3 -c '
import json, os, sys
g = json.load(open(os.environ["GOALS"]))
tasks = g.get("tasks", [])
ids = {t["id"] for t in tasks}
bad = [n for t in tasks for n in t.get("needs", []) if n not in ids]
if bad:
    print("unknown deps:", bad); sys.exit(1)
for t in tasks:
    if not t.get("id"):
        print("task missing id"); sys.exit(1)
    for field in ("id", "goal", "nick"):
        v = str(t.get(field, ""))
        if "\n" in v or "\t" in v:
            print("task", t["id"], "field", field, "must not contain newlines/tabs"); sys.exit(1)
state = {"tasks": tasks, "done": []}
p = os.path.join(os.environ.get("ZCODE_TEAM_STATE", os.path.expanduser("~/.zcode/team-lead")), "scheduler.json")
os.makedirs(os.path.dirname(p), exist_ok=True)
json.dump(state, open(p, "w"), indent=1)
print("plan loaded:", len(tasks), "tasks ->", p)' ;;
  done)
    tid="$1"; [ -z "$tid" ] && { echo "usage: team.sh done <taskId>"; exit 1; }
    TID="$tid" python3 -c '
import json, os
p = os.path.join(os.environ.get("ZCODE_TEAM_STATE", os.path.expanduser("~/.zcode/team-lead")), "scheduler.json")
try: s = json.load(open(p))
except Exception: s = {}
s.setdefault("done", []).append(os.environ["TID"])
json.dump(s, open(p, "w"), indent=1)
print("marked done:", os.environ["TID"])' ;;
  tick)
    TICKF=$(mktemp)
    ZCODE_TEAM_STATE="${ZCODE_TEAM_STATE:-$HOME/.zcode/team-lead}" python3 -c '
import json, os, sys
p = os.path.join(os.environ["ZCODE_TEAM_STATE"], "scheduler.json")
try:
    s = json.load(open(p))
except FileNotFoundError:
    sys.exit(0)
except Exception as e:
    print("WARN: corrupt scheduler state, skipping tick:", e, file=sys.stderr); sys.exit(0)
done = set(s.get("done", []))
for t in s.get("tasks", []):
    if t["id"] in done:
        continue
    wait = [n for n in t.get("needs", []) if n not in done]
    if wait:
        print("BLOCKED\t" + t["id"] + "\t\twaiting on: " + ", ".join(wait))
    else:
        print("READY\t" + t["id"] + "\t" + t.get("nick", "") + "\t" + t.get("goal", ""))
' > "$TICKF"
    rc=0
    while IFS="$(printf '\t')" read -r kind tid nick goal; do
      case "$kind" in
        BLOCKED) echo "PAUSED $tid - $goal";;
        READY)
          if [ "$TEAM_DRY" = "1" ]; then
            echo "(dry) would order ${nick:-$tid}: $goal"
          else
            echo "ordering ${nick:-$tid}: $goal"
            if "$0" order "${nick:-$tid}" "$goal"; then
              "$0" done "$tid"
            else
              echo "order FAILED for $tid - left pending, retry next tick"
              rc=1
            fi
          fi;;
      esac
    done < "$TICKF"
    rm -f "$TICKF"; exit $rc ;;
  qa)
    raw="$1"; [ -z "$raw" ] && { echo "usage: team.sh qa <sessId|nick> [--dry-run]"; exit 1; }
    id=$(resolve "$raw")
    prompt="ADVERSARIAL QA REVIEW: you are a fresh, read-only reviewer with NO stake in the prior work. 1) Write 3-6 concrete edge-case/attack tests this workspace's recent changes must survive (boundaries, empty, concurrency, unicode, security). 2) Attempt to BREAK the recent changes - run the focused checks, try the attacks. 3) Report findings as BLOCKER/MAJOR/MINOR with file:line evidence, or PASS with the checks you ran. Never trust the implementer's claims; verify by execution."
    case "${2:-}" in
      --dry-run) echo "QA PROMPT (dry): $prompt"; exit 0;;
    esac
    ws=$(sqlite3 "$DB" "SELECT workspace_path FROM tasks WHERE task_id='$id' LIMIT 1")
    [ -d "$ws" ] || { echo "unknown workspace for $raw"; exit 1; }
    qa_name="qa-$(date +%s)"
    "$0" hire "$qa_name" "$ws" "--plan $prompt" || exit 1
    "$0" order "$qa_name" "Proceed with the adversarial review per your role. Report BLOCKER/MAJOR/MINOR with evidence, or PASS with executed checks." ;;
  register)
    nick="$1"; shift
    [ -z "$nick" ] && { echo "usage: team.sh register <nick> key=value ...  (e.g. caps=algo,rust model=glm)"; exit 1; }
    NICK="$nick" KV="$*" python3 -c '
import json, os
p = os.environ["ZCODE_TEAM_ROSTER"]
try: r = json.load(open(p))
except Exception: r = {}
e = r.setdefault(os.environ["NICK"], {})
for kv in os.environ["KV"].split():
    k, _, v = kv.partition("=")
    e[k] = v.split(",") if "," in v else v
json.dump(r, open(p, "w"), indent=1)
print("registered:", os.environ["NICK"], e)' ;;
  dispatch)
    caps=""; dry=""; task=""
    while [ $# -gt 0 ]; do
      case "$1" in
        cap:*) caps="${1#cap:}";;
        --dry-run) dry=1;;
        *) task="$task $1";;
      esac
      shift
    done
    task="${task# }"
    [ -z "$task" ] && { echo "usage: team.sh dispatch [--dry-run] [cap:tags] <task...>"; exit 1; }
    CHOICE=$(ZCODE_SESSION_DB="${ZCODE_SESSION_DB:-$HOME/.zcode/cli/db/db.sqlite}" CAPS="$caps" RST="$ROSTER" python3 -c '
import json, os, sqlite3, time
roster = json.load(open(os.environ["RST"]))
caps = set(filter(None, os.environ["CAPS"].split(",")))
con = sqlite3.connect(os.environ["ZCODE_SESSION_DB"])
since = (time.time() - 3600) * 1000
cands = []
for nick, v in roster.items():
    rcaps = set(v.get("caps", [])) if isinstance(v.get("caps"), list) else set()
    if caps and not (rcaps & caps):
        continue
    sid = v.get("sessId", "")
    if not sid.startswith("sess_"):
        continue
    row = con.execute("SELECT sum(CASE WHEN status=:s THEN 1 ELSE 0 END), coalesce(max(started_at),0) FROM turn_usage WHERE session_id=:i", {"s": "running", "i": sid}).fetchone()
    running, last = row if row else (0, 0)
    cands.append((running or 0, -(last or 0), nick, sid))
cands.sort()
print(cands[0][3] if cands else "")')
    [ -z "$CHOICE" ] && { echo "no capable worker found"; exit 1; }
    if [ -n "$dry" ]; then echo "(dry) would dispatch to: $CHOICE - task:$task"; exit 0; fi
    echo "dispatching to $CHOICE"
    "$0" order "$CHOICE" "$task" ;;
  gate)
    ws="$1"; stage="$2"; verdict="$3"
    if [ "$verdict" = "status" ]; then
      cat "$ws/.team-gates.json" 2>/dev/null || echo "(no gates recorded for $ws)"
    else
      GATE_WS="$ws" GATE_STAGE="$stage" GATE_VERDICT="$verdict" python3 -c '
import json, os, time
gf = os.path.join(os.environ["GATE_WS"], ".team-gates.json")
try: g = json.load(open(gf))
except Exception: g = {}
g[os.environ["GATE_STAGE"]] = {"verdict": os.environ["GATE_VERDICT"], "at": time.strftime("%F %T")}
json.dump(g, open(gf, "w"), indent=1)
print("gate", os.environ["GATE_STAGE"], "=", os.environ["GATE_VERDICT"])'
    fi ;;

  rollback)
    ws="$1"; tag="$2"; force="${3:-}"
    [ -d "$ws" ] || { echo "no dir: $ws"; exit 1; }
    if [ "$force" = "--force" ]; then
      (cd "$ws" && git reset --hard "$tag" && echo "rolled back to $tag") || echo "rollback FAILED"
    else
      echo "(dry) would run: cd $ws && git reset --hard $tag   - add --force to execute"
    fi ;;
  patches)
    op="${1:-status}"
    case "$op" in
      status)
        APP_ASAR="${ZCODE_APP_ASAR:-/Applications/ZCode.app/Contents/Resources/app.asar}" python3 -c '
import json, struct, os
p = os.environ["APP_ASAR"]
f = open(p, "rb"); f.seek(4); hs = struct.unpack("<I", f.read(4))[0]
f.seek(16); h = json.loads(f.read(hs-8).rstrip(b"\0"))
node = h["files"]["out"]["files"]["host"]["files"]["index.js"]
f.seek(8 + hs + int(node["offset"])); src = f.read(node["size"]).decode("utf-8", "replace")
pkg = h["files"]["package.json"]
f.seek(8 + hs + int(pkg["offset"])); pkgsrc = f.read(pkg["size"]).decode()
checks = [("supervisor mode", "ZCODE_SUPERVISOR_V1" in src), ("group chats", "ZCODE_GROUPS_V1" in src),
          ("discord adapter", "ZCODE_discordAdapter" in src), ("voice bootstrap", "voice-bootstrap" in pkgsrc)]
print("=== patch fleet status ===")
ok = True
for name, present in checks:
    print(("APPLIED " if present else "MISSING "), name)
    ok = ok and present
print("ALL APPLIED" if ok else "DRIFT DETECTED - reapply needed")'
        ;;
      reapply)
        if [ "${2:-}" = "--yes" ] && [ -f "$HOME/.zcode/scripts/reapply_all.sh" ]; then
          bash "$HOME/.zcode/scripts/reapply_all.sh"
        elif [ "${2:-}" = "--yes" ]; then
          echo "reapply_all.sh missing (see tools/reapply-patches.sh)"
        else
          echo "this re-patches the installed app; confirm with: team.sh patches reapply --yes"
        fi ;;
      *) echo "usage: team.sh patches status|reapply [--yes]";;
    esac ;;

  *) echo "usage: team.sh feed [nick|--lines N] | perms [--minutes M|--push] | burn [--days D] [nick] | handoff <id|nick> [out.md] | plan <goals.json> | tick | done <taskId> | qa <id|nick> [--dry-run] | register <nick> k=v... | dispatch [--dry-run] [cap:tags] <task...> | gate <ws> <stage> pass|fail|status | rollback <ws> <tag> [--force] | patches status | list | roster | all-status | status <id|nick> | order <id|nick> <msg...> | nudge <id|nick> | broadcast <msg...> | tell <from> <to> <msg...> | proof <id|nick> | standup | notify <text...> | watch [sec] | deploy-lock acquire|release|status <nick> [ws] | autopoll on [min]|off|run | hire <nick> <wsDir> [--plan] [mission] | title <id|nick>" ;;
esac
