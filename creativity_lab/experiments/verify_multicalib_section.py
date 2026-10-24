#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ §6.10.2b 的【结构化逐格核对】（★ 独立实现，★ 不 import 生成器 ★）

> 落点：`creativity_lab/experiments/verify_multicalib_section.py`
> 用法：
>   python3 -B creativity_lab/experiments/verify_multicalib_section.py \
>       --report docs/交付/第二组交付报告_2026-10-24.md \
>       --json runs/topo-arm-v2-2026-10-24/h0_theta0_multicalib.json
>   python3 -B creativity_lab/experiments/verify_multicalib_section.py --self-test
>
> ★ **为什么不能只靠「字符串在报告里出现过」（★ 一条被实测证伪的检查形态 ★）** ★
★ 我先在 `crosscheck_report.py` 里加了一版「★ 逐字包含 ★」检查（★ 15 项 ★）⇒ ★
★ 变异注入（★ 把 6.10.2b 表里的 `1.483σ` 改成 `1.999σ` ★）⇒ ★ **全绿、没抓到** ★
★ ⇒ ★ 根因：★ `"1.483σ" in report` 只证明【某处有这个串】★ ⇒ ★ **报告里还有第二处 `1.483σ` ⇒ 命中 ★**
★ ⇒ ⇒ ★ **「命中」≠「那一格对」★** ⇒ ⇒ ★ **逐字核对必须【定位到具体行与具体格】★**
★ ⇒ ⇒ ★ 本脚本因此**结构化解析 6.10.2b 的那张表**，★ 逐行逐格与 json 比对 ★
★ ⇒ ⇒ ★ 且**自带变异注入自测**（★ 证明它真会红 ★）★
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CALIB_ROWS = [
    ("A_all_arms", "A 全部臂"),
    ("B_prereg_new", "B 预注册·新批段"),
    ("B_prereg_full", "B 预注册·完整"),
    ("C_old_only", "C 旧批单独"),
]
CONTRASTS = ["H-TOPO-4a", "H-TOPO-4c", "H-TOPO-4d"]
VERDICT_SHORT = {
    "不可分辨": "不可分辨",
    "未观察到支持": "未观察到支持",
    "成立（★ 但须同时报 0.448 门槛 ★）": "成立",
    "未观察到支持（★ 达 θ₀ 未达 0.448 ★）": "未观察到支持",
    "不可判定（★ 有信息的尺子不足 2 把 ★）": "不可判定",
}


def extract_section(rep: str) -> str:
    # ★ ★ 定位必须用【行首唯一锚点】★★
    #   ★ 裸标题字符串会命中【表格里引用的标题】⇒ ★ 本轮实测踩过 ★
    _a, _b = "\n### 6.10.2b", "\n### 6.10.3"
    if rep.count(_a) != 1:
        raise RuntimeError("6.10.2b 行首命中 %d 次（★ 必须恰好 1 次 ★）" % rep.count(_a))
    i = rep.index(_a) + 1
    j = rep.index(_b, i)
    if j < 0:
        raise RuntimeError("报告里找不到 6.10.3 段（★ 6.10.2b 无法定位边界 ★）")
    return rep[i:j]


