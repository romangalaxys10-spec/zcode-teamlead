#!/usr/bin/env python3
"""Supervisor patch v13: queue mid-task messages instead of failing.
When a locked group sends a message while the focused task is still running,
sendPrompt rejects with "A prompt is already running for this session" and the
user gets "Task failed: ...". Now:
- G4 ACKs immediately: "Queued - the agent will follow through once the
  current step finishes."
- tT's catch retries sendPrompt every 20s (up to ~30 min); on success the
  user gets "Queued message delivered". Genuine failures still report normally.
Idempotent."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

ACK_OLD = 'H(P.bot,h.actor,P.context.activeTaskId),[]'
ACK_NEW = ('H(P.bot,h.actor,P.context.activeTaskId),'
           'P.context._lock&&await mo(P.context)?[me(h.actor,"\\ud83d\\udce5 Queued \\u2014 the agent will follow through on this once the current step finishes.")]'
           ':[]')

CATCH_OLD = ('u.delete(N),K(N),await le(I,N,"error",{error:ke}),'
             'await en(h,me(P,hn(Ee)?Je:ne(Ve,"taskFailed",{message:Je}))).catch(()=>{})})')
CATCH_NEW = ('if(/already running/i.test(Je)){'
             'let ZC_n=0,ZC_iv=setInterval(async()=>{'
             'if(++ZC_n>90){clearInterval(ZC_iv);try{await en(h,me(P,"\\u23f3 Queued message timed out (30 min) \\u2014 send it again.")).catch(()=>{})}catch{}return}'
             'try{let ZC_s=await ft(I);'
             'await ZC_s.sendPrompt({taskId:N,traceId:R,content:$,attachments:V.length>0?V:void 0,botDeliveryTarget:ce,modelSelection:ge});'
             'clearInterval(ZC_iv);'
             'await en(h,me(P,"\\ud83d\\udcee Queued message delivered \\u2014 the agent picked it up.")).catch(()=>{})'
             '}catch{}},2e4);return}'
             'u.delete(N),K(N),await le(I,N,"error",{error:ke}),'
             'await en(h,me(P,hn(Ee)?Je:ne(Ve,"taskFailed",{message:Je}))).catch(()=>{})})')


def main():
    src = open(HOST, errors="ignore").read()
    if "Queued message delivered" in src:
        print("  already: v13"); return 0
    for name, old, new in [("G4 queue ACK", ACK_OLD, ACK_NEW), ("tT retry queue", CATCH_OLD, CATCH_NEW)]:
        n = src.count(old)
        assert n == 1, f"anchor count={n} for {name}"
        src = src.replace(old, new, 1)
        print(f"OK {name}")
    open(HOST, "w").write(src)
    print("supervisor v13 applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
