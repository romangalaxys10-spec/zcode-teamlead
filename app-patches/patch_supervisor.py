#!/usr/bin/env python3
"""Patch ZCode bot runtime into SUPERVISOR MODE (idempotent):
- busy + plain message  -> spawn a fresh parallel session and submit there
                           (instead of refusing with "task is still running")
- /tasks switching      -> allowed while other tasks run
- /new while busy       -> allowed
Telegram bot becomes a nano-supervisor: every message = a new task,
updates stream per task into the chat; /stop stops the focused task."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

REPLACEMENTS = [
    (
        # G4 handleMessage: busy -> spawn new parallel session, fall through to submit
        'if(P.context.mode==="task"&&P.context.activeTaskId&&await mo(P.context))return[me(h.actor,ne(P.locale,"taskRunning"))];let R;try{R=await Pi(P.bot,h,P.locale)}',
        'if(P.context.mode==="task"&&P.context.activeTaskId&&await mo(P.context)){P.context=await qt(P.context,await ct(P.context));try{const zp=F[h.actor.provider];zp&&zp.send&&await zp.send(P.bot,{providerUserId:h.actor.providerUserId,text:"\\ud83e\\uddf5 New parallel task started \\u2014 the previous one keeps running. /tasks to switch focus, /stop stops the focused task."})}catch{}}let R;try{R=await Pi(P.bot,h,P.locale)}',
    ),
    (
        # task.set: allow switching focus while a task runs
        'if(R.context.activeTaskId!==V.taskId&&await mo(R.context))return[me(h.actor,ne(R.locale,"taskRunning"))];',
        '',
    ),
    (
        # /new: allowed while busy
        'if(await mo(R.context))return[me(h.actor,ne(R.locale,"taskRunning"))];let $=await qt(R.context,await ct(R.context));return Xr',
        'let $=await qt(R.context,await ct(R.context));return Xr',
    ),
]


def main():
    src = open(HOST, errors="ignore").read()
    if "ZCODE_SUPERVISOR_V1" in src:
        print("host: supervisor already patched")
        return 0
    for i, (old, new) in enumerate(REPLACEMENTS, 1):
        n = src.count(old)
        assert n == 1, f"anchor {i} count={n} (expected 1)"
        src = src.replace(old, new, 1)
        print(f"OK replacement {i}")
    src = src.replace("function up(e){", "var ZCODE_SUPERVISOR_V1=1;function up(e){", 1)
    open(HOST, "w").write(src)
    print("supervisor patch applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
