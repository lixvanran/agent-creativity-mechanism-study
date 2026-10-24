# -*- coding: utf-8 -*-
"""从 web_search 的落盘 artifact 里精确取出原句（含真实标点），用于 source.quote。"""
import glob, os, sys

BASE = "/workspace/.mavis/tool-results/454829926822221"
files = sorted(glob.glob(os.path.join(BASE, "*", "chunks", "*.txt")))
blobs = {}
for f in files:
    try:
        blobs[f] = open(f, encoding="utf-8", errors="replace").read()
    except Exception as e:
        print("READ FAIL", f, e)

NEEDLES = sys.argv[1:]
for needle in NEEDLES:
    print("=" * 100)
    print("NEEDLE:", needle)
    hit = 0
    for f, blob in blobs.items():
        idx = blob.find(needle)
        if idx >= 0:
            hit += 1
            s = blob[idx: idx + len(needle) + 120]
            print("  FILE:", os.path.basename(os.path.dirname(os.path.dirname(f))))
            print("  RAW :", repr(s))
    if not hit:
        print("  !! NOT FOUND")
