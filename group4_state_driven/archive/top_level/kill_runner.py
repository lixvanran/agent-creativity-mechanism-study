#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""杀掉残留的 run_arch_compare 进程。

★ 记忆铁律：kill/detect 逻辑必须**写在脚本文件里**，
  模式只出现在文件内容里，不出现在调用方 cmdline 里 ⇒ 否则会自杀/自匹配。
"""
import os
import subprocess
import sys
import time

PAT = "run_arch_compare.py"
me = os.getpid()


def find():
    out = subprocess.run(["pgrep", "-f", PAT], capture_output=True, text=True)
    pids = []
    for p in (out.stdout or "").split():
        try:
            pid = int(p)
        except ValueError:
            continue
        if pid == me:
            continue
        pids.append(pid)
    return pids


if __name__ == "__main__":
    pids = find()
    print("found:", pids)
    for p in pids:
        try:
            os.kill(p, 9)
            print("  killed", p)
        except Exception as e:
            print("  skip", p, e)
    time.sleep(1)
    print("remaining:", find())
