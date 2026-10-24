#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""杀掉残留的 probe_arch2 进程（模式写在文件里，避免 pkill 自匹配）。"""
import os, subprocess, sys, time
PAT = "probe_arch2.py"
me = os.getpid()
def find():
    out = subprocess.run(["pgrep", "-f", PAT], capture_output=True, text=True)
    return [int(p) for p in (out.stdout or "").split() if p.isdigit() and int(p) != me]
if __name__ == "__main__":
    pids = find()
    print("found:", pids)
    for p in pids:
        try:
            os.kill(p, 9); print("  killed", p)
        except Exception as e:
            print("  skip", p, e)
    time.sleep(1); print("remaining:", find())
