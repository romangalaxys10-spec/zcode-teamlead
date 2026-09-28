#!/usr/bin/env python3
"""Supervisor patch v3: paginate /task session picker (10 per page).
- page state per chat; 'Next page ->' appears as a selectable option
- '/task 2' jumps to page 2; '__next__' selection advances the page
Independently idempotent per change (skip when anchor absent)."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

VAR = 'var ZCODE_tp=new Map;\n'

V4_OLD = (
    'let I=(await Fr(P.context,P.user)).slice(0,10),N=I.map(V=>V.task),'
    'R=P.context.activeTaskId?N.find(V=>V.taskId===P.context.activeTaskId):null,'
    '$={id:`task-${Date.now()}`,title:ne(P.locale,"taskSelectTitle",{task:R?`${R.title} (${R.taskId})`:"draft"}),'
    'currentId:P.context.activeTaskId??void 0,action:"task.set",'
    'options:I.map(V=>({id:V.task.taskId,label:V.task.title,description:ap(V.task))}))'
)
# NOTE: the original ends with '}))' — build exact string defensively below.
V4_OLD_EXACT = (
    'let I=(await Fr(P.context,P.user)).slice(0,10),N=I.map(V=>V.task),'
    'R=P.context.activeTaskId?N.find(V=>V.taskId===P.context.activeTaskId):null,'
    '$={id:`task-${Date.now()}`,title:ne(P.locale,"taskSelectTitle",{task:R?`${R.title} (${R.taskId})`:"draft"}),'
    'currentId:P.context.activeTaskId??void 0,action:"task.set",'
    'options:I.map(V=>({id:V.task.taskId,label:V.task.title,description:ap(V.task)}))}'
)
V4_NEW = (
    'let ZC_all=await Fr(P.context,P.user),ZC_max=Math.max(0,Math.ceil(ZC_all.length/10)-1),'
    'ZC_pg=Math.min(ZCODE_tp.get(J(h.actor))||0,ZC_max),'
    'I=ZC_all.slice(ZC_pg*10,ZC_pg*10+10),N=I.map(V=>V.task),'
    'R=P.context.activeTaskId?N.find(V=>V.taskId===P.context.activeTaskId):null,'
    '$={id:`task-${Date.now()}`,title:ne(P.locale,"taskSelectTitle",{task:R?`${R.title} (${R.taskId})`:"draft"})+(ZC_max>0?" (page "+(ZC_pg+1)+"/"+(ZC_max+1)+")":""),'
    'currentId:P.context.activeTaskId??void 0,action:"task.set",'
    'options:I.map(V=>({id:V.task.taskId,label:V.task.title,description:ap(V.task)}))'
    '.concat(ZC_pg<ZC_max?[{id:"__next__",label:"Next page",description:"page "+(ZC_pg+2)+" / "+(ZC_max+1)}]:[])}'
)

TS_OLD = 'case"task.set":{let R=await Bt(h,"task");if(!R.ok)return R.reply;let $=await J4(h,R.context,R.user,I.value);'
TS_NEW = (
    'case"task.set":{let R=await Bt(h,"task");if(!R.ok)return R.reply;'
    'if(I.value==="__next__"){ZCODE_tp.set(J(h.actor),(ZCODE_tp.get(J(h.actor))||0)+1);return V4(h)}'
    'if(/^\\d+$/.test(I.value)){ZCODE_tp.set(J(h.actor),Math.max(0,Number(I.value)-1));return V4(h)}'
    'let $=await J4(h,R.context,R.user,I.value);'
)

CHANGES = [
    ("V4 pagination (slice/title/options)", V4_OLD_EXACT, V4_NEW),
    ("task.set page intercept", TS_OLD, TS_NEW),
]


def main():
    src = open(HOST, errors="ignore").read()
    if "ZCODE_tp" in src:
        print("  already: supervisor v3 (pagination)")
        return 0
    applied = 0
    if "function up(e){" in src and "var ZCODE_tp" not in src:
        src = src.replace("function up(e){", VAR + "function up(e){", 1)
        applied += 1
        print("OK page-state var injected")
    for name, old, new in CHANGES:
        if old not in src:
            print(f"  SKIP (anchor absent, possibly already patched): {name}")
            continue
        n = src.count(old)
        assert n == 1, f"anchor count={n} for {name}"
        src = src.replace(old, new, 1)
        applied += 1
        print(f"OK {name}")
    open(HOST, "w").write(src)
    print(f"supervisor v3 applied ({applied} change(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
