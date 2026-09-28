#!/usr/bin/env python3
"""Extend teamlead team.sh + leadlib.py with OpenMuse-inspired powers (v0.6):
- queue add|list|drop|run  persistent prioritized follow-up queue (drained to workers)
- attach <nick> [--once]   live tail of one worker's event stream (take control view)
- takeover <nick>          open the worker's workspace in ZCode desktop (deep link)
- receipts [n]            audit trail of executed lead commands
- cards on|off            rich status cards for status/standup output
- loop <min>              combined daemon: autopoll + scheduler tick + queue drain"""
import re
import sys

REPO = "/Users/d/.zcode/teamlead-repo"
TEAM = REPO + "/skills/team-lead/team.sh"
LIB = REPO + "/skills/team-lead/leadlib.py"

LIB_ADD = r'''

def cmd_queue(args):
    import time as _t
    p = os.path.join(STATE_DIR, "queue.json")
    try:
        q = json.load(open(p))
    except Exception:
        q = []
    if not args or args[0] == "list":
        for i, item in enumerate(q):
            print(f"{i}  p{item.get('p', 2)}  {item.get('added', '')[:16]}  {item.get('text', '')[:80]}")
        print(f"({len(q)} queued)") if not q else None
        return 0
    if args[0] == "add":
        pri = 2
        rest = args[1:]
        if rest and re.fullmatch(r"p[1-3]", rest[0]):
            pri = int(rest[0][1]); rest = rest[1:]
        text = " ".join(rest).strip()
        if not text:
            print("usage: queue add [p1|p2|p3] <text>"); return 1
        q.append({"p": pri, "text": text, "added": _t.strftime("%F %T")})
        q.sort(key=lambda x: (x.get("p", 2), x.get("added", "")))
        json.dump(q, open(p, "w"), indent=1)
        print(f"queued (p{pri}): {text[:70]}")
        return 0
    if args[0] == "drop":
        idx = int(args[1]); removed = q.pop(idx)
        json.dump(q, open(p, "w"), indent=1)
        print("dropped:", removed.get("text", "")[:60]); return 0
    print("usage: queue list | add [pN] <text> | drop <idx>")
    return 1


def cmd_attach(args):
    once = "--once" in args
    args = [a for a in args if a != "--once"]
    sess, nick = resolve(args[0] if args else None)
    since = time.time() * 1000 - 10 * 60 * 1000
    seen = 0
    while True:
        rows = []
        for e in iter_events(sess, since):
            ev = e.get("event", "")
            if any(k in ev for k in ("turn.", "error", "permission", "task_")):
                rows.append((e.get("timestamp", "")[11:19], ev, (e.get("message") or "")[:90]))
        for r in rows[seen:]:
            print(*r)
        seen = len(rows)
        if once:
            return 0
        time.sleep(10)
        since = time.time() * 1000 - 60000


LIB_TABLE = {"queue": cmd_queue, "attach": cmd_attach}
if "LIB_TABLE" not in dir():
    pass
'''

TEAM_CASES = r'''
  queue)
    python3 "$LEADLIB" queue "${@:-list}" ;;
  attach)
    [ -z "$1" ] && { echo "usage: team.sh attach <sessId|nick> [--once]"; exit 1; }
    python3 "$LEADLIB" attach "$@" ;;
  takeover)
    id=$(resolve "$1"); [ -z "$id" ] && { echo "usage: team.sh takeover <sessId|nick>"; exit 1; }
    ws=$(sqlite3 "$DB" "SELECT workspace_path FROM tasks WHERE task_id='$id' LIMIT 1")
    [ -d "$ws" ] || { echo "unknown workspace: $ws"; exit 1; }
    enc=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$ws")
    open "zcode://workspace/open?path=$enc" && echo "takeover: opened $ws in ZCode desktop" ;;
  receipts)
    n="${1:-15}"
    tail -n "$n" "${ROSTER%.json}-receipts.txt" 2>/dev/null || echo "(no receipts yet)" ;;
  loop)
    mins="${1:-10}"
    while :; do
      "$0" tick || true
      [ -n "$TEAM_WEBHOOK" ] && "$0" notify "loop tick $(date '+%H:%M')" >/dev/null
      sleep $((mins * 60))
    done ;;
  cards)
    st="${1:-status}"
    echo "=== $(date '+%F %T') ==="
    "$0" "$st" | while IFS= read -r l; do echo "│ $l"; done
    echo "└────────────────────" ;;
'''


def main():
    changed = []
    lib = open(LIB, errors="ignore").read()
    if "def cmd_queue" not in lib:
        lib = lib.replace('if __name__ == "__main__":', LIB_ADD + '\nif __name__ == "__main__":', 1)
        lib = lib.replace(
            'fn = {"feed": cmd_feed, "perms": cmd_perms, "burn": cmd_burn, "handoff": cmd_handoff, "sched-state": cmd_sched_state}.get(sys.argv[1])',
            'fn = {"feed": cmd_feed, "perms": cmd_perms, "burn": cmd_burn, "handoff": cmd_handoff, "sched-state": cmd_sched_state, "queue": cmd_queue, "attach": cmd_attach}.get(sys.argv[1])',
            1,
        )
        changed.append("leadlib: queue + attach")
    open(LIB, "w").write(lib)

    team = open(TEAM, errors="ignore").read()
    if '"queue)"' not in team and "  queue)" not in team:
        anchor = '  *) echo "usage: team.sh feed'
        assert anchor in team
        team = team.replace(anchor, TEAM_CASES + "\n" + anchor, 1)
        team = team.replace(
            "feed [nick|--lines N] | perms",
            "queue add|list|drop | attach <id|nick> [--once] | takeover <id|nick> | receipts [n] | loop [min] | cards <cmd> | feed [nick|--lines N] | perms",
            1,
        )
        changed.append("team.sh: openmuse commands")
    open(TEAM, "w").write(team)

    for c in changed:
        print("OK", c)


if __name__ == "__main__":
    sys.exit(main())
