#!/bin/bash
# patch-watch.sh — detect ZCode app updates and re-apply the local patch fleet.
# Compares the sha256 of app.asar against the last-seen hash; on change runs
# reapply_all.sh (backup->extract->patch->check->repack->verify->install).
set -u
ASAR="${ZCODE_APP_ASAR:-/Applications/ZCode.app/Contents/Resources/app.asar}"
STATE="$HOME/.zcode/patch-watch.sha"
LOG="$HOME/.zcode/patch-watch.log"
SCRIPT="$HOME/.zcode/scripts/reapply_all.sh"
LOCK="$HOME/.zcode/.patch-watch.lock"

log(){ echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }
mkdir -p "$LOCK" 2>/dev/null || exit 0
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

[ -f "$SCRIPT" ] || { log "reapply_all.sh missing"; exit 1; }
[ -f "$ASAR" ] || { log "asar missing"; exit 1; }

NEW=$(shasum -a 256 "$ASAR" | awk '{print $1}')
OLD=$(cat "$STATE" 2>/dev/null || echo "")
if [ -z "$OLD" ]; then
  echo "$NEW" > "$STATE"; log "baseline recorded"; exit 0
fi
if [ "$NEW" = "$OLD" ]; then exit 0; fi

log "app.asar changed — re-applying patch fleet"
sleep 30
if bash "$SCRIPT" --yes >> "$LOG" 2>&1; then
  shasum -a 256 "$ASAR" | awk '{print $1}' > "$STATE"
  log "re-applied OK; new hash recorded. Restart ZCode to load."
else
  log "REAPPLY FAILED — restore manually from app.asar.bak-autoreapply and investigate"
fi
