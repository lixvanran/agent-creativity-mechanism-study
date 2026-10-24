#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 把「部分预判决」的数字从 `partial_verdict.json` 填进交付报告 ★

★ ★★ 为什么要有这个脚本（★ 纪律）★★
★ 报告里的数字 > 10 个 ⇒ **必须由脚本从 analysis 填**；★ 手抄 = 抄错的温床。
★ ⇒ ★ 本脚本：★ 读 `partial_verdict.json` ⇒ ★ 改写报告里被【锚点】定位的那几行
★ ⇒ ★ **锚点找不到 ⇒ SystemExit（★ 响亮失败，★ 不许留空、不许静默跳过 ★）**

★ ★★ 额外修掉一个手抄才会出的错 ★★
★ 报告 6.10.4 的 4c 行曾把【单格值 +0.6045】写在【题级方向】列 ⇒ ★ **标签与数值错配**
★ ⇒ ★ 本脚本的题级方向一律取 json 里的 `dir_votes`（★ 那是脚本自己算的题级均值 ★）
★ ⇒ ★ **手抄这一列不可能对，★ 脚本才对。★★**

用法：
    python3 -B creativity_lab/experiments/fill_report_partial.py \
        --report docs/交付/第二组交付报告_2026-10-25.md \
        --json runs/topo-arm-v2-2026-10-25/partial_verdict.json
