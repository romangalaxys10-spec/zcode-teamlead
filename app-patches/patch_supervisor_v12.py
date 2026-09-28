#!/usr/bin/env python3
"""Supervisor patch v12: stale session model no longer dead-ends locked sessions.
When a message targets a selected session whose SAVED model selection no longer
resolves (provider changed/removed), the resume path threw sessionModelUnavailable.
Now it falls back to the context's default model (same resolution the draft path
uses). The session's saved selection is untouched (still "preserved"). Idempotent."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

OLD = 'if(!ge||ce?.selectionIssue)throw new Error(ne(P.locale,"sessionModelUnavailable"));'
NEW = ('if(!ge||ce?.selectionIssue){let ZC_d=P.context.draftOptions??await He(P.context),'
       'ZC_v=await de(P.context,ZC_d.modelSelection);ge=ZC_v?.effectiveSelection;'
       'if(!ge)throw new Error(ne(P.locale,"sessionModelUnavailable"))}')


def main():
    src = open(HOST, errors="ignore").read()
    if NEW in src:
        print("  already: model fallback applied"); return 0
    n = src.count(OLD)
    assert n == 1, f"anchor count={n}"
    src = src.replace(OLD, NEW, 1)
    open(HOST, "w").write(src)
    print("OK stale model falls back to context default")
    return 0


if __name__ == "__main__":
    sys.exit(main())
