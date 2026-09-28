#!/bin/bash
# run_tests.sh — headless tests for the team-lead v0.5 additions (T0-T10).
# Read-only against real data; scheduler/roster/gates use temp dirs.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
TEAM="$HERE/../skills/team-lead/team.sh"
PASS=0; FAIL=0

ok(){ echo "PASS $1"; PASS=$((PASS+1)); }
bad(){ echo "FAIL $1 — $2"; FAIL=$((FAIL+1)); }
check(){ # name, condition-result ($? style), evidence
  if [ "$2" = "0" ]; then ok "$1"; else bad "$1" "$3"; fi
}

echo "== T0 syntax =="
sh -n "$TEAM" && ok "T0a team.sh syntax" || bad "T0a" "sh -n"
python3 -m py_compile "$HERE/../skills/team-lead/leadlib.py" && ok "T0b leadlib compiles" || bad "T0b" "py_compile"

echo "== T1 feed =="
OUT=$("$TEAM" feed --lines 3 2>&1); RC=$?
[ $RC -eq 0 ] && [ -n "$OUT" ]; check "T1 feed runs" $? "rc=$RC out=$OUT"

echo "== T2 perms (synthetic) =="
TMPD=$(mktemp -d)
LOGF="$TMPD/zcode-2099-01-01.jsonl"
mkdir -p "$TMPD"
cat > "$LOGF" <<'EOF'
{"timestamp":"2099-01-01T10:00:00.000Z","event":"permission.requested","sessionId":"sess_test123","message":"permission request pending: bash rm -rf"}
EOF
OUT=$(ZCODE_LOG_DIR="$TMPD" ZCODE_TEAM_STATE="$TMPD/state" python3 "$HERE/../skills/team-lead/leadlib.py" perms --minutes 999999)
echo "$OUT" | grep -q "permission" ; check "T2 perms detects synthetic request" $? "$OUT"
rm -rf "$TMPD"

echo "== T3 burn (real db, read-only) =="
OUT=$("$TEAM" burn --days 30 2>&1); RC=$?
echo "$OUT" | grep -q "token burn" && [ $RC -eq 0 ]; check "T3 burn table" $? "$OUT"

echo "== T4 plan/tick scheduler =="
TMPD=$(mktemp -d)
cat > "$TMPD/goals.json" <<'EOF'
{"tasks":[
 {"id":"t1","needs":[],"goal":"scaffold module A","nick":"w1"},
 {"id":"t2","needs":["t1"],"goal":"wire module B to A","nick":"w2"}
]}
EOF
OUT=$(ZCODE_TEAM_STATE="$TMPD/state" "$TEAM" plan "$TMPD/goals.json" 2>&1)
echo "$OUT" | grep -q "plan loaded: 2"; check "T4a plan loads" $? "$OUT"
OUT=$(ZCODE_TEAM_STATE="$TMPD/state" TEAM_DRY_RUN=1 "$TEAM" tick 2>&1)
echo "$OUT" | grep -q "(dry) would order w1: scaffold module A" && echo "$OUT" | grep -q "PAUSED t2"; check "T4b tick respects deps" $? "$OUT"
ZCODE_TEAM_STATE="$TMPD/state" "$TEAM" done t1 >/dev/null
OUT=$(ZCODE_TEAM_STATE="$TMPD/state" TEAM_DRY_RUN=1 "$TEAM" tick 2>&1)
echo "$OUT" | grep -q "would order w2: wire module B to A"; check "T4c done unblocks dependents" $? "$OUT"
rm -rf "$TMPD"

echo "== T5 handoff (real recent session) =="
SID=$(sqlite3 "${ZCODE_SESSION_DB:-$HOME/.zcode/cli/db/db.sqlite}" "SELECT s.id FROM session s JOIN turn_usage t ON t.session_id=s.id ORDER BY t.started_at DESC LIMIT 1")
TMPD=$(mktemp -d)
ZCODE_TEAM_STATE="$TMPD" python3 "$HERE/../skills/team-lead/leadlib.py" handoff "$SID" "$TMPD/pack.md" >/dev/null 2>&1
grep -q "Handoff pack" "$TMPD/pack.md" 2>/dev/null; check "T5 handoff pack" $? "sid=$SID"
rm -rf "$TMPD"

echo "== T6 qa prompt =="
SID=$(sqlite3 "${ZCODE_SESSION_DB:-$HOME/.zcode/cli/db/db.sqlite}" "SELECT id FROM session ORDER BY time_updated DESC LIMIT 1")
OUT=$("$TEAM" qa "$SID" --dry-run 2>&1)
echo "$OUT" | grep -q "ADVERSARIAL QA"; check "T6 qa dry prompt" $? "$OUT"

echo "== T7 register =="
TMPD=$(mktemp -d)
ZCODE_TEAM_ROSTER="$TMPD/roster.json" "$TEAM" register alice caps=algo,rust model=glm >/dev/null
grep -q '"caps"' "$TMPD/roster.json" && grep -q "rust" "$TMPD/roster.json"; check "T7 register caps" $? "$(cat "$TMPD/roster.json" 2>/dev/null)"
rm -rf "$TMPD"

echo "== T8 dispatch dry (real db) =="
TMPD=$(mktemp -d)
SID=$(sqlite3 "${ZCODE_SESSION_DB:-$HOME/.zcode/cli/db/db.sqlite}" "SELECT id FROM session ORDER BY time_updated DESC LIMIT 1")
printf '{"w1":{"sessId":"%s","caps":["algo"]}}' "$SID" > "$TMPD/roster.json"
OUT=$(ZCODE_TEAM_ROSTER="$TMPD/roster.json" "$TEAM" dispatch --dry-run cap:algo fix the flaky test 2>&1)
echo "$OUT" | grep -q "would dispatch to: sess_"; check "T8 dispatch picks worker" $? "$OUT"
rm -rf "$TMPD"

echo "== T9 gates =="
TMPD=$(mktemp -d); mkdir -p "$TMPD/ws"
OUT=$("$TEAM" gate "$TMPD/ws" build pass 2>&1); RC1=$?
OUT2=$("$TEAM" gate "$TMPD/ws" build status 2>&1); RC2=$?
echo "$OUT2" | grep -q '"verdict": "pass"'; check "T9 gate pass/status" $? "rc1=$RC1 out1=$OUT rc2=$RC2 out2=$OUT2"
rm -rf "$TMPD"

echo "== T10 patch fleet status (installed app) =="
OUT=$("$TEAM" patches status 2>&1)
echo "$OUT" | grep -q "patch fleet status"; check "T10 fleet status runs" $? "$OUT"

echo
echo "RESULTS: $PASS passed, $FAIL failed"
[ "$FAIL" = "0" ]
