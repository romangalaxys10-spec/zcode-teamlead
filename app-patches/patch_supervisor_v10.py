#!/usr/bin/env python3
"""Supervisor v10: DEBUG INSTRUMENTATION for the group-routing bug.
Adds a debug logger (appends JSON lines to /Users/d/.zcode/team-debug.log) and
instruments: readContext (scoped key + slot hit), task.set (resolution), and
the G4 busy-spawn gate (lock/activeTask/mo decision). Temporary — for tracing
the 'selected task not used' bug. Logs nothing but ids/flags, no content."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

IMPORTS = 'import * as ZC_fs from "node:fs";\n'
LOGGER = '''var ZC_dbg=o=>{try{ZC_fs.appendFileSync("/Users/d/.zcode/team-debug.log",JSON.stringify({...o,t:Date.now()})+"\\n")}catch{}};
'''

CE_OLD = 'async function Ce(h,P){await Fn();let ZC_k=BZ(P)+(h.chatType!=="private"&&h.chatId?"::g:"+h.chatId:""),N=(await n.readState()).bots[ZC_k];'
CE_NEW = ('async function Ce(h,P){await Fn();let ZC_k=BZ(P)+(h.chatType!=="private"&&h.chatId?"::g:"+h.chatId:""),N=(await n.readState()).bots[ZC_k];'
          'ZC_dbg({at:"readContext",key:ZC_k,chatType:h.chatType,hit:!!N,lock:N?N._lock:void 0,task:N?N.activeTaskId:void 0});')

TS_OLD = 'if(I.value==="__next__"){ZCODE_tp.set(J(h.actor),(ZCODE_tp.get(J(h.actor))||0)+1);return V4(h)}'
TS_NEW = ('if(I.value==="__next__"){ZCODE_tp.set(J(h.actor),(ZCODE_tp.get(J(h.actor))||0)+1);return V4(h)}'
          'ZC_dbg({at:"task.set",value:String(I.value).slice(0,50),lockCtx:R.context._k||R.context.botId});')

G4_OLD = 'if(P.context.mode==="task"&&P.context.activeTaskId&&!P.context._lock&&await mo(P.context)){'
G4_NEW = ('ZC_dbg({at:"G4-gate",mode:P.context.mode,activeTaskId:String(P.context.activeTaskId||"").slice(0,26),'
          'lock:!!P.context._lock,key:P.context._k||P.context.botId});'
          'if(P.context.mode==="task"&&P.context.activeTaskId&&!P.context._lock&&await mo(P.context)){')

CHANGES = [
    ("readContext instrumentation", CE_OLD, CE_NEW),
    ("task.set instrumentation", TS_OLD, TS_NEW),
    ("G4 gate instrumentation", G4_OLD, G4_NEW),
]


def main():
    src = open(HOST, errors="ignore").read()
    if "ZC_dbg" in src:
        print("  already instrumented"); return 0
    assert src.startswith("import"), "unexpected file start"
    src = IMPORTS + LOGGER + src
    applied = 0
    for name, old, new in CHANGES:
        if old not in src:
            print(f"  SKIP (anchor absent): {name}"); continue
        n = src.count(old)
        assert n == 1, f"anchor count={n} for {name}"
        src = src.replace(old, new, 1)
        applied += 1
        print(f"OK {name}")
    open(HOST, "w").write(src)
    print(f"instrumentation applied ({applied} change(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
