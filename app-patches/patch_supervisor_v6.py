#!/usr/bin/env python3
"""Supervisor patch v6: PER-GROUP project/session isolation.
Bot context (workspace/activeTaskId/mode/draft/pending) was persisted under the
bot id only, so every Telegram group of one bot shared a single context.
Now group chats get a scoped state key `botId::g:<chatId>`:
- /project, /task, /new, /stop in group A never touch group B or private chats
- private chats keep the original unscoped key (zero regression)
Idempotent per change (skip when anchor absent)."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

CHANGES = [
    (
        "readContext: scoped key",
        'async function Ce(h,P){await Fn();let N=(await n.readState()).bots[BZ(P)];',
        'async function Ce(h,P){await Fn();let ZC_k=BZ(P)+(h.actor.chatType!=="private"&&h.actor.chatId?"::g:"+h.actor.chatId:""),N=(await n.readState()).bots[ZC_k];',
    ),
    (
        "readContext: tag migrated context with scope",
        'Ee={...N,workspacePath:V.workspacePath,workspaceIdentity:V.workspaceIdentity,workspaceId:ge};',
        'Ee={...N,_k:ZC_k,workspacePath:V.workspacePath,workspaceIdentity:V.workspaceIdentity,workspaceId:ge};',
    ),
    (
        "readContext: tag fresh context with scope",
        'R?{botId:P.id,workspacePath:R.workspacePath,workspaceIdentity:R.workspaceIdentity,workspaceId:R.id,mode:"draft",activeTaskId:null,draftOptions:await He(R),updatedAt:Date.now()}:null',
        'R?{botId:P.id,_k:ZC_k,workspacePath:R.workspacePath,workspaceIdentity:R.workspaceIdentity,workspaceId:R.id,mode:"draft",activeTaskId:null,draftOptions:await He(R),updatedAt:Date.now()}:null',
    ),
    (
        "writeContext: honor scope",
        'async function $e(h){let P=await n.readState();P.bots[h.botId]={...h,updatedAt:Date.now()},await n.writeState(P)}',
        'async function $e(h){let P=await n.readState();P.bots[h._k||h.botId]={...h,updatedAt:Date.now()},await n.writeState(P)}',
    ),
]


def main():
    src = open(HOST, errors="ignore").read()
    applied = 0
    for name, old, new in CHANGES:
        if new in src:
            print(f"  already: {name}")
            continue
        if old not in src:
            print(f"  SKIP (anchor absent): {name}")
            continue
        n = src.count(old)
        assert n == 1, f"anchor count={n} for {name}"
        src = src.replace(old, new, 1)
        applied += 1
        print(f"OK {name}")
    open(HOST, "w").write(src)
    print(f"supervisor v6 applied ({applied} change(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
