#!/usr/bin/env python3
"""Supervisor v18: private-chat onboarding picker.
First message from a private chat (no prior interaction with this bot) no
longer lands in a random project. Instead the bot presents a selection:
  ➕ New project & task (native /new flow)
  📌 existing tasks across allowed workspaces (task.set switches + locks via v7)
Groups are untouched (gate is private-only). Idempotent."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

A1_OLD = 'var ZC_dbg='
A1_NEW = 'var ZCODE_seen=new Map;\nvar ZC_dbg='

A2_OLD = 'if(N)return N;ZC_dbg({at:"G4-gate"'
A2_NEW = ('if(h.actor.chatType==="private"&&P.context.mode==="draft"&&!P.context.activeTaskId'
          '&&!ZCODE_seen.has(J(h.actor))){'
          'ZCODE_seen.set(J(h.actor),1);'
          'let ZC_list=await Fr(P.context,P.user),ZC_opts=[{id:"__new__",label:"\\u2795 New project & task"}]'
          '.concat(ZC_list.slice(0,9).map(ZC_e=>({id:ZC_e.task.taskId,'
          'label:"\\ud83d\\udccd "+(ZC_e.task.title||ZC_e.task.taskId).slice(0,50),'
          'description:(ZC_e.workspacePath||"").split("/").pop()})));'
          'if(ZC_list.length===0)ZC_opts=[{id:"__new__",label:"\\u2795 New project & task"}];'
          'return fo(h.actor,{id:"onboard-"+Date.now(),'
          'title:ne(P.locale,"taskSelectTitle",{task:"new"}),currentId:void 0,'
          'action:"task.set",options:ZC_opts},P.locale)}'
          'ZC_dbg({at:"G4-gate"')

A3_OLD = 'if(I.value==="__next__"){ZCODE_tp.set(J(h.actor),(ZCODE_tp.get(J(h.actor))||0)+1);return V4(h)}'
A3_NEW = ('if(I.value==="__next__"){ZCODE_tp.set(J(h.actor),(ZCODE_tp.get(J(h.actor))||0)+1);return V4(h)}'
          'if(I.value==="__new__"){R.context=await qt(R.context,await ct(R.context));'
          'return Xr(h.actor,R.context,R.locale)}')


def main():
    src = open(HOST, errors="ignore").read()
    if "ZCODE_seen" in src:
        print("  already: v18"); return 0
    applied = 0
    for name, old, new in [("seen map", A1_OLD, A1_NEW),
                           ("G4 onboarding picker", A2_OLD, A2_NEW),
                           ("task.set __new__", A3_OLD, A3_NEW)]:
        n = src.count(old)
        assert n == 1, f"anchor count={n} for {name}"
        src = src.replace(old, new, 1)
        applied += 1
        print(f"OK {name}")
    open(HOST, "w").write(src)
    print(f"supervisor v18 applied ({applied} change(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
