#!/usr/bin/env python3
"""Spot-check: sha256-compare N random packed files in a repacked asar against
the source tree they were packed from. Usage: asar_spotcheck.py <asar> <srcdir> [n]"""
import hashlib
import json
import random
import struct
import sys

ASAR = sys.argv[1]
SRC = sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 12

f = open(ASAR, "rb")
f.seek(4)
hsize = struct.unpack("<I", f.read(4))[0]
f.seek(16)
header = json.loads(f.read(hsize - 8).rstrip(b"\0"))
data_start = 8 + hsize

files = []


def walk(node, prefix):
    for name, child in node.get("files", {}).items():
        p = prefix + "/" + name
        if "files" in child:
            walk(child, p)
        elif "size" in child and not child.get("unpacked"):
            files.append((p, child["offset"], child["size"]))


walk(header, "")
random.seed(42)
sample = random.sample(files, min(N, len(files)))
bad = 0
for path, off, size in sample:
    f.seek(data_start + int(off))
    h1 = hashlib.sha256(f.read(size)).hexdigest()
    h2 = hashlib.sha256(open(SRC + path, "rb").read()).hexdigest()
    if h1 != h2:
        bad += 1
        print("MISMATCH", path)
print(f"{len(sample) - bad}/{len(sample)} spot-checks pass; total packed files={len(files)}")
sys.exit(1 if bad else 0)
