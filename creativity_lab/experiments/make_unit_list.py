#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 冻结一份「已落盘单元清单」：★ 让所有分析脚本读【同一份】单元集 ★

> 落点：`creativity_lab/experiments/make_unit_list.py`
> 用法：
>   python3 -B creativity_lab/experiments/make_unit_list.py \
>       --run-dir runs/topo-arm-v2-2026-10-24 --tag n150
>
> ★ **为什么需要它（★ 一条被实测逼出来的纪律 ★）** ★
★ 批在跑时，★ 每个分析脚本各自 `glob(units/*.json)` ⇒ ★ 各自看到的单元集是
★ **不同时刻**的 ⇒ ★ 两个脚本的 n 可能差 1–2 ⇒ ★ 派生读数对不上 ⇒ ★
★ ★ 实测踩到过：★ `partial_verdict` 报 n=148、★ `h0_theta0` 报 n=149 ⇒ ★
★ ★ 而「H0 配对 n」两边都是 12 ⇒ ★ **只查 n_pairs 的断言抓不到这个错** ★ ⇒ ⇒
★ ⇒ ★ **必须让两个脚本读同一份清单，★ n 才是结构性一致而不是靠运气 ★**
★ ⇒ ★ 且清单本身要能进交付包（★ 它是「这版读数基于哪些单元」的可复核依据 ★）

★ 输出：`runs/<run-dir>/UNITS-<tag>.txt`（★ 每行一个 basename，★ 不含 .json ★）
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import os
import re
import sys

PAT = re.compile(r"(\S+)_r(\d+)_(\S+)_u(\d+)$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()

    unit_dir = os.path.join(a.run_dir, "units")
    if not os.path.isdir(unit_dir):
        print("✘ units 目录不存在：%s" % unit_dir)
        return 2
    names = []
    skipped = []
    for f in sorted(glob.glob(os.path.join(unit_dir, "*.json"))):
        b = os.path.basename(f)[:-5]
        if PAT.match(b):
            names.append(b)
        else:
            skipped.append(b)
    if not names:
        print("✘ 没有可用单元")
        return 3
    out = os.path.join(a.run_dir, "UNITS-%s.txt" % a.tag)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(names) + "\n")
    os.replace(tmp, out)
    h = hashlib.sha256(open(out, "rb").read()).hexdigest()
    print("✔ 单元清单：%s" % out)
    print("   单元数 %d ｜ 跳过的非单元文件 %d ｜ sha256 %s" % (len(names), len(skipped), h))
    if skipped:
        print("   ★ 跳过（★ 命名不符单元格式 ★）：%s" % ", ".join(skipped[:5]))
    print()
    print("★ 用法：所有分析脚本加 --unit-list %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