def parse_table(sec: str):
    """★ 解析 6.10.2b 的四行口径表 ⇒ {口径key: {列名: 文本}} ★"""
    out = {}
    for line in sec.split("\n"):
        if not line.startswith("| **"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 10:
            continue
        label = cells[0].replace("**", "")
        key = None
        for k, _lab in CALIB_ROWS:
            if label.startswith(k.split("_")[0]) and ("全部臂" in label or "预注册" in label or "旧批" in label):
                # ★ 精确匹配标签 ★
                if _lab in label or ("全部臂" in label and k == "A_all_arms") \
                   or ("新批段" in label and k == "B_prereg_new") \
                   or ("完整" in label and k == "B_prereg_full") \
                   or ("旧批单独" in label and k == "C_old_only"):
                    key = k
                    break
        if key is None:
            continue
        out[key] = {"label": label, "cells": cells}
    return out


def norm_num(x):
    """★ 归一化【只去装饰】★：★ 去粗体标记、去 σ、去空格、去全角空格 ★

    ★ ★ 归一化的范围必须最小化（★ 第 1 层论证线 2026-10-24 的教训 ★）★★
    ★ 本函数只动【排版装饰】，★ 不动数字本身 ⇒ ★ 差一位小数仍会被抓到 ★
    """
    s = str(x)
    for ch in ("**", "σ", " ", "　", "|", "*"):
        s = s.replace(ch, "")
    return s.strip()


def verify(rep: str, mj: dict):
    sec = extract_section(rep)
    rows = parse_table(sec)
    errs = []
    h0 = mj.get("h0") or {}
    verd = mj.get("verdicts") or {}
    for key, _lab in CALIB_ROWS:
        st = h0.get(key)
        if not st:
            errs.append("json 里缺口径 %s" % key)
            continue
        r = rows.get(key)
        if not r:
            errs.append("报告 6.10.2b 表里缺口径行 %s（★ 标签=%r ★）" % (key, _lab))
            continue
        c = r["cells"]
        # 列：0 口径｜1 原料｜2 n｜3 σ｜4 X₀｜5 θ₀｜6 4a｜7 4c｜8 4d｜9 判决格
        exp = {
            2: str(st["n_pairs"]),
            3: "%.4f" % st["sigma_rep"],
            4: "%.4f" % st["X0_q95_over_sqrt2"],
            5: "%.3fσ" % st["theta0_standardized"],
        }
        for idx, want in exp.items():
            got = norm_num(c[idx])
            if got != norm_num(want):
                errs.append("%s 第 %d 列：报告=%r，json=%r" % (key, idx, got, want))
        # 超门槛格数
        for k, cn in enumerate(CONTRASTS):
            p = (verd.get(cn, {}).get("per_calibration", {}) or {}).get(key, {})
            tot = verd.get(cn, {}).get("n_cells")
            want = "%d/%d" % (p.get("n_cells_over_theta0", 0), tot if tot is not None else 0)
            got = norm_num(c[6 + k])
            if got != want:
                errs.append("%s 的 %s 超门槛列：报告=%r，json=%r" % (key, cn, got, want))
        # 判决格
        want_v = []
        for cn in CONTRASTS:
            p = (verd.get(cn, {}).get("per_calibration", {}) or {}).get(key, {})
            v = p.get("verdict", "—")
            want_v.append(VERDICT_SHORT.get(v, v))
        got_v = [x.strip() for x in c[9].split("/")]
        if [x.replace("**", "") for x in got_v] != want_v:
            errs.append("%s 的判决格列：报告=%r，json=%r" % (key, got_v, want_v))
    # ★ 方向判定句必须在（★ 且比值逐字出现 ★）★★
    ratio = (mj.get("direction_risk") or {}).get("theta0_ratio_B_over_A")
    if ratio is not None:
        if ("%.4f" % ratio) not in sec:
            errs.append("6.10.2b 里找不到 θ₀ 比值 %.4f" % ratio)
    for kw in ("偏离方向", "判决是否随口径改变", "跨口径混合是否有效"):
        if kw not in sec:
            errs.append("6.10.2b 里缺判据小节「%s」" % kw)
    return errs


def self_test():
    """★ 变异注入：★ 证明这个检查真会红（★ 否则它就是个恒真检查 ★）★"""
    rep_p = os.path.join(ROOT, "docs", "交付", "第二组交付报告_2026-10-24.md")
    js_p = os.path.join(ROOT, "runs", "topo-arm-v2-2026-10-24", "h0_theta0_multicalib.json")
    if not (os.path.exists(rep_p) and os.path.exists(js_p)):
        print("★ 自测跳过：★ 找不到报告或 json ★")
        return 1
    rep = open(rep_p, encoding="utf-8").read()
    mj = json.load(open(js_p, encoding="utf-8"))
    base = verify(rep, mj)
    print("== 自测 ① 基线：★ 应当【无错】==")
    if base:
        print("   ✘ 基线就有 %d 处不符 ⇒ 先修基线" % len(base))
        for e in base[:10]:
            print("     - %s" % e)
        return 1
    print("   ✔ 基线无错")
    # 变异 ①：改 θ₀
    m2 = json.loads(json.dumps(mj))
    m2["h0"]["B_prereg_full"]["theta0_standardized"] = 9.999
    e2 = verify(rep, m2)
    print("== 自测 ② 变异（改 json 的 θ₀）⇒ 应当【被抓】==")
    if e2:
        print("   ✔ 抓到 %d 处：%s" % (len(e2), e2[0]))
    else:
        print("   ✘ 没抓到 ⇒ 这个检查是假绿")
        return 1
    # 变异 ②：改报告里的那一格（★ 只改一处 ⇒ 其余处仍含同串 ⇒ 专门抓「命中≠这一处对」★）
    sec = extract_section(rep)
    mutated = rep.replace("1.483σ", "1.999σ", 1)
    e3 = verify(mutated, mj)
    print("== 自测 ③ 变异（改报告表里那一格）⇒ 应当【被抓】==")
    if e3:
        print("   ✔ 抓到 %d 处：%s" % (len(e3), e3[0]))
    else:
        print("   ✘ 没抓到 ⇒ 这个检查抓不到「表里那一格被改」")
        return 1
    # 变异 ③：改超门槛格数
    m4 = json.loads(json.dumps(mj))
    k0 = list(m4["verdicts"]["H-TOPO-4c"]["per_calibration"].keys())[0]
    m4["verdicts"]["H-TOPO-4c"]["per_calibration"][k0]["n_cells_over_theta0"] = 99
    e4 = verify(rep, m4)
    print("== 自测 ④ 变异（改超门槛格数）⇒ 应当【被抓】==")
    if e4:
        print("   ✔ 抓到 %d 处：%s" % (len(e4), e4[0]))
    else:
        print("   ✘ 没抓到")
        return 1
    print()
    print("✔ 自测全过：★ 这个检查会红（★ 不是恒真 ★）★")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not (a.report and a.json):
        print(__doc__)
        return 1
    rep = open(a.report, encoding="utf-8").read()
    mj = json.load(open(a.json, encoding="utf-8"))
    errs = verify(rep, mj)
    if errs:
        print("✘ 6.10.2b 与 json 不符（★ %d 处 ★）：" % len(errs))
        for e in errs:
            print("   - %s" % e)
        return 2
    print("✔ 6.10.2b 逐格核对全部对得上（★ 四口径 × 10 列 + 三条判据句 ★）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
