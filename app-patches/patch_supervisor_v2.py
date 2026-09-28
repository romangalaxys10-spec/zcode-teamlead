#!/usr/bin/env python3
"""Supervisor patch v2: expose native task/session selection.
- /task (task.list, V4) refused with "taskRunning" while busy — removed the
  guard so the session picker opens any time (read-only listing anyway).
- Register /task in the Telegram command menu (dy/Gae/qae tables).
Each change is independently idempotent; works on v1-patched or fresh trees."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

CHANGES = [
    (
        "V4 task.list busy-guard removed",
        'async function V4(h){let P=await Bt(h,"task");if(!P.ok)return P.reply;if(await mo(P.context))return[me(h.actor,ne(P.locale,"taskRunning"))];',
        'async function V4(h){let P=await Bt(h,"task");if(!P.ok)return P.reply;',
    ),
    (
        "command menu: task added to dy",
        'dy=["help",...Zae,"bind"]',
        'dy=["help","task",...Zae,"bind"]',
    ),
    (
        "command menu: Gae task entry",
        'Gae={bind:"bind",help:"help",',
        'Gae={bind:"bind",task:"task",help:"help",',
    ),
    (
        "command menu: qae task description",
        'qae={bind:"Bind this chat",help:"Show help",',
        'qae={bind:"Bind this chat",task:"Select task/session",help:"Show help",',
    ),
]


def main():
    src = open(HOST, errors="ignore").read()
    applied = 0
    for name, old, new in CHANGES:
        if old not in src:
            print(f"  already: {name}")
            continue
        n = src.count(old)
        assert n == 1, f"anchor count={n} for {name}"
        src = src.replace(old, new, 1)
        applied += 1
        print(f"OK {name}")
    open(HOST, "w").write(src)
    print(f"supervisor v2 applied ({applied} change(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
