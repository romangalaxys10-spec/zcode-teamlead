#!/usr/bin/env python3
"""Supervisor patch v7: explicit task FOCUS (lock).
Bug: selecting a session via /task didn't stick — the supervisor busy-spawn
opened a NEW session on the next message instead of routing into the focused one.
Fix:
- /task selection stamps the persisted context with _lock:1
- G4 busy-spawn skips locked contexts -> messages submit INTO the focused task
- /new clears the lock (fresh start)
Private chats and un-locked groups keep parallel-spawn behavior. Idempotent."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

CHANGES = [
    (
        "task.set stamps focus lock",
        'let ce={...R.context,workspacePath:$.workspacePath,',
        'let ce={...R.context,_lock:1,workspacePath:$.workspacePath,',
    ),
    (
        "G4 busy-spawn respects focus lock",
        'if(P.context.mode==="task"&&P.context.activeTaskId&&await mo(P.context)){P.context=await qt(P.context,await ct(P.context));',
        'if(P.context.mode==="task"&&P.context.activeTaskId&&!P.context._lock&&await mo(P.context)){P.context=await qt(P.context,await ct(P.context));',
    ),
    (
        "/new clears focus lock",
        'pendingPermissionOptions:void 0,pendingElicitation:void 0};return se(h.botId),await $e(I),I}',
        'pendingPermissionOptions:void 0,pendingElicitation:void 0,_lock:void 0};return se(h.botId),await $e(I),I}',
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
    print(f"supervisor v7 applied ({applied} change(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
