#!/usr/bin/env python3
"""Supervisor patch v8: group callback queries share the group actor identity.
Bug: /task listed tasks (message actor: providerUserId = chat id), but tapping
an inline button produced a callback actor with providerUserId = user id
(tce was not groups-aware) -> pending-selection key mismatch -> the picker
re-rendered instead of confirming the selection.
Fix: tce mirrors Yae — in group chats providerUserId = chat id, private chats
keep the user id. Idempotent."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

OLD = 'providerUserId:c,displayName:'
NEW = 'providerUserId:o?.type!=="private"&&o&&(typeof o.id=="number"||typeof o.id=="string")?String(o.id):c,displayName:'


def main():
    src = open(HOST, errors="ignore").read()
    if NEW in src:
        print("  already: callback actor uses chat id in groups")
        return 0
    n = src.count(OLD)
    assert n == 1, f"anchor count={n}"
    src = src.replace(OLD, NEW, 1)
    open(HOST, "w").write(src)
    print("OK tce callback actor mirrors group identity")
    return 0


if __name__ == "__main__":
    sys.exit(main())
