#!/bin/bash
# reapply-patches.sh — re-apply all local ZCode app patches after an app update.
# Pipeline: backup -> extract installed asar -> run each patch script -> syntax
# check -> repack (preserving native unpacked set) -> verify -> install.
# The patch scripts (patch_supervisor.py, patch_groups.py, patch_discord.py)
# operate on the fixed working tree /tmp/zcode-discord/app.
set -e
APP_ASAR="${ZCODE_APP_ASAR:-/Applications/ZCode.app/Contents/Resources/app.asar}"
WORK=/tmp/zcode-discord
SCRIPTS="$HOME/.zcode/scripts"

[ "$(basename "$1")" = "--yes" ] || { echo "this modifies the installed ZCode app; run: $0 --yes"; exit 1; }
command -v node >/dev/null || { echo "node required"; exit 1; }

echo "[1/6] backup"
cp "$APP_ASAR" "$APP_ASAR.bak-autoreapply"

echo "[2/6] extract"
rm -rf "$WORK/app" && mkdir -p "$WORK"
npx --yes @electron/asar extract "$APP_ASAR" "$WORK/app"

echo "[3/6] apply patches"
for p in patch_supervisor.py patch_groups.py patch_discord.py; do
  if [ -f "$SCRIPTS/$p" ]; then
    python3 "$SCRIPTS/$p" || { echo "PATCH FAILED: $p"; exit 1; }
  else
    echo "  (skip missing $p)"
  fi
done

echo "[4/6] syntax check"
cp "$WORK/app/out/host/index.js" /tmp/zlead-hostcheck.mjs
node --check /tmp/zlead-hostcheck.mjs && rm -f /tmp/zlead-hostcheck.mjs

echo "[5/6] repack + verify"
cd "$WORK"
rm -rf app-new.asar app-new.asar.unpacked
npx --yes @electron/asar pack app app-new.asar --unpack "{**/prebuilds/darwin-arm64/**,**/sshcrypto.node}"
npx --yes @electron/asar list app-new.asar | sort > new-list.txt
npx --yes @electron/asar list "$APP_ASAR" | sort > orig-list.txt
diff orig-list.txt new-list.txt || { echo "LIST PARITY FAILED"; exit 1; }
python3 "$SCRIPTS/asar_spotcheck.py" app-new.asar app 12

echo "[6/6] install"
cp app-new.asar "$APP_ASAR"
cp -R app-new.asar.unpacked/ "${APP_ASAR}.unpacked/" 2>/dev/null || cp -R app-new.asar.unpacked/ "${APP_ASAR%.asar}.unpacked/"
echo "DONE — restart ZCode to load. Patch fleet re-applied."
