#!/usr/bin/env python3
"""Supervisor patch v4:
- /queue command: lists RUNNING tasks (count + titles + which is focused)
- spawn notice now names the new task (slug of its first message)
Each change independently idempotent (skip when anchor absent)."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

QUEUE_FN = '''async function ZCODE_queue(h){let P=await Bt(h,"task");if(!P.ok)return P.reply;let ZC=await Fr(P.context,P.user),run=ZC.filter(Ee=>Ee.task&&Ee.task.status==="running");let focused=P.context.activeTaskId||"";if(run.length===0)return[me(h.actor,ne(P.locale,"noHistoryTasks"))];let lines=run.map(Ee=>(Ee.task.taskId===focused?"\\u25b6 ":"  ")+(Ee.task.title||Ee.task.taskId));return[me(h.actor,"Queue ("+run.length+" running):\\n"+lines.join("\\n"))]}
'''

CHANGES = [
    (
        "queue command parser",
        'case"reply":case"\\u56DE\\u590D":',
        'case"queue":return{type:"queue.list"};case"reply":case"\\u56DE\\u590D":',
    ),
    (
        "queue dispatch case",
        'case"task.list":return V4(h);',
        'case"task.list":return V4(h);case"queue.list":return ZCODE_queue(h);',
    ),
    (
        "queue handler injected",
        'i(V4,"handleTaskList");',
        'i(V4,"handleTaskList");' + QUEUE_FN,
    ),
    (
        "menu dy queue",
        'dy=["help","task",...Zae,"bind"]',
        'dy=["help","task","queue",...Zae,"bind"]',
    ),
    (
        "menu Gae queue",
        'Gae={bind:"bind",task:"task",help:"help",',
        'Gae={bind:"bind",task:"task",queue:"queue",help:"help",',
    ),
    (
        "menu qae queue",
        'qae={bind:"Bind this chat",task:"Select task/session",help:"Show help",',
        'qae={bind:"Bind this chat",task:"Select task/session",queue:"Show running tasks",help:"Show help",',
    ),
    (
        "spawn notice names the new task",
        'text:"\\ud83e\\uddf5 New parallel task started \\u2014 the previous one keeps running. /tasks to switch focus, /stop stops the focused task."',
        'text:"\\ud83e\\uddf5 New parallel task: "+String(h.text||"").split(/\\s+/u).join(" ").trim().slice(0,48)+" \\u2014 previous one keeps running. /task to switch, /queue for the list."',
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
    print(f"supervisor v4 applied ({applied} change(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
