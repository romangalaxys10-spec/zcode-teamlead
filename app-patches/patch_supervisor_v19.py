#!/usr/bin/env python3
"""Supervisor v19: /project picker gains "New project" creation.
- workspace picker gains a "+ New project" option
- selecting it asks for a name; the next message becomes the project name
- bot creates ~/Documents/Projects/<name>, switches the chat's context there,
  and the next message starts the first task (sidebar shows the new project)
Idempotent."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

CHANGES = [
    ("newproj state var",
     "var ZCODE_seen=new Map;",
     "var ZCODE_seen=new Map;var ZCODE_newproj=new Map;",),
    ("workspace picker: + New project option",
     'currentId:R.context.workspaceId,action:"workspace.set",options:ce},R.locale)',
     'currentId:R.context.workspaceId,action:"workspace.set",'
     'options:ce.concat([{id:"__newproj__",label:"\\u2795 New project"}])},R.locale)',),
    (
        "workspace.set: arm new-project naming",
        'case"workspace.set":{let R=await Bt(h,"workspace");if(!R.ok)return R.reply;',
        'case"workspace.set":{let R=await Bt(h,"workspace");if(!R.ok)return R.reply;'
        'if(I.value==="__newproj__"){ZCODE_newproj.set(J(h.actor),1);'
        'return[me(h.actor,"\\ud83d\\udcdd Send me the name for the new project (this message is the name).")]}',
    ),
    (
        "G4: consume name, create project, fall through to draft submit",
        'if(h.actor.chatType==="private"&&P.context.mode==="draft"&&!P.context.activeTaskId&&!ZCODE_seen.has(J(h.actor))){',
        'if(ZCODE_newproj.get(J(h.actor))&&h.text){ZCODE_newproj.delete(J(h.actor));'
        'let ZC_name=String(h.text).replace(/[^\\w\\- ]+/g,"").trim().replace(/\\s+/g,"-").slice(0,60);'
        'if(!ZC_name)return[me(h.actor,"invalid project name")];'
        'let ZC_dir=process.env.HOME+"/Documents/Projects/"+ZC_name;'
        'try{ZC_fs.mkdirSync(ZC_dir,{recursive:true})}catch(ZC_e){return[me(h.actor,"mkdir failed: "+ZC_e.message)]}'
        'let ZC_ctx={...P.context,_k:P.context._k||P.context.botId,'
        'workspacePath:ZC_dir,workspaceIdentity:void 0,workspaceId:void 0,'
        'mode:"draft",activeTaskId:null};'
        'try{ZC_ctx.draftOptions=await He(ZC_ctx)}catch{ZC_ctx.draftOptions=void 0}'
        'P.context=ZC_ctx;await $e(P.context);'
        'return[me(h.actor,"\\u2705 New project created: "+ZC_name+" \\u2014 send your first message and it becomes the first task.")]}'
        'if(N)return N;if(h.actor.chatType==="private"&&P.context.mode==="draft"&&!ZCODE_seen.has(J(h.actor))){',
    ),
]


def main():
    src = open(HOST, errors="ignore").read()
    if "ZCODE_newproj" in src:
        print("  already: v19"); return 0
    for name, old, new in CHANGES:
        n = src.count(old)
        assert n == 1, f"anchor count={n} for {name}"
        src = src.replace(old, new, 1)
        print(f"OK {name}")
    open(HOST, "w").write(src)
    print("supervisor v19 applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
