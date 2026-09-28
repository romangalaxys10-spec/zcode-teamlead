#!/usr/bin/env python3
"""Supervisor v11: stamp the group scope AT PERSIST TIME.
The callback flow's context can lack `_k` (it bypasses readContext tagging),
so task.set/workspace.set writes fell to the unscoped bot slot -> selection
lost. Stamp `_k` from h.actor directly at both persist sites. Idempotent."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

STAMP = 'let ZC_sk=(h.actor.chatType!=="private"&&h.actor.chatId)?BZ(R.bot)+"::g:"+h.actor.chatId:(R.context._k||R.context.botId);'

CHANGES = [
    (
        "task.set persist stamp",
        'let ce={...R.context,_lock:1,workspacePath:$.workspacePath,',
        STAMP + 'let ce={...R.context,_lock:1,_k:ZC_sk,workspacePath:$.workspacePath,',
    ),
    (
        "workspace.set persist stamp",
        'let ce={...R.context,workspacePath:V.workspacePath,',
        STAMP + 'let ce={...R.context,_k:ZC_sk,workspacePath:V.workspacePath,',
    ),
]


def main():
    src = open(HOST, errors="ignore").read()
    if "ZC_sk" in src:
        print("  already: v11"); return 0
    for name, old, new in CHANGES:
        n = src.count(old)
        if n == 0:
            print(f"  SKIP (absent): {name}"); continue
        assert n == 1, f"anchor count={n} for {name}"
        src = src.replace(old, new, 1)
        print(f"OK {name}")
    open(HOST, "w").write(src)
    print("supervisor v11 applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
