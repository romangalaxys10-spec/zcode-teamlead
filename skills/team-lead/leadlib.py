#!/usr/bin/env python3
"""leadlib.py — team-lead intelligence engine (v0.5).

Subcommands (called by team.sh):
  feed [--lines N] [--json] [nick|sessId]     live event tap from host jsonl logs
  perms [--minutes M] [--json]                pending/stalled permission surfacing
  burn [--days D] [--json] [nick|sessId]      token/cost telemetry from turn_usage
  handoff <nick|sessId> [outfile.md]          context handoff pack for a fresh session
  sched-state                                 print scheduler state json
Returns exit 0 unless a real error. All state under ~/.zcode/team-lead/ unless overridden.
"""
import glob
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta

HOME = os.path.expanduser("~")
DB = os.environ.get("ZCODE_TASKS_DB", f"{HOME}/.zcode/v2/tasks-index.sqlite")
SESSION_DB = os.environ.get("ZCODE_SESSION_DB", f"{HOME}/.zcode/cli/db/db.sqlite")
LOG_DIR = os.environ.get("ZCODE_LOG_DIR", f"{HOME}/.zcode/cli/log")
ROSTER = os.environ.get("ZCODE_TEAM_ROSTER", f"{HOME}/.zcode/team-roster.json")
STATE_DIR = os.environ.get("ZCODE_TEAM_STATE", f"{HOME}/.zcode/team-lead")


def roster():
    try:
        return json.load(open(ROSTER))
    except Exception:
        return {}


def resolve(arg):
    """nickname or sess_ id -> (sessId, nick)"""
    if not arg:
        return None, None
    if arg.startswith("sess_"):
        for nick, v in roster().items():
            if v.get("sessId") == arg:
                return arg, nick
        return arg, None
    v = roster().get(arg)
    return (v or {}).get("sessId"), (arg if v else None)


def log_files():
    files = sorted(glob.glob(f"{LOG_DIR}/zcode-*.jsonl"))
    return files[-2:] if len(files) > 2 else files


def iter_events(sess_id=None, since_ms=0):
    """yield parsed event dicts, newest last, optionally filtered"""
    for path in log_files():
        try:
            with open(path, errors="ignore") as f:
                for line in f:
                    if sess_id and sess_id not in line:
                        continue
                    try:
                        e = json.loads(line)
                    except Exception:
                        continue
                    ts = e.get("timestamp")
                    if ts:
                        try:
                            t = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000
                        except Exception:
                            continue
                        if t < since_ms:
                            continue
                    yield e
        except FileNotFoundError:
            continue


def cmd_feed(args):
    n = 10
    json_out = False
    target = None
    i = 0
    while i < len(args):
        if args[i] == "--lines":
            i += 1; n = int(args[i])
        elif args[i] == "--json":
            json_out = True
        else:
            target = args[i]
        i += 1
    sess, nick = resolve(target)
    since = time.time() * 1000 - 48 * 3600 * 1000
    interesting = ("turn.", "permission", "session.event.persistence", "error", "task_")
    out = []
    for e in iter_events(sess, since):
        ev = e.get("event", "")
        if not any(k in ev for k in interesting):
            continue
        out.append({
            "time": e.get("timestamp", "")[11:19],
            "session": (e.get("sessionId") or "")[:20],
            "nick": nick or "",
            "event": ev,
            "message": (e.get("message") or "")[:90],
        })
    out = out[-n:]
    if json_out:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    if not out:
        print(f"(no events in last 48h for {target or 'team'})")
        return 0
    for o in out:
        who = f" {o['nick']}" if o["nick"] else ""
        print(f"{o['time']}{who}  {o['event']:<38} {o['message']}")
    return 0


def cmd_perms(args):
    minutes = 30
    json_out = False
    i = 0
    while i < len(args):
        if args[i] == "--minutes":
            i += 1; minutes = int(args[i])
        elif args[i] == "--json":
            json_out = True
        i += 1
    since = time.time() * 1000 - minutes * 60 * 1000
    hits = {}
    for e in iter_events(None, since):
        ev = (e.get("event") or "") + " " + (e.get("message") or "")
        if re.search(r"permission", ev, re.I) and re.search(r"request|pending|await|ask", ev, re.I):
            sid = (e.get("sessionId") or "?")[:24]
            hits.setdefault(sid, []).append({"time": e.get("timestamp", "")[11:19], "event": e.get("event"), "message": (e.get("message") or "")[:120]})
    out = []
    for sid, evs in hits.items():
        nick = next((k for k, v in roster().items() if v.get("sessId", "").startswith(sid)), "")
        out.append({"session": sid, "nick": nick, "events": evs[-3:]})
    if json_out:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    if not out:
        print(f"(no permission activity in last {minutes}m — workers unblocked)")
        return 0
    print(f"⚠ permission activity (last {minutes}m):")
    for o in out:
        who = o["nick"] or o["session"]
        for e in o["events"]:
            print(f"  {who}: {e['time']} {e['event']} — {e['message']}")
    return 0