"""

import argparse
import json
import os
import re
import sys


def die(msg):
    print("✘ %s" % msg)
    sys.exit(1)


def one(s, old, new, tag):
    """★ 锚点必须【唯一命中】；★ 命中 0 次或 >1 次都响亮失败。★"""
    n = s.count(old)
    if n != 1:
        die("锚点[%s]命中 %d 次（★ 期望恰好 1 次 ★）：%r" % (tag, n, old[:70]))
    return s.replace(old, new)



def replace_line(s, prefix, new_line, tag):
    """★ 按【行前缀】定位并【整行替换】★ —— 比整串匹配稳（★ 表格里的加粗标记会变 ★）。★"""
    lines = s.split("\n")
    idx = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
    if len(idx) != 1:
        die("行[%s]命中 %d 次（★ 期望恰好 1 次 ★）：%r" % (tag, len(idx), prefix[:60]))
    lines[idx[0]] = new_line
    return "\n".join(lines)



def re_sub_once(s, pat, repl, tag, flags=0):
    """★ 正则替换：★ 命中次数必须【恰好 1】；★ 否则响亮失败。★"""
    n = len(re.findall(pat, s, flags))
    if n != 1:
        die("正则[%s]命中 %d 次（★ 期望恰好 1 次 ★）：%r" % (tag, n, pat))
    return re.sub(pat, repl, s, count=1, flags=flags)


def fmt(x, nd=4):
    return ("%." + str(nd) + "f") % x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--contaminated-unit", default=None,
                    help="★ 已知污染单元的 basename（★ 用于报告 6.12.2 的单元数与臂 n ★）")
    a = ap.parse_args()

    if not os.path.isfile(a.report):
        die("报告不存在：%s" % a.report)
    if not os.path.isfile(a.json):
        die("json 不存在：%s" % a.json)

    d = json.load(open(a.json, encoding="utf-8"))
    h0 = d["h0"]
    n_actual = d["n_units_actual"]
    n_target = d["n_units_target"]
    theta0 = d["theta0"]
    verdicts = d.get("verdicts") or {}

    # ★ 找不到对比字典就响亮失败（★ 不许静默跳过 ★）
    if not verdicts:
        die("json 里没有对比结果字典（★ 键：%s ★）" % list(d.keys()))

    s = open(a.report, encoding="utf-8").read()

    # ── 6.10.2 H0 表 ──
    v = h0["vendi"]
    m = h0["modes"]
    sd = h0["structured_dedup"]
    n_pairs = v.get("n_pairs", 0)
    s = replace_line(s, "| 可用配对 |", "| 可用配对 | **%d**（★ 目标 21：正式批 `nosel_b3` 6 题×2rep=12 + 旧批 `nosel_b5` 3 题×3rep=9 ★） |" % n_pairs, "6.10.2 配对数")
    s = re_sub_once(s, r"题内 rep σ = [0-9]+ 个同臂同题 rep 差",
            "题内 rep σ = %d 个同臂同题 rep 差" % n_pairs, "6.10.2 σ 描述")
    s = replace_line(s, "| **vendi** | σ =",
            "| **vendi** | σ = **%s**（CI [%s, %s]）｜ q95 = **%s**(nr) / **%s**(lin)（CI [%s, %s]）｜ **X₀ = q95/√2 = %s** ｜ **θ₀ = %.2f σ** |"
            % (fmt(v["sigma_rep"]), fmt(v["sigma_bootstrap_ci"][0]), fmt(v["sigma_bootstrap_ci"][1]),
               fmt(v["q95_nearest_rank"]), fmt(v["q95_linear"]),
               fmt(v["q95_bootstrap_ci"][0]), fmt(v["q95_bootstrap_ci"][1]),
               fmt(v["X0_q95_over_sqrt2"]), v["theta0_standardized"]), "6.10.2 vendi 行")
    s = replace_line(s, "| modes | σ =",
            "| modes | σ = %s ｜ X₀ = %s ｜ θ₀ = %.2f σ |"
            % (fmt(m["sigma_rep"]), fmt(m["X0_q95_over_sqrt2"]), m["theta0_standardized"]), "6.10.2 modes 行")
    s = re_sub_once(s, r"⇒ ★ 本轮用\*\*全部臂\*\*的同题 rep 差（n=[0-9]+）★",
            "⇒ ★ 本轮用**全部臂**的同题 rep 差（n=%d）★" % n_pairs, "6.10.2 口径登记")
    s = replace_line(s, "| **structured_dedup** | ★ **σ =",
            "| **structured_dedup** | ★ **σ = %s、q95 = %s（所有组恒为 5/5）★★ |"
            % (fmt(sd["sigma_rep"]), fmt(sd["q95_nearest_rank"])), "6.10.2 sdedup 行")

    # ── 6.10.4 主判据表（★ 逐格、题级方向全部从 json 取 ★）──
    for name, label in (("H-TOPO-4a", "有无交互"), ("H-TOPO-4c", "有无综述"),
                        ("H-TOPO-4d", "轮内可见性图")):
        if name not in verdicts:
            die("json 里缺对比 %s（★ 键：%s ★）" % (name, list(verdicts.keys())))
        c = verdicts[name]
        cells = c["cells"]
        n_cells = c["n_cells"]
        stds = [x["vendi_std"] for x in cells]
        n_over = sum(1 for x in stds if abs(x) > theta0)
        cell_txt = " ｜ ".join(("**%.2f**" % abs(x) if abs(x) > theta0 else "%.2f" % abs(x))
                               for x in stds)
        # ★ 题级方向：★ 取 json 的 dir_votes（★ 那是题级均值，★ 不是单格值 ★）
        dir_txt = []
        for tid, mean, sgn in c["dir_votes"]:
            dir_txt.append("%s %+.4f" % (tid, mean))
        dir_txt = " ｜ ".join(dir_txt)
        # ★ 方向相反 ⇒ 加标注
        pos = c["pos"]; neg = c["neg"]
        if pos > 0 and neg > 0:
            dir_txt += " ⇒ **方向相反**"
        # ★ 定位旧行：★ 行前缀式（★ 幂等：★ 不依赖旧行的具体数字 ★）★★
        prefix = "| **%s** | %s |" % (name, label)
        new_line = ("| **%s** | %s | %d | %s | %d/%d | ★ %s |"
                    % (name, label, n_cells, cell_txt, n_over, n_cells, dir_txt))
        s = replace_line(s, prefix, new_line, "6.10.4 %s 行" % name)

    s = re_sub_once(s, r"### 6\.10\.4 主判据（★ 标准化效应量 = 差值 ÷ 题内 σ ｜ 门槛 θ₀ = [0-9.]+ σ",
            "### 6.10.4 主判据（★ 标准化效应量 = 差值 ÷ 题内 σ ｜ 门槛 θ₀ = %.2f σ" % theta0,
            "6.10.4 标题")
    s = re_sub_once(s, r"★ \*\*检出力地板（★ 报「不可分辨」时必须同时报 ★）\*\*：★ \*\*θ₀ = [0-9.]+ σ\*\*",
            "★ **检出力地板（★ 报「不可分辨」时必须同时报 ★）**：★ **θ₀ = %.2f σ**" % theta0,
            "6.10.4 检出力地板")

    # ── 6.10.5 结论句的 n ──
    s = re_sub_once(s, r"「在已跑批的 \*\*[0-9]+/[0-9]+\*\* 单元（[^）]*）上",
            "「在已跑批的 **%d/%d** 单元（★ 快照：已跑题 %s，★ 每题 %s rep，★ 6 臂，每组 5 份综述后 proposal）上"
            % (n_actual, n_target, "、".join(d.get("tids") or []),
               "、".join(str(x) for x in (d.get("reps") or []))),
            "6.10.5 结论句 n")
    # ★ 快照说明：★ 幂等（★ 两种形态都接受，★ 已是目标形态则跳过 ★）
    _note = "（★ **本段数字由 `fill_report_partial.py` 从 `partial_verdict.json` 自动填入** ★ ⇒ ★ **n 会随批推进变化** ★ ⇒ ★ 交稿前以脚本重填为准 ★）"
    if _note not in s:
        s = re_sub_once(s, r"（★ 快照时点[^）]*★）", _note, "6.10.5 快照说明")

    # ★ 6.10.6 表里的 θ₀
    s = re_sub_once(s, r"\| 检出力地板 \| θ₀ = \*\*[0-9.]+ σ\*\*",
            "| 检出力地板 | θ₀ = **%.2f σ**" % theta0, "6.10.6 检出力地板")

    open(a.report, "w", encoding="utf-8").write(s)
    print("✔ 已填：n=%d/%d ｜ θ₀=%.2fσ ｜ vendi σ=%s ｜ n_pairs=%d"
          % (n_actual, n_target, theta0, fmt(v["sigma_rep"]), n_pairs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
