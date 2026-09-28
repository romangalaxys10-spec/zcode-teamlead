#!/bin/bash
# agent-computer.sh — OpenMuse-style agent computer for ZCode workers. UNIVERSAL.
# macOS + Linux. Docker provides Linux container isolation when available;
# macOS falls back to sandbox-exec. Every worker Chrome profile exposes a CDP
# port for browser automation and live mirroring. All events receipted.
set -u
AC="$HOME/.zcode/team-lead/ac"
EXCHANGE="$AC/exchange"
MIRROR="$AC/mirror"
CHROME_CANDIDATES=("${AC_CHROME:-}" google-chrome google-chrome-stable chromium chromium-browser "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
RECEIPTS="${ZCODE_TEAM_ROSTER:-$HOME/.zcode/team-roster.json}"; RECEIPTS="${RECEIPTS%.json}-receipts.txt"
AC_PY=""

receipt(){ echo "[$(date '+%F %T')] AC $*" >> "$RECEIPTS"; }
have(){ command -v "$1" >/dev/null 2>&1; }
find_chrome(){ # prefer a dedicated "Chrome for Testing" binary: never delegates
  # to the user's running Chrome, so CDP ports and profiles stay deterministic
  local pb="$HOME/Library/Caches/ms-playwright"
  for v in "$pb"/chromium-*/chrome-mac-arm64/Google\ Chrome\ for\ Testing.app/Contents/MacOS/Google\ Chrome\ for\ Testing; do
    [ -x "$v" ] && { echo "$v"; return 0; }
  done
  for c in "${CHROME_CANDIDATES[@]}"; do have "$c" && { echo "$c"; return 0; }; done
  [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ] && { echo "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; return 0; }; return 1; }
nick_ok(){ case "$1" in *[!A-Za-z0-9_-]*|"") echo "bad nick (alnum/-/_ only)"; return 1;; esac; }
ws_dir(){ mkdir -p "$AC/profiles/$1" "$AC/mirror/$1"; echo "$AC/profiles/$1"; }
docker_ok(){ have docker && docker info >/dev/null 2>&1; }
cdp_port(){ printf '%d' $((9300 + $(printf '%s' "$1" | cksum | cut -d' ' -f1) % 300)); }
find_py(){ for c in "$HOME/.venvs/rtstt/bin/python" python3 python; do
    command -v "$c" >/dev/null 2>&1 || continue
    "$c" -c "import websockets" >/dev/null 2>&1 && { AC_PY="$c"; return 0; }; done; return 1; }

browser_open(){
  local nick="$1" url="${2:-about:blank}"
  nick_ok "$nick" || return 1
  local prof; prof=$(ws_dir "$nick")
  local chrome; chrome=$(find_chrome) || { echo "no chrome/chromium found"; return 1; }
  local port; port=$(cdp_port "$nick")
  receipt "browser-open $nick $url (cdp:$port)"
  "$chrome" --user-data-dir="$prof" --remote-debugging-port="$port" \
    --no-first-run --no-default-browser-check --restore-last-session "$url" >/dev/null 2>&1 &
  for _ in $(seq 1 30); do
    curl -s -m 1 "http://127.0.0.1:$port/json/version" >/dev/null 2>&1 && { echo "browser[$nick] opened (cdp 127.0.0.1:$port) $url"; return 0; }
    sleep 0.5
  done
  echo "browser[$nick] opened (cdp port not confirmed)"
}
cdp(){
  local nick="$1" action="$2" arg="${3:-}"
  nick_ok "$nick" || return 1
  find_py || { echo "need python3 with websockets"; return 1; }
  local port; port=$(cdp_port "$nick")
  local need=1
  curl -s -m 1 "http://127.0.0.1:$port/json/list" 2>/dev/null | grep -q '"type": "page"' && need=0
  curl -s -m 1 "http://127.0.0.1:$port/json/version" >/dev/null 2>&1 && [ "$need" = "0" ] && need=0 || need=1
  if [ "$need" = "1" ]; then browser_open "$nick" "https://example.com" >/dev/null; sleep 2; fi
  exec "$AC_PY" "$(dirname "$0")/ac_cdp.py" "$port" "$action" "${arg:-}"
}
mirror(){
  local nick="$1" interval="${2:-2}" serve_port="${3:-8766}"
  nick_ok "$nick" || return 1
  local port; port=$(cdp_port "$nick")
  if ! curl -s -m 1 "http://127.0.0.1:$port/json/version" >/dev/null 2>&1; then
    browser_open "$nick" "https://example.com" >/dev/null
  fi
  find_py || { echo "need python3 with websockets"; return 1; }
  local port; port=$(cdp_port "$nick")
  local out="$MIRROR/$nick"; mkdir -p "$out"
  receipt "mirror $nick interval=$interval serve=$serve_port"
  echo "live mirror: http://127.0.0.1:$serve_port  (ctrl-c to stop)"
  exec "$AC_PY" "$(dirname "$0")/ac_mirror.py" "$port" "$interval" "$out" "$serve_port"
}
term_exec(){
  local nick="$1" ws="$2"; shift 2
  local cmd="$*"
  nick_ok "$nick" || return 1
  [ -d "$ws" ] || { echo "no workspace: $ws"; return 1; }
  [ -n "$cmd" ] || { echo "usage: term-exec <nick> <ws> <cmd...>"; return 1; }
  local prof; prof=$(ws_dir "$nick")
  receipt "term-exec $nick [$ws] $cmd"
  if docker_ok; then
    local cname="ac-$nick"
    docker inspect "$cname" >/dev/null 2>&1 || docker run -d --name "$cname" \
      -v "$ws:/work" -w /work "${AC_IMAGE:-alpine:3.20}" sleep infinity >/dev/null || { echo "container start failed"; exit 1; }
    docker exec "$cname" sh -c "$cmd"
  elif have /usr/bin/sandbox-exec; then
    local rules="$prof/sandbox.sb"
    cat > "$rules" <<SBEOF
(version 1)
(deny default)
(allow process* file-read* network* sysctl-read mach-lookup iokit-operation)
(allow file-write* (subpath "$ws") (subpath "/private/tmp") (subpath "$prof"))
SBEOF
    (cd "$ws" && /usr/bin/sandbox-exec -f "$rules" /bin/sh -c "$cmd")
  else
    echo "WARN: no sandbox available, running unsandboxed"
    (cd "$ws" && sh -c "$cmd")
  fi
}
pdfdrop(){
  [ $# -eq 0 ] && { echo "usage: pdfdrop <file...>"; return 1; }
  for f in "$@"; do
    [ -f "$f" ] || { echo "missing: $f"; continue; }
    base="$(basename "${f%.*}")"; out="$EXCHANGE/$base-$(date +%s).pdf"
    case "${f##*.}" in
      pdf) cp "$f" "$out";;
      png|jpg|jpeg|tiff|gif)
        if have sips; then sips -s format pdf "$f" --out "$out" >/dev/null
        elif have convert; then convert "$f" "$out" >/dev/null; fi;;
      *)
        if have libreoffice; then libreoffice --headless --convert-to pdf --outdir "$EXCHANGE" "$f" >/dev/null 2>&1 && mv "$EXCHANGE/$(basename "${f%.*}").pdf" "$out" 2>/dev/null
        elif have cupsfilter; then cupsfilter "$f" > "$out" 2>/dev/null
        elif have textutil; then textutil -convert txt "$f" -output "$f.tmp.txt" >/dev/null 2>&1 && cupsfilter "$f.tmp.txt" > "$out" 2>/dev/null; rm -f "$f.tmp.txt"; fi;;
    esac
    [ -s "$out" ] && echo "dropped: $out" || { echo "FAILED: $f"; rm -f "$out"; }
  done
}
pdflist(){ ls -1t "$EXCHANGE" 2>/dev/null | head "${1:-20}" || echo "(empty)"; }
status(){
  echo "chrome: $(find_chrome >/dev/null 2>&1 && echo yes || echo no)"
  echo "docker (linux containers): $(docker_ok && echo yes || echo no)"
  echo "sandbox: $(have /usr/bin/sandbox-exec && echo sandbox-exec || echo '(host execution on linux)')"
  echo "pdf: cupsfilter=$(have cupsfilter && echo yes || echo no) libreoffice=$(have libreoffice && echo yes || echo no) sips=$(have sips && echo yes || echo no)"
  echo "python-websockets: $(find_py >/dev/null 2>&1 && echo yes || echo no)"
  echo "profiles: $(browser-list | tr '\n' ' ')"
  echo "exchange: $(ls -1 "$EXCHANGE" 2>/dev/null | wc -l | tr -d ' ') pdfs"
}
case "${1:-status}" in
  browser-open) shift; browser_open "$@";;
  browser-takeover) shift; browser_open "$@" "${2:-about:blank}" front 2>/dev/null; have osascript && osascript -e 'tell application "Google Chrome" to activate' 2>/dev/null; have wmctrl && wmctrl -a Chrome 2>/dev/null; true;;
  browser-list) browser_list;;
  cdp) shift; cdp "$@";;
  mirror) shift; mirror "$@";;
  term-exec) shift; term_exec "$@";;
  pdfdrop) shift; pdfdrop "$@";;
  pdflist) shift; pdflist "$@";;
  status) status;;
  *) echo "usage: agent-computer.sh browser-open|browser-takeover|browser-list|cdp <nick> <navigate|text|title|eval|shot> <arg>|mirror <nick> [interval] [port]|term-exec <nick> <ws> <cmd>|pdfdrop <file...>|pdflist|status";;
esac
