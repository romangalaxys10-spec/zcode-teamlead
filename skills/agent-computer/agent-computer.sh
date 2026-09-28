#!/bin/bash
# agent-computer.sh — OpenMuse-style "agent computer" for ZCode workers (macOS).
# Each worker gets: a persistent Chrome profile, a sandboxed terminal, and a PDF
# drop/exchange zone. Files: ~/.zcode/team-lead/ac/<nick>/
# subcommands:
#   browser-open <nick> [url]     launch worker's persistent Chrome profile
#   browser-takeover <nick>       same, but brought to front for human control
#   browser-list                  list worker profiles
#   term-exec <nick> <ws> <cmd>   run cmd in a sandbox restricted to ws (receipt logged)
#   pdfdrop <file...>             convert file(s) to PDF into the exchange zone
#   pdflist [nick]                list exchange PDFs
#   status                        environment capabilities
set -u
AC="$HOME/.zcode/team-lead/ac"
EXCHANGE="$AC/exchange"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
RECEIPTS="${ZCODE_TEAM_ROSTER:-$HOME/.zcode/team-roster.json}"; RECEIPTS="${RECEIPTS%.json}-receipts.txt"
mkdir -p "$AC/profiles" "$EXCHANGE"

validate_nick(){ case "$1" in *[!A-Za-z0-9_-]*|"") echo "bad nick (alnum/-/_ only)"; return 1;; esac; }
validate_ws(){ case "$2" in *'"'*|*'<'*|*')'*) echo "bad ws path chars"; return 1;; esac; [ -d "$2" ] || { echo "no workspace: $2"; return 1; }; }
receipt(){ echo "[$(date '+%F %T')] AC $*" >> "$RECEIPTS"; }

browser-open(){
  local nick="$1" url="${2:-about:blank}" front="${3:-1}"
  validate_nick "$nick" || return 1
  local prof="$AC/profiles/$nick"
  mkdir -p "$prof"
  "$CHROME" --user-data-dir="$prof" --no-first-run --no-default-browser-check ${front:+""} "$url" >/dev/null 2>&1 &
  receipt "browser-open $nick $url"
  echo "browser[$nick] opened ($url)"
}
browser-takeover(){
  local nick="$1" url="${2:-}"
  browser-open "$nick" "${url:-about:blank}" 1
  osascript -e 'tell application "Google Chrome" to activate' 2>/dev/null
  echo "takeover: $nick browser is now in the foreground"
}
browser-list(){ ls -1 "$AC/profiles" 2>/dev/null || echo "(none)"; }

term-exec(){
  local nick="$1" ws="$2"; shift 2
  local cmd="$*"
  validate_nick "$nick" || return 1
  validate_ws "$ws" || return 1
  # SEMI-TRUSTED worker shell: file/network access allowed by design (workers need npm/curl).
  # This is process/write isolation, NOT a security boundary against the worker itself.
  [ -n "$cmd" ] || { echo "usage: term-exec <nick> <ws> <cmd...>"; exit 1; }
  local prof="$AC/profiles/$nick"; mkdir -p "$prof"
  local profile_rules="$prof/sandbox.sb"
  cat > "$profile_rules" <<EOF
(version 1)
(deny default)
(allow process* file-read* network* sysctl-read mach-lookup iokit-operation)
(allow file-write* (subpath "$ws") (subpath "/private/tmp") (subpath "$prof"))
EOF
  receipt "term-exec $nick [$ws] $cmd"
  (cd "$ws" && /usr/bin/sandbox-exec -f "$profile_rules" /bin/zsh -c "$cmd")
}
pdfdrop(){
  [ $# -eq 0 ] && { echo "usage: pdfdrop <file...>"; return 1; }
  for f in "$@"; do
    [ -f "$f" ] || { echo "missing: $f"; continue; }
    local base="$(basename "${f%.*}")"; local out="$EXCHANGE/$base-$(date +%s).pdf"
    case "${f##*.}" in
      pdf) cp "$f" "$out";;
      png|jpg|jpeg|tiff|gif) sips -s format pdf "$f" --out "$out" >/dev/null;;
      txt|md|html|rtf|doc|docx) textutil -convert txt "$f" -output "$f.tmp.txt" >/dev/null 2>&1 && cupsfilter "$f.tmp.txt" > "$out" 2>/dev/null; rm -f "$f.tmp.txt";;
      *) cupsfilter "$f" > "$out" >/dev/null 2>&1;;
    esac
    [ -s "$out" ] && echo "dropped: $out" || { echo "FAILED: $f"; rm -f "$out"; }
  done
}
pdflist(){ ls -1t "$EXCHANGE" 2>/dev/null | head "${1:-20}" || echo "(empty)"; }
status(){
  echo "chrome: $([ -x "$CHROME" ] && echo yes || echo no)"
  echo "pdf tools: cupsfilter=$([ -x /usr/sbin/cupsfilter ] && echo yes || echo no) textutil=$(command -v textutil >/dev/null && echo yes || echo no)"
  echo "sandbox-exec: $([ -x /usr/bin/sandbox-exec ] && echo yes || echo no) (note: macOS shell isolation, NOT a Linux container)"
  echo "profiles: $(browser-list | tr '\n' ' ')"
  echo "exchange: $(ls -1 "$EXCHANGE" 2>/dev/null | wc -l | tr -d ' ') pdfs"
}
case "${1:-status}" in
  browser-open) shift; browser-open "$@";;
  browser-takeover) shift; browser-takeover "$@";;
  browser-list) browser-list;;
  term-exec) shift; term-exec "$@";;
  pdfdrop) shift; pdfdrop "$@";;
  pdflist) shift; pdflist "$@";;
  status) status;;
  *) echo "usage: agent-computer.sh browser-open|browser-takeover|browser-list|term-exec|pdfdrop|pdflist|status ...";;
esac
