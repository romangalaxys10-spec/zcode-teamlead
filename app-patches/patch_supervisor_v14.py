#!/usr/bin/env python3
"""Supervisor v14: draft-path stale model fallback.
G4's DRAFT path threw "Bot cannot resolve Submission model" when the context's
saved draft modelSelection was stale/unavailable. Now it retries resolution
without the saved pick (host-preferred model) before giving up.
Also covers the same throw pattern anywhere it appears. Idempotent."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

OLD = 'if(!Je||ke.modelSelection&&Ve?.selectionIssue)throw new Error("Bot \\u65E0\\u6CD5\\u4ECE\\u76EE\\u6807 Host \\u89E3\\u6790 Submission \\u6A21\\u578B");'
NEW = ('if(!Je||ke.modelSelection&&Ve?.selectionIssue){let ZC_v2=await de(P.context,void 0);'
       'Je=ZC_v2?.effectiveSelection;Ve=ZC_v2;'
       'if(!Je)throw new Error("Bot \\u65E0\\u4ECE\\u76EE\\u6807 Host \\u89E3\\u6790 Submission \\u6A21\\u578B")}')


def main():
    src = open(HOST, errors="ignore").read()
    if "ZC_v2" in src:
        print("  already: v14"); return 0
    n = src.count(OLD)
    assert n == 1, f"anchor count={n}"
    src = src.replace(OLD, NEW, 1)
    open(HOST, "w").write(src)
    print("OK draft-path stale model falls back to host-preferred")
    return 0


if __name__ == "__main__":
    sys.exit(main())
