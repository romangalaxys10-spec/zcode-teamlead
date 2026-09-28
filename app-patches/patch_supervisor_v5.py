#!/usr/bin/env python3
"""Supervisor patch v5: working heartbeat.
Starts the runtime's native typing indicator (H = startTyping, 4s interval)
when a bot task is SUBMITTED — previously it only started after permission or
elicitation resolution, so Telegram/Discord sat silent during long tool runs.
Stop is native (K/stopTyping on turn completion). Independently idempotent."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

OLD = 'tT(P.bot,h.actor,P.context,P.context.activeTaskId,Ee,R.content,R.zcodeAttachments,kH(h.actor),ge),[]'
NEW = 'tT(P.bot,h.actor,P.context,P.context.activeTaskId,Ee,R.content,R.zcodeAttachments,kH(h.actor),ge),H(P.bot,h.actor,P.context.activeTaskId),[]'


def main():
    src = open(HOST, errors="ignore").read()
    if OLD not in src:
        if NEW in src:
            print("  already: heartbeat on submit")
            return 0
        print("anchor missing — aborting"); return 1
    assert src.count(OLD) == 1
    src = src.replace(OLD, NEW, 1)
    open(HOST, "w").write(src)
    print("OK heartbeat starts at task submit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
