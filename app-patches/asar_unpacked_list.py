#!/usr/bin/env python3
"""List entries marked unpacked:true in an asar header."""
import json
import struct
import sys

path = sys.argv[1]
with open(path, "rb") as f:
    f.seek(4)
    hsize = struct.unpack("<I", f.read(4))[0]
    f.seek(16)
    header = json.loads(f.read(hsize - 8).rstrip(b"\0"))


def walk(node, prefix, out):
    for name, child in node.get("files", {}).items():
        p = prefix + "/" + name
        if "files" in child:
            walk(child, p, out)
        elif child.get("unpacked"):
            out.append(p)


out = []
walk(header, "", out)
print(len(out), "unpacked entries")
for p in out:
    print(p)
