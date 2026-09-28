#!/usr/bin/env python3
"""Supervisor patch v9: fix /task button taps re-rendering the picker.
Root cause: Telegram selection callbacks decode to "/task <optionIndex>" and
the v3 pagination intercept treated any numeric value as a page jump — so every
button tap re-rendered the list instead of selecting.
Fix: keep ONLY the collision-free "__next__" token for page advancement;
numeric "/task <n>" returns to native semantics (select the Nth task).
Idempotent."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

OLD = ('if(I.value==="__next__"){ZCODE_tp.set(J(h.actor),(ZCODE_tp.get(J(h.actor))||0)+1);return V4(h)}'
       'if(/^\\d+$/.test(I.value)){ZCODE_tp.set(J(h.actor),Math.max(0,Number(I.value)-1));return V4(h)}')
NEW = 'if(I.value==="__next__"){ZCODE_tp.set(J(h.actor),(ZCODE_tp.get(J(h.actor))||0)+1);return V4(h)}'


def main():
    src = open(HOST, errors="ignore").read()
    if OLD not in src:
        if NEW in src and "/^\\d+$/.test(I.value)" not in src:
            print("  already: numeric intercept removed")
            return 0
        print("anchor missing — aborting (tree state unexpected)"); return 1
    src = src.replace(OLD, NEW, 1)
    open(HOST, "w").write(src)
    print("OK numeric page-jump intercept removed; __next__ kept")
    return 0


if __name__ == "__main__":
    sys.exit(main())
