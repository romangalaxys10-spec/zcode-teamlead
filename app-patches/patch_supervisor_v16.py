#!/usr/bin/env python3
"""Supervisor v16 (v13b): pin the session's LAST-USED model (from model_usage)
on resume-model-failure, before the group-default fallback. Idempotent."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

OLD = ('if(!ge||ce?.selectionIssue){let ZC_d=P.context.draftOptions??await He(P.context),'
       'ZC_v=await de(P.context,ZC_d.modelSelection);ge=ZC_v?.effectiveSelection;'
       'if(!ge)throw new Error(ne(P.locale,"sessionModelUnavailable"))}')

NEW = ('if(!ge||ce?.selectionIssue){'
       'try{let Q=String.fromCharCode(39),ZC_cp=await import("node:child_process"),'
       'ZC_tid=String(P.context.activeTaskId||"").replace(/[^A-Za-z0-9_-]/g,""),'
       'ZC_out=ZC_cp.execFileSync("/usr/bin/sqlite3",'
       '[process.env.HOME+"/.zcode/cli/db/db.sqlite","SELECT provider_id"+Q+"||"+Q+"model_id FROM model_usage WHERE session_id="+Q+ZC_tid+Q+" AND coalesce(provider_id,"+Q+Q+")!="+Q+Q+" ORDER BY started_at DESC LIMIT 1"],'
       '{encoding:"utf8",timeout:1e4}).trim();'
       'if(ZC_out.includes("|")){let ZC_parts=ZC_out.split("|"),ZC_p=ZC_parts[ZC_parts.length-2],ZC_m=ZC_parts[ZC_parts.length-1],'
       'ZC_r=await de(P.context,{providerId:ZC_p,modelId:ZC_m});ge=ZC_r?.effectiveSelection}}catch{}}'
       'if(!ge||ce?.selectionIssue){let ZC_d=P.context.draftOptions??await He(P.context),'
       'ZC_v=await de(P.context,ZC_d.modelSelection);ge=ZC_v?.effectiveSelection;'
       'if(!ge)throw new Error(ne(P.locale,"sessionModelUnavailable"))}')


def main():
    src = open(HOST, errors="ignore").read()
    if "ZC_cp" in src:
        print("  already: v16"); return 0
    anchor = 'if(!ge||ce?.selectionIssue){let ZC_d=P.context.draftOptions??await He(P.context),ZC_v=await de(P.context,ZC_d.modelSelection);ge=ZC_v?.effectiveSelection;if(!ge)throw new Error(ne(P.locale,"sessionModelUnavailable"))}'
    n = src.count(anchor)
    assert n == 1, f"anchor count={n}"
    src = src.replace(anchor, NEW, 1)
    open(HOST, "w").write(src)
    print("OK v13b last-used model pinning applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