def cmd_burn(args):
    days = 7
    json_out = False
    target = None
    i = 0
    while i < len(args):
        if args[i] == "--days":
            i += 1; days = int(args[i])
        elif args[i] == "--json":
            json_out = True
        else:
            target = args[i]
        i += 1
    sess, nick = resolve(target)
    since = time.time() * 1000 - days * 86400 * 1000
    con = sqlite3.connect(SESSION_DB)
    con.row_factory = sqlite3.Row
    q = """SELECT s.id, substr(coalesce(s.title,'(untitled)'),1,32) title,
                  count(*) turns,
                  sum(CASE WHEN t.status='running' THEN 1 ELSE 0 END) running,
                  coalesce(sum(t.input_tokens),0) in_tok,
                  coalesce(sum(t.output_tokens),0) out_tok,
                  coalesce(sum(t.reasoning_tokens),0) reason_tok,
                  coalesce(sum(t.duration_ms),0) ms,
                  max(t.started_at) last
           FROM turn_usage t JOIN session s ON s.id=t.session_id
           WHERE t.started_at >= ? {}
           GROUP BY s.id ORDER BY in_tok DESC"""
    q = q.format("AND t.session_id=?" if sess else "")
    rows = con.execute(q, (since, sess) if sess else (since,)).fetchall()
    budget = int(os.environ.get("TEAM_BUDGET_TOKENS", "0") or 0)
    out = []
    total_in = total_out = 0
    for r in rows:
        total_in += r["in_tok"]; total_out += r["out_tok"]
        out.append(dict(r))
    if json_out:
        print(json.dumps({"days": days, "budget": budget, "total_in": total_in, "total_out": total_out, "sessions": out}, indent=1))
        return 0
    hdr = f"{'session':<34} {'turns':>5} {'run':>3} {'in':>12} {'out':>10} {'hours':>6}"
    print(f"=== token burn, last {days}d ===\n{hdr}")
    for r in out:
        print(f"{r['id'][:32]:<34} {r['turns']:>5} {r['running']:>3} {r['in_tok']:>12,} {r['out_tok']:>10,} {r['ms']/3600000:>6.1f}")
    print(f"{'TOTAL':<34} {'':>5} {'':>3} {total_in:>12,} {total_out:>10,}")
    if budget and total_in + total_out > budget:
        print(f"⚠ BUDGET EXCEEDED: {total_in + total_out:,} > {budget:,} (TEAM_BUDGET_TOKENS)")
    return 0


def cmd_handoff(args):
    if not args:
        print("usage: handoff <nick|sessId> [outfile.md]"); return 1
    sess, nick = resolve(args[0])
    if not sess:
        print("unknown session"); return 1
    out = args[1] if len(args) > 1 else f"{STATE_DIR}/handoff-{(nick or sess)[:24]}.md"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    con = sqlite3.connect(SESSION_DB)
    row = con.execute("SELECT title, directory, datetime(time_created/1000,'unixepoch'), datetime(time_updated/1000,'unixepoch') FROM session WHERE id=?", (sess,)).fetchone()
    tu = con.execute("""SELECT count(*), coalesce(sum(input_tokens),0), coalesce(sum(output_tokens),0)
                        FROM turn_usage WHERE session_id=?""", (sess,)).fetchone()
    ws = None
    try:
        con2 = sqlite3.connect(DB)
        ws = con2.execute("SELECT workspace_path FROM tasks WHERE task_id=?", (sess,)).fetchone()
        ws = ws[0] if ws else None
    except Exception:
        pass
    events = []
    for e in iter_events(sess, time.time() * 1000 - 7 * 86400 * 1000):
        if any(k in (e.get("event") or "") for k in ("turn.completed", "turn.failed", "error")):
            events.append(f"- {e.get('timestamp','')[5:19]} {e.get('event')}: {(e.get('message') or '')[:100]}")
    lines = [
        f"# Handoff pack — {nick or sess}",
        f"- session: `{sess}`",
        f"- title: {row[0] if row else '?'} | workspace: `{ws or '?'}`",
        f"- active: {row[2] if row else '?'} → {row[3] if row else '?'}",
        f"- turns: {tu[0]} | tokens in/out: {tu[1]:,}/{tu[2]:,}",
        "",
        "## Recent milestones",
        *(events[-15:] or ["- (none)"]),
        "",
        "## Instructions to successor",
        "You are taking over this task. Read the workspace, verify current state with `proof`-style",
        "checks (git log, dirty files), and continue from the last milestone above. Do not redo",
        "completed work; first action should be a short status reply.",
    ]
    open(out, "w").write("\n".join(lines) + "\n")
    print(f"handoff pack written: {out}")
    return 0


def cmd_sched_state(args):
    p = f"{STATE_DIR}/scheduler.json"
    try:
        print(open(p).read())
    except FileNotFoundError:
        print("{}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    os.makedirs(STATE_DIR, exist_ok=True)
    fn = {"feed": cmd_feed, "perms": cmd_perms, "burn": cmd_burn, "handoff": cmd_handoff, "sched-state": cmd_sched_state}.get(sys.argv[1])
    if not fn:
        print(f"unknown: {sys.argv[1]}"); sys.exit(1)
    sys.exit(fn(sys.argv[2:]))
