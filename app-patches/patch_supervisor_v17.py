#!/usr/bin/env python3
"""Supervisor v17: private-chat recovery — picker instead of poison.
Bug: the private chat's context had a stale draft (dead model pick from the
pre-fix era); the G4 draft path threw the Chinese model error on EVERY message,
even /project, because the poisoned draftOptions were carried through v14's
retry (same context object).
Fix: on model-resolution failure in the draft path:
  1. reset to a FRESH clean draft (qt) and retry resolution once
  2. if still failing, return the native project picker (fo workspace.set)
     so the user selects existing project — no error loop.
Idempotent."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

OLD = ('if(!Je||ke.modelSelection&&Ve?.selectionIssue){let ZC_v2=await de(P.context,void 0);'
       'Je=ZC_v2?.effectiveSelection;Ve=ZC_v2;'
       'if(!Je)throw new Error("Bot \\u65E0\\u4ECE\\u76EE\\u6807 Host \\u89E3\\u6790 Submission \\u6A21\\u578B")}')

NEW = ('if(!Je||ke.modelSelection&&Ve?.selectionIssue){'
       'P.context=await qt(P.context,await ct(P.context));'
       'try{let ZC_k3=P.context.draftOptions??await He(P.context),ZC_w3=await de(P.context,ZC_k3.modelSelection);'
       'Je=ZC_w3?.effectiveSelection;Ve=ZC_w3;ke=ZC_k3}catch(e3){Je=null}'
       'if(!Je||ke.modelSelection&&Ve?.selectionIssue){'
       'let ZC_cfg=await n.readConfig(),ZC_list=await hr(ZC_cfg,P.bot,Bo(P.context)),'
       'ZC_opts=(await sp(ZC_list,P.user.allowedWorkspaces)).map(ZC_w=>({id:ZC_w.id,label:yI(ZC_w.workspacePath)}));'
       'if(ZC_opts.length===0)throw new Error(ne(P.locale,"sessionModelUnavailable"));'
       'return fo(h.actor,{id:"workspace-"+Date.now(),'
       'title:ne(P.locale,"workspaceSelectTitle",{workspace:""}),currentId:void 0,'
       'action:"workspace.set",options:ZC_opts},P.locale)}}')


def main():
    src = open(HOST, errors="ignore").read()
    if "ZC_k3" in src:
        print("  already: v17"); return 0
    n = src.count(OLD)
    assert n == 1, f"anchor count={n}"
    src = src.replace(OLD, NEW, 1)
    open(HOST, "w").write(src)
    print("OK draft failure -> fresh draft retry -> project picker")
    return 0


if __name__ == "__main__":
    sys.exit(main())
