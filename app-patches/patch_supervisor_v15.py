#!/usr/bin/env python3
"""Supervisor v15: tag the context on Ce's early-return path.
When the stored group context fails workspace validation (Nt -> null),
readContext returned the RAW slot object without the `_k` scope tag — so
persisted selections wrote to the unscoped bot slot and locks vanished.
Now the early-return carries the tag. Idempotent."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"
OLD = "if(!V)return N;"
NEW = "if(!V)return{...N,_k:ZC_k};"


def main():
    src = open(HOST, errors="ignore").read()
    if NEW in src:
        print("  already: v15"); return 0
    n = src.count(OLD)
    assert n == 1, f"anchor count={n}"
    src = src.replace(OLD, NEW, 1)
    open(HOST, "w").write(src)
    print("OK early-return tagged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
